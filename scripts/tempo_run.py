"""Temporal pilot runner: static greedy inference over committed calls. No adapters, no training, no gold access.

Usage: tempo_run.py --hub HUB --stage NAME --config CONFIG.json [--fake RESPONSES.json]
Config keys: set (smoke|main), select ("all" or list of call_ids), order_seed, max_seconds, max_calls,
max_input_tokens, retry_limit (infrastructure errors only), model (path/manifest/dtype/device/enable_thinking).

Records: HUB/stages/NAME/calls/<call>.json written atomically after each complete call (raw reply, token counts,
stop reason, seconds, input hash). LOCK.json binds the stage to one config/calls/source hash: a resume under any
changed hash is refused. Infrastructure failures are logged to attempts.jsonl; after retry_limit retries the call is
recorded as infra_failed (final). STATUS.json is refreshed after every call; END.json marks a finished queue;
STOP.json records a budget stop (resumable).
"""
import argparse
import hashlib
import json
import random
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import atomic_json, release_source_hash


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def safe(cid):
    return cid.replace("|", "__")


class HFModel:
    def __init__(self, cfg):
        import torch
        from dream_core.modeling import load_local_model
        self.torch = torch
        self.model, self.tok, self.manifest = load_local_model(cfg)
        eos = self.model.generation_config.eos_token_id
        self.eos = set(eos if isinstance(eos, list) else [eos]) | {self.tok.eos_token_id}
        self.identity = {"revision": self.manifest.get("revision"), "path": cfg["path"], "dtype": cfg["dtype"],
                         "enable_thinking": cfg["enable_thinking"], "decoding": "greedy",
                         "torch": torch.__version__}
        import transformers
        self.identity["transformers"] = transformers.__version__

    def encode(self, system, user):
        from dream_core.modeling import render_chat
        text = render_chat(self.tok, user, system=system, enable_thinking=False)
        return self.tok(text, return_tensors="pt", add_special_tokens=False).input_ids

    def generate(self, ids, cap):
        torch = self.torch
        ids = ids.to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=cap,
                                      do_sample=False, temperature=None, top_p=None, top_k=None,
                                      pad_token_id=self.tok.pad_token_id)
        new = out[0, ids.shape[1]:].tolist()
        stop = "eos" if new and new[-1] in self.eos else "length"
        text = self.tok.decode(new, skip_special_tokens=True)
        return text, len(new), stop

    def peak_gib(self):
        return self.torch.cuda.max_memory_allocated() / 2 ** 30


class FakeModel:
    """Test double: replies from a call_id -> text map (or a default)."""
    def __init__(self, path):
        self.replies = json.loads(Path(path).read_text())
        self.identity = {"revision": "fake", "decoding": "fake"}
        self.fail_once = set(self.replies.pop("_fail_once", []))

    def encode(self, system, user):
        return {"n": len((system + user).split()), "user": user}

    def generate(self, ids, cap):
        cid = self.current
        if cid in self.fail_once:
            self.fail_once.discard(cid)
            raise RuntimeError("simulated infrastructure failure")
        return self.replies.get(cid, self.replies.get("_default", '{"choice": "A"}')), 5, "eos"

    def peak_gib(self):
        return 0.0


def n_tokens(ids):
    return ids["n"] if isinstance(ids, dict) else int(ids.shape[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--fake")
    a = ap.parse_args()
    hub = Path(a.hub)
    cfg_text = Path(a.config).read_text()
    cfg = json.loads(cfg_text)
    data = hub / "data"
    commit = json.loads((data / f"COMMITMENT-{cfg['set']}.json").read_text())
    calls_path = data / f"{cfg['set']}-calls.jsonl"
    calls_bytes = calls_path.read_bytes()
    if sha_bytes(calls_bytes) != commit["calls_sha256"]:
        raise SystemExit("calls file does not match its commitment")
    out = hub / "stages" / a.stage
    (out / "calls").mkdir(parents=True, exist_ok=True)
    lock = {"config_sha256": sha_bytes(cfg_text.encode()), "calls_sha256": commit["calls_sha256"],
            "source_sha256": release_source_hash(ROOT), "fake": bool(a.fake)}
    lock_path = out / "LOCK.json"
    if lock_path.exists():
        old = json.loads(lock_path.read_text())
        if old != lock:
            raise SystemExit(f"stage locked to different hashes: {old} vs {lock}")
    else:
        atomic_json(lock_path, lock)
    (out / "config.json").write_text(cfg_text)
    calls = [json.loads(l) for l in calls_bytes.decode().splitlines()]
    if cfg["select"] != "all":
        want = set(cfg["select"])
        calls = [c for c in calls if c["call_id"] in want]
        if len(calls) != len(want):
            raise SystemExit("select names unknown calls")
    if cfg.get("order") != "as_committed":  # V1.16.0: optional precommitted schedule; default unchanged
        random.Random(cfg["order_seed"]).shuffle(calls)

    def done(c):
        p = out / "calls" / f"{safe(c['call_id'])}.json"
        if not p.exists():
            return False
        try:
            r = json.loads(p.read_text())
        except ValueError:
            raise SystemExit(f"corrupted record {p}; inspect before resuming")
        if r.get("user_sha256") != c["user_sha256"] or not r.get("complete"):
            raise SystemExit(f"record {p} does not match its call; inspect before resuming")
        return True

    todo = [c for c in calls if not done(c)]
    t_start = time.time()
    (out / f"start-{int(t_start)}.json").write_text(json.dumps(
        {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "planned": len(calls), "todo": len(todo), **lock}, indent=2))
    model = FakeModel(a.fake) if a.fake else HFModel(cfg["model"])
    load_s = time.time() - t_start
    n_new, stop_reason = 0, None
    for c in todo:
        elapsed = time.time() - t_start
        if elapsed > cfg["max_seconds"]:
            stop_reason = f"max_seconds {cfg['max_seconds']} reached"
            break
        if n_new >= cfg["max_calls"]:
            stop_reason = f"max_calls {cfg['max_calls']} reached"
            break
        rec = {k: c[k] for k in ("call_id", "group_id", "domain", "pattern", "length", "arm", "qtype", "variant",
                                 "n_records", "evidence_cutoff", "max_new_tokens", "user_sha256")}
        rec["model"] = model.identity
        model.current = c["call_id"]
        ids = model.encode(c["system"], c["user"])
        rec["input_tokens"] = n_tokens(ids)
        if rec["input_tokens"] > cfg["max_input_tokens"]:
            rec.update(status="input_too_long", raw=None, output_tokens=0, stop=None, seconds=0.0, complete=True)
        else:
            attempt = 0
            while True:
                t0 = time.time()
                try:
                    text, n_out, stop = model.generate(ids, c["max_new_tokens"])
                    rec.update(status="ok", raw=text, output_tokens=n_out, stop=stop,
                               seconds=round(time.time() - t0, 3), attempts=attempt + 1, complete=True)
                    break
                except Exception as e:  # infrastructure only: model content never raises
                    with open(out / "attempts.jsonl", "a") as fh:
                        fh.write(json.dumps({"call_id": c["call_id"], "attempt": attempt + 1, "error": repr(e)[:500],
                                             "at": time.strftime("%H:%M:%S")}) + "\n")
                    if hasattr(model, "torch"):
                        model.torch.cuda.empty_cache()
                    attempt += 1
                    if attempt > cfg["retry_limit"]:
                        rec.update(status="infra_failed", raw=None, output_tokens=0, stop=None, seconds=0.0,
                                   attempts=attempt, complete=True)
                        break
        rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        atomic_json(out / "calls" / f"{safe(c['call_id'])}.json", rec)
        n_new += 1
        n_done = len(calls) - len(todo) + n_new
        el = time.time() - t_start
        atomic_json(out / "STATUS.json", {"done": n_done, "planned": len(calls), "new_this_run": n_new,
                                          "elapsed_s": round(el, 1), "load_s": round(load_s, 1),
                                          "peak_gib": round(model.peak_gib(), 2),
                                          "eta_s": round((el - load_s) / n_new * (len(todo) - n_new), 0),
                                          "last": c["call_id"], "at": time.strftime("%H:%M:%S")})
    finished = all(done(c) for c in calls)
    summary = {"finished": finished, "stop_reason": stop_reason, "new_this_run": n_new,
               "elapsed_s": round(time.time() - t_start, 1), "load_s": round(load_s, 1),
               "peak_gib": round(model.peak_gib(), 2), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    atomic_json(out / ("END.json" if finished else "STOP.json"), summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
