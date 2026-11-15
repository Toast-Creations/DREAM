"""Commit the text-interface policy study inputs (no model).
Usage: textpol_generate.py --hub HUB --set textpol|textpolsmoke [--base-seed 20261112]
Writes HUB/data/<set>-{episodes,calls,gold}.jsonl + COMMITMENT-<set>.json (refuses to overwrite)."""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import history as Hm, policy as P, prose_study as PS, render, text_channel as TC

SMOKE = [("delivery", "false_block"), ("delivery", "unresolved"), ("assembly", "false_permission"),
         ("assembly", "corrected")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["textpol", "textpolsmoke"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261112)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    if a.set == "textpol":
        specs = P.episode_specs(a.set, a.base_seed)
    else:
        specs = [(f"{a.set}-{d[:3]}-{t}-0", d, t, int(hashlib.sha256(f"{a.base_seed}|{a.set}|{d}|{t}".encode()).hexdigest()[:12], 16))
                 for d, t in SMOKE]
    eps, calls, golds, rejected = [], [], [], []
    for eid, dom, et, seed in specs:
        for att in range(60):
            try:
                w, ep = P.build_episode_world(eid, dom, et, seed + att, a.set)
                texts = TC.prose_texts(w, ep)
                for r, t in zip(ep["records_v02"], texts):
                    PS.check_equivalent(r, t)
                break
            except AssertionError as e:
                rejected.append({"episode_id": eid, "seed": seed + att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {eid}")
        ep["prose_texts"] = texts
        eps.append(ep)
        for k, u in enumerate(TC.prompts(w, ep), 1):
            cid = f"{eid}|prose|r{k}"
            calls.append({"call_id": cid, "group_id": eid, "domain": dom, "pattern": et, "surface": "prose", "k": k,
                          "length": "short", "arm": "text", "qtype": "X", "variant": f"r{k}", "n_records": k,
                          "evidence_cutoff": ep["records_v02"][k - 1]["received_at"], "max_new_tokens": 256,
                          "system": render.SYSTEM, "user": u, "user_sha256": hashlib.sha256(u.encode()).hexdigest()})
            golds.append({"call_id": cid, "type": "record", "gold": Hm.public(ep["records_v02"][k - 1]),
                          "registry": {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, ep["records_v02"][:k])},
                          "text": texts[k - 1]})
    for name, rows in (("episodes", eps), ("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}-{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": a.base_seed, "source_sha256": release_source_hash(ROOT), "episodes": len(eps),
           "calls": len(calls), "rejected_attempts": rejected, "adapter": TC.ADAPTER_VERSION,
           **{f"{p}_sha256": sha(data / f"{a.set}-{p}.jsonl") for p in ("episodes", "calls", "gold")}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "episodes", "calls", "calls_sha256")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
