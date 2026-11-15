"""One-retry branch runner (live): replays each history/surface through the frozen pipeline with the committed
initial replies and asks the model for at most one retry per rejected record. Offline, static greedy inference.

Usage: repair_run.py --hub HUB --set SET --initial-stage S0 --stage S1 --config CFG [--fake REPLIES.json]
CFG keys: max_retries, max_seconds, model (as tempo_run). Each retry is written atomically to
HUB/stages/S1/calls/<call>.json (prompt sha, raw reply, tokens, trigger code) before the pipeline continues; a rerun
reuses complete records whose prompt sha matches and refuses a mismatch. Budget stop -> STOP.json, else END.json.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import atomic_json, release_source_hash
from tempo import engine_fixtures as EF, repair as RP
from tempo_run import FakeModel, HFModel, n_tokens, safe

SYSTEM_SET_KEYS = ("histories", "calls", "gold")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def inputs(hub, set_):
    data = hub / "data"
    commit = json.loads((data / f"COMMITMENT-{set_}.json").read_text())
    for p in SYSTEM_SET_KEYS:
        if sha((data / f"{set_}-{p}.jsonl").read_bytes()) != commit[f"{p}_sha256"]:
            raise SystemExit(f"{set_}-{p} does not match its commitment")
    hs = load(data / f"{set_}-histories.jsonl")
    calls = {c["call_id"]: c for c in load(data / f"{set_}-calls.jsonl")}
    gold = {g["call_id"]: g for g in load(data / f"{set_}-gold.jsonl")}
    return hs, calls, gold


def initial_replies(hub, stage, calls):
    out = {}
    for cid, c in calls.items():
        p = hub / "stages" / stage / "calls" / f"{safe(cid)}.json"
        r = json.loads(p.read_text())
        if not r.get("complete") or r["user_sha256"] != c["user_sha256"]:
            raise SystemExit(f"initial record {p} incomplete or mismatched")
        out[cid] = r["raw"] if r["status"] == "ok" else None
    return out


def branch_inputs(h, calls, gold, surface, init):
    hid = h["history_id"]
    ks = [k for k in range(1, 7) if f"{hid}|{surface}|r{k}" in calls]
    cid = lambda k: f"{hid}|{surface}|r{k}"
    return dict(spec=EF.spec_from_world(h["world"], h["domain"], h["records"]),
                surface_texts={k: h["texts"][surface][k - 1] for k in ks},
                prompts={k: calls[cid(k)]["user"] for k in ks},
                registries={k: gold[cid(k)]["registry"] for k in ks},
                initial_raw={k: init[cid(k)] for k in ks},
                now_of=lambda k: h["records"][k - 1]["received_at"]), ks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--initial-stage", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--fake")
    a = ap.parse_args()
    hub = Path(a.hub)
    cfg_text = Path(a.config).read_text()
    cfg = json.loads(cfg_text)
    hs, calls, gold = inputs(hub, a.set)
    init = initial_replies(hub, a.initial_stage, calls)
    out = hub / "stages" / a.stage
    (out / "calls").mkdir(parents=True, exist_ok=True)
    lock = {"config_sha256": sha(cfg_text.encode()), "source_sha256": release_source_hash(ROOT),
            "calls_sha256": sha((hub / "data" / f"{a.set}-calls.jsonl").read_bytes()),
            "initial_stage": a.initial_stage, "fake": bool(a.fake)}
    lp = out / "LOCK.json"
    if lp.exists() and json.loads(lp.read_text()) != lock:
        raise SystemExit("stage locked to different hashes")
    atomic_json(lp, lock)
    state = {"model": None, "new": 0, "t0": time.time(), "stop": None}

    def model():
        if state["model"] is None:
            state["model"] = FakeModel(a.fake) if a.fake else HFModel(cfg["model"])
        return state["model"]

    manifest = []
    for h in hs:
        for surface in ("lines", "prose"):
            kw, ks = branch_inputs(h, calls, gold, surface, init)
            if not ks:
                continue
            base = calls[f"{h['history_id']}|{surface}|r{ks[0]}"]

            def retry_fn(k, prompt, h=h, surface=surface):
                cid = f"{h['history_id']}|{surface}|r{k}|retry"
                p = out / "calls" / f"{safe(cid)}.json"
                psha = sha(prompt.encode())
                if p.exists():
                    r = json.loads(p.read_text())
                    if r.get("user_sha256") != psha or not r.get("complete"):
                        raise SystemExit(f"retry record {p} does not match its prompt; inspect")
                    return r["raw"] if r["status"] == "ok" else None
                if state["stop"]:
                    return None
                if state["new"] >= cfg["max_retries"] or time.time() - state["t0"] > cfg["max_seconds"]:
                    state["stop"] = "retry budget reached"
                    return None
                m = model(); m.current = cid
                ids = m.encode(base["system"], prompt)
                t0 = time.time()
                rec = {"call_id": cid, "user_sha256": psha, "history_id": h["history_id"], "surface": surface, "k": k,
                       "input_tokens": n_tokens(ids), "model": m.identity}
                try:
                    text, n_out, stop = m.generate(ids, base["max_new_tokens"])
                    rec.update(status="ok", raw=text, output_tokens=n_out, stop=stop)
                except Exception as e:  # infrastructure only; one retry
                    with open(out / "attempts.jsonl", "a") as fh:
                        fh.write(json.dumps({"call_id": cid, "error": repr(e)[:300]}) + "\n")
                    try:
                        text, n_out, stop = m.generate(ids, base["max_new_tokens"])
                        rec.update(status="ok", raw=text, output_tokens=n_out, stop=stop)
                    except Exception:
                        rec.update(status="infra_failed", raw=None, output_tokens=0, stop=None)
                rec.update(seconds=round(time.time() - t0, 3), complete=True, prompt=prompt,
                           finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
                atomic_json(p, rec)
                state["new"] += 1
                atomic_json(out / "STATUS.json", {"retries": state["new"], "last": cid,
                                                  "elapsed_s": round(time.time() - state["t0"], 1)})
                return rec["raw"]
            rows, _ = RP.run_branch(context=f"{h['history_id']}|{surface}|one-retry", retry_fn=retry_fn, **kw)
            manifest += [{"history_id": h["history_id"], "surface": surface, "k": r["k"],
                          "trigger": r["initial"]["code"], "retried": r["retried"],
                          "retry_accepted": r.get("retry", {}).get("accepted")} for r in rows if r["retried"]]
    atomic_json(out / "RETRIES.json", manifest)
    summ = {"finished": state["stop"] is None, "stop_reason": state["stop"], "new_retry_calls": state["new"],
            "retries_needed": len(manifest), "elapsed_s": round(time.time() - state["t0"], 1),
            "peak_gib": round(state["model"].peak_gib(), 2) if state["model"] else 0.0,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    atomic_json(out / ("END.json" if state["stop"] is None else "STOP.json"), summ)
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
