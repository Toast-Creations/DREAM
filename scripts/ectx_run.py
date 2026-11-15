"""Run one stage of the explicit-context study (smoke / development / sealed). Resumable.

Stage config (JSON) keys:
  split            "dev" or "sealed"
  episodes         list of episode IDs (explicit; recorded)
  mode             "w_only" (instruction selection) or "full" (train adapters, then W, W+A, W+X)
  system           key in ectx.runtime.SYSTEM_PROMPTS
  lora             {"rank", "alpha", "targets"}
  train            {"steps", "lr", "n_aug", "weight_decay"}
  seed             integer; adapter seed for episode i = seed + i
  conditions       optional (V1.6.3): subset/order of ["W", "W+A", "W+X", "W+Y"]; default W, W+A, W+X
  cross_partners   required with W+Y: {target: donor} from a different world; every donor used exactly once,
                   each world's targets drawing donors from both other worlds (validated before model load)
  adapters_from    optional: stage whose saved adapters are reused (no training); split must match; files are
                   verified against that stage's training records
  reset_tolerance  declared max |logit diff| between adapter-removed and clean-load outputs on the
                   reference and task probes (also used for the save/load functional check); exceeding
                   it at any check stops the stage.
The sealed split opens only if HUB/FROZEN-PROTOCOL.json exists, records David's approval, and its
config hash and the sealed data hash match.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from _bootstrap import ROOT
from dream_core import localpaths as LP  # public release: local paths from environment
from ectx import runtime
from dream_core.ledger import release_source_hash

MODEL = {"path": f"{LP.MODELS}/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218",
         "manifest": f"{LP.MODELS}/Qwen3-8B/model-manifest.json",
         "dtype": "bfloat16", "device": "cuda", "enable_thinking": False}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_split(hub, split):
    path = Path(hub) / "data" / f"{split}.jsonl"
    name = "COMMITMENT.json" if split in ("dev", "sealed") else f"COMMITMENT-{split}.json"
    commit = json.loads((Path(hub) / "data" / name).read_text())
    if sha(path) != commit[f"{split}_sha256"]:
        raise SystemExit(f"{split}.jsonl does not match its commitment")
    return {e["episode_id"]: e for e in map(json.loads, path.read_text().splitlines())}


def partners(ids, episodes):
    """W+X derangement: each episode borrows the next same-family episode's adapter (cyclic)."""
    out = {}
    for fam in ("delivery", "assembly", "workshop"):
        fam_ids = [i for i in ids if episodes[i]["family"] == fam]
        if len(fam_ids) == 1:
            raise SystemExit(f"W+X needs at least two {fam} episodes")
        for k, i in enumerate(fam_ids):
            out[i] = fam_ids[(k + 1) % len(fam_ids)]
    return out


def validate_cross(mapping, ids, episodes):
    """W+Y donors: different world, each target once, each donor once, both other worlds used per world."""
    fam = lambda i: episodes[i]["family"]
    if sorted(mapping) != sorted(ids):
        raise SystemExit("cross_partners must cover every target exactly once")
    if sorted(mapping.values()) != sorted(ids):
        raise SystemExit("each donor must be used exactly once")
    for t, d in mapping.items():
        if fam(t) == fam(d):
            raise SystemExit(f"cross donor {d} is from the same world as {t}")
    for f in {fam(i) for i in ids}:
        donors = {fam(mapping[t]) for t in ids if fam(t) == f}
        if len(donors) != 2:
            raise SystemExit(f"{f} targets must draw donors from both other worlds")
    return mapping


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hub", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    hub = Path(a.hub)
    cfg_text = Path(a.config).read_text()
    cfg = json.loads(cfg_text)
    out = hub / "stages" / a.stage
    out.mkdir(parents=True, exist_ok=True)
    saved_cfg = out / "config.json"
    if saved_cfg.exists() and saved_cfg.read_text() != cfg_text:
        raise SystemExit("stage exists with a different config; use a new stage name")
    saved_cfg.write_text(cfg_text)
    if cfg["split"] == "sealed":
        frozen = json.loads((hub / "FROZEN-PROTOCOL.json").read_text())
        if not frozen.get("approved_by_david") or frozen["config_sha256"] != hashlib.sha256(cfg_text.encode()).hexdigest():
            raise SystemExit("sealed stage requires David-approved FROZEN-PROTOCOL.json matching this config")
        if frozen["source_sha256"] != release_source_hash(ROOT):
            raise SystemExit("source changed since the protocol was frozen")
    episodes = load_split(hub, cfg["split"])
    ids = cfg["episodes"]
    missing = [i for i in ids if i not in episodes]
    if missing:
        raise SystemExit(f"unknown episodes: {missing}")
    tol = cfg["reset_tolerance"]  # required: declared before any adaptation
    if not isinstance(tol, (int, float)) or tol < 0:
        raise SystemExit("reset_tolerance must be a non-negative number")
    conditions = cfg.get("conditions", ["W", "W+A", "W+X"])
    if not set(conditions) <= {"W", "W+A", "W+X", "W+Y"} or len(set(conditions)) != len(conditions):
        raise SystemExit(f"bad conditions {conditions}")
    pair = partners(ids, episodes) if cfg["mode"] == "full" else {}  # validated before the model loads
    cross = validate_cross(cfg["cross_partners"], ids, episodes) if "W+Y" in conditions else {}
    adapter_dir, train_dir = out / "adapters", out / "train"
    if cfg.get("adapters_from"):
        src_stage = hub / "stages" / cfg["adapters_from"]
        if json.loads((src_stage / "config.json").read_text())["split"] != cfg["split"]:
            raise SystemExit("adapters_from stage used a different split")
        adapter_dir, train_dir = src_stage / "adapters", src_stage / "train"
        if not all((train_dir / f"{i}.json").exists() for i in ids):
            raise SystemExit("adapters_from stage lacks training records for some episodes")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    start = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_sha256": release_source_hash(ROOT),
             "config_sha256": hashlib.sha256(cfg_text.encode()).hexdigest(), "model": MODEL,
             "reset_tolerance": tol, "wx_partners": pair, "wy_cross_partners": cross, "conditions": conditions,
             "adapters_from": cfg.get("adapters_from"), "task_probe_qid": episodes[ids[0]]["queries"][0]["qid"]}
    from ectx import render
    rt = runtime.Runtime(MODEL, cfg["lora"], cfg["system"],
                         task_probe=render.user_prompt(episodes[ids[0]], episodes[ids[0]]["queries"][0]))

    def enforce(where):
        detail = rt.removal_detail()
        if max(detail.values()) > tol:
            (out / "RESET-FAILURE.json").write_text(json.dumps({"where": where, "detail": detail, "tolerance": tol}, indent=2))
            raise SystemExit(f"reset check failed at {where}: {detail} > {tol}")
        return detail

    start.update(model_revision=rt.manifest["revision"], base_fingerprint=rt.base_fingerprint,
                 base_full_sha256=rt.full_hash(), removal_at_start=enforce("start"))
    (out / f"start-{int(time.time())}.json").write_text(json.dumps(start, indent=2) + "\n")
    (out / "train").mkdir(exist_ok=True); (out / "adapters").mkdir(exist_ok=True); (out / "eval").mkdir(exist_ok=True)
    from safetensors.torch import save_file, load_file
    if cfg["mode"] == "full" and not cfg.get("adapters_from"):
        for k, eid in enumerate(ids):
            rec_path = out / "train" / f"{eid}.json"
            if rec_path.exists():
                continue
            state, rec, trained_logits = rt.train_adapter(episodes[eid], "ectxtrain", cfg["seed"] + k, cfg["train"])
            apath = out / "adapters" / f"{eid}.safetensors"
            save_file(state, str(apath))
            rt.load_adapter("ectxreload", load_file(str(apath)))  # raises unless weights match exactly
            reload_diff = float((rt.adapter_probe("ectxreload") - trained_logits).abs().max())
            rt.drop_adapter("ectxreload")
            if reload_diff > tol:
                raise SystemExit(f"save/load functional check failed for {eid}: {reload_diff}")
            rec.update(adapter_sha256=sha(apath), fingerprint_after=rt.fingerprint(),
                       saveload_task_probe_maxdiff=reload_diff,
                       trained_vs_base_task_probe_maxdiff=float((trained_logits - rt.reference_logits.get("task", rt.reference_logits["reference"])).abs().max()),
                       removal_after=enforce(f"after training {eid}"))
            rec["base_unchanged"] = rec["fingerprint_after"] == rt.base_fingerprint
            if not rec["base_unchanged"]:
                raise SystemExit(f"base weights changed after training {eid}")
            rec_path.write_text(json.dumps(rec, indent=2) + "\n")
            print("trained", eid, rec["seconds"], "s loss", round(rec["loss_first"], 3), "->", round(rec["loss_last"], 3), flush=True)
    trained = {eid: json.loads((train_dir / f"{eid}.json").read_text())["adapter_sha256"]
               for eid in ids} if cfg["mode"] == "full" else {}
    for eid in ids:
        ev_path = out / "eval" / f"{eid}.jsonl"
        if ev_path.exists():
            continue
        t0 = time.time()
        if cfg["mode"] == "w_only":
            with rt.peft.disable_adapter():
                rows = rt.answer_all(episodes[eid], "W")
        else:
            donors = {"W+A": eid, "W+X": pair[eid], "W+Y": cross.get(eid)}
            adapters = {}
            for cond in conditions:
                if cond == "W":
                    continue
                x = donors[cond]
                path = adapter_dir / f"{x}.safetensors"
                if sha(path) != trained[x]:
                    raise SystemExit(f"adapter file for {x} changed since training")
                adapters[cond] = (load_file(str(path)), x)
            rows = rt.evaluate_conditions(episodes[eid], conditions, adapters)
        detail = enforce(f"after evaluating {eid}")
        check = {"episode_id": eid, "qid": "_reset", "fingerprint_unchanged": rt.fingerprint() == rt.base_fingerprint,
                 "removal_detail": detail, "removal_maxdiff": max(detail.values()), "eval_seconds": round(time.time() - t0, 2)}
        if not check["fingerprint_unchanged"]:
            raise SystemExit(f"base weights changed during {eid}")
        ev_path.write_text("".join(json.dumps(r) + "\n" for r in rows + [check]))
        acc = {c: sum(r["correct"] for r in rows if r["condition"] == c and not r["qid"].startswith("unrelated"))
               for c in conditions}
        print("evaluated", eid, acc, f"{check['eval_seconds']}s", flush=True)
    end = {"finished": time.strftime("%Y-%m-%dT%H:%M:%S"), "base_full_sha256": rt.full_hash(),
           "removal_at_end": enforce("end")}
    end["base_full_hash_unchanged"] = end["base_full_sha256"] == start["base_full_sha256"]
    (out / f"end-{int(time.time())}.json").write_text(json.dumps(end, indent=2) + "\n")
    print(json.dumps(end, indent=2))
    return 0 if end["base_full_hash_unchanged"] else 1


if __name__ == "__main__":
    sys.exit(main())
