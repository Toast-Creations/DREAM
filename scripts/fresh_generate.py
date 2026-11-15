"""Commit the V1.12.0 observation-freshness panel (no model, no controller output).
Usage: fresh_generate.py --hub HUB --set fresh|freshsmoke [--base-seed N]
Writes HUB/data/public/<set>-worlds.jsonl (controller inputs: fixed facts, reports, goals, public transition
declarations), HUB/data/hidden/<set>-hidden.jsonl (environment only: truth, tape, seed, case labels, generator
records) and HUB/data/COMMITMENT-<set>.json (hashes; refuses to overwrite)."""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import freshgen as FG, freshness as F

DEFAULT_SEED = {"fresh": 20261207, "freshsmoke": 20261208}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_set(set_name, base_seed):
    out, rejected = [], []
    for domain, row, seed in FG.specs(set_name, base_seed, smoke=set_name == "freshsmoke"):
        for att in range(80):
            try:
                w, pub, hid = FG.build(row, domain, seed + att, set_name)
                for tr in pub["transitions"]:
                    F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
                break
            except AssertionError as e:
                rejected.append({"world_id": row[0], "seed": seed + att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {row[0]}")
        out.append((pub, hid))
    return out, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["fresh", "freshsmoke"], required=True)
    ap.add_argument("--base-seed", type=int)
    a = ap.parse_args()
    seed = a.base_seed or DEFAULT_SEED[a.set]
    data = Path(a.hub) / "data"
    (data / "public").mkdir(parents=True, exist_ok=True)
    (data / "hidden").mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    built, rejected = build_set(a.set, seed)
    pp, hp = data / "public" / f"{a.set}-worlds.jsonl", data / "hidden" / f"{a.set}-hidden.jsonl"
    with open(pp, "w") as fp, open(hp, "w") as fh:
        for pub, hid in built:
            fp.write(json.dumps(pub, sort_keys=True) + "\n")
            fh.write(json.dumps(hid, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "worlds": len(built),
           "rejected_attempts": rejected, "public_sha256": sha(pp), "hidden_sha256": sha(hp),
           "allocation": "tempo.freshgen." + ("SMOKE_D/SMOKE_A" if a.set == "freshsmoke" else "DELIVERY/ASSEMBLY"),
           "model_calls": 0}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "worlds", "public_sha256", "hidden_sha256")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
