"""V1.21.0 KEEP+ID development screen: commit inputs and the KEEP call schedule (no model).
Usage: kid_generate.py --hub HUB --src-hub HUB_1_20
1. Copies the 1.20 public targets and hidden cases into HUB/data/inputs/ after checking both against the 1.20 freeze
   hashes (the hidden copy is for later validation/scoring only; this script never opens it after copying).
2. Selects the primary arrival and correction targets (192) from the PUBLIC file only.
3. Builds each KEEP+ID prompt with tempo.keepid.build (public-only RES-DET identity, BASE prompt + one annotation line).
4. Writes HUB/data/kid-calls.jsonl (one KEEP call per target, cap 256, seeded order), the public ledger
   HUB/data/kid-ledger.jsonl and HUB/data/COMMITMENT-kid.json."""
import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import keepid as KI, render

SCHED_SEED = 20261110
ACTS = ("arrival", "correction")
FROZEN_1_20 = {"public/ref-targets.jsonl": "289f767fea0aeb9550eef5deee5128561630976f7ee955a5dffc81c1337a7e8f",
               "hidden/ref-cases.jsonl": "a0685deefd32a6222322e252f64a68f6a15156cd67f3f329207678dd0a3809f9"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def call(cid, u, cap=256):
    return {"call_id": cid, "group_id": cid.split("|")[0], "domain": "assembly", "surface": "prose", "k": 0,
            "length": "short", "arm": "KEEP", "pattern": "KEEP", "qtype": "X", "variant": cid, "n_records": 0,
            "evidence_cutoff": 0, "max_new_tokens": cap, "system": render.SYSTEM, "user": u,
            "user_sha256": hashlib.sha256(u.encode()).hexdigest()}


def select(pubs):
    return [p for p in pubs if p["component"] == "primary" and p["act"] in ACTS]


def build_calls(pubs):
    """Public rows -> (calls in schedule order, ledger rows). Deterministic; reads nothing else."""
    led, calls = [], []
    for p in select(pubs):
        b = KI.build(p)
        if b is None:
            raise SystemExit(f"{p['target']}: no public identity")
        prompt, L = b
        calls.append(call(f"{p['target']}|KEEP", prompt))
        led.append({"target": p["target"], "group": p["group"], "family": p["family"], "reception": p["reception"],
                    "act": p["act"], "history": p["history"], "stratum": p["stratum"], **L})
    random.Random(SCHED_SEED).shuffle(calls)
    return calls, led


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--src-hub", required=True)
    a = ap.parse_args()
    data, src = Path(a.hub) / "data", Path(a.src_hub) / "data"
    if (data / "COMMITMENT-kid.json").exists():
        raise SystemExit("commitment exists")
    (data / "inputs").mkdir(parents=True, exist_ok=True)
    copied = {}
    for rel, h in FROZEN_1_20.items():
        if sha(src / rel) != h:
            raise SystemExit(f"1.20 {rel} differs from its freeze hash")
        dst = data / "inputs" / Path(rel).name
        shutil.copyfile(src / rel, dst)
        copied[rel] = {"dst": str(dst.relative_to(a.hub)), "sha256": sha(dst)}
    pubs = [json.loads(l) for l in (data / "inputs" / "ref-targets.jsonl").read_text().splitlines() if l.strip()]
    calls, led = build_calls(pubs)
    for name, rows in (("kid-calls.jsonl", calls), ("kid-ledger.jsonl", led)):
        with open(data / name, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": "kid", "rule": KI.RULE, "source_sha256": release_source_hash(ROOT), "schedule_seed": SCHED_SEED,
           "calls": len(calls), "calls_sha256": sha(data / "kid-calls.jsonl"),
           "ledger_sha256": sha(data / "kid-ledger.jsonl"), "inputs": copied,
           "by_family_act": {f"{x['family']}|{x['act']}": sum(1 for y in led if (y['family'], y['act']) == (x['family'], x['act']))
                             for x in led}}
    (data / "COMMITMENT-kid.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("calls", "calls_sha256", "by_family_act")}))


if __name__ == "__main__":
    main()
