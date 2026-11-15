"""Commit the deferred-goal transfer inputs (no model).
Usage: goaltr_generate.py --hub HUB --set goaltr|goaltrsmoke [--base-seed 20261113]
Writes HUB/data/<set>-{episodes,calls,gold}.jsonl + COMMITMENT-<set>.json (refuses to overwrite).
Goals are fixed by the episode specification (transfer.episode_specs) before any extraction exists; the extraction
calls are built from the history alone (no goal) and are shared by both goal clones."""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import history as Hm, prose_study as PS, render, text_channel as TC, transfer as T

SMOKE = [("delivery", "false_block", "b_delayed", 0, True), ("delivery", "unresolved", "b_prov_false", 0, False),
         ("assembly", "false_permission", "b_changed", 1, True), ("assembly", "corrected", "b_corrected", 0, True)]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_set(set_name, base_seed):
    if set_name == "goaltr":
        specs = T.episode_specs(set_name, base_seed)
    else:
        specs = [{"episode_id": f"{set_name}-{d[:3]}-{at}-0", "domain": d, "a_type": at, "b_type": bt, "b_j": bj,
                  "a_item_is_x": ax,
                  "seed": int(hashlib.sha256(f"{base_seed}|{set_name}|{d}|{at}".encode()).hexdigest()[:12], 16)}
                 for d, at, bt, bj, ax in SMOKE]
    out, rejected = [], []
    for s in specs:
        for att in range(80):
            try:
                w, ep = T.build(s["episode_id"], s["domain"], s["a_type"], s["b_type"], s["b_j"], s["a_item_is_x"],
                                s["seed"] + att, set_name)
                texts = TC.prose_texts(w, ep)
                for r, t in zip(ep["records_v02"], texts):
                    PS.check_equivalent(r, t)
                break
            except AssertionError as e:
                rejected.append({"episode_id": s["episode_id"], "seed": s["seed"] + att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {s['episode_id']}")
        ep["prose_texts"] = texts
        out.append((w, ep))
    return out, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["goaltr", "goaltrsmoke"], required=True)
    ap.add_argument("--base-seed", type=int, default=20261113)
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    data.mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    built, rejected = build_set(a.set, a.base_seed)
    eps, calls, golds = [], [], []
    for w, ep in built:
        eps.append(ep)
        eid = ep["episode_id"]
        for k, u in enumerate(TC.prompts(w, ep), 1):
            cid = f"{eid}|prose|r{k}"
            calls.append({"call_id": cid, "group_id": eid, "domain": ep["domain"], "pattern": f"{ep['a_type']}/{ep['b_type']}",
                          "surface": "prose", "k": k, "length": "short", "arm": "text", "qtype": "X", "variant": f"r{k}",
                          "n_records": k, "evidence_cutoff": ep["records_v02"][k - 1]["received_at"],
                          "max_new_tokens": 256, "system": render.SYSTEM, "user": u,
                          "user_sha256": hashlib.sha256(u.encode()).hexdigest()})
            golds.append({"call_id": cid, "type": "record", "gold": Hm.public(ep["records_v02"][k - 1]),
                          "registry": {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, ep["records_v02"][:k])},
                          "text": ep["prose_texts"][k - 1]})
    for name, rows in (("episodes", eps), ("calls", calls), ("gold", golds)):
        with open(data / f"{a.set}-{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    rec = {"set": a.set, "base_seed": a.base_seed, "source_sha256": release_source_hash(ROOT), "episodes": len(eps),
           "calls": len(calls), "rejected_attempts": rejected, "adapter": TC.ADAPTER_VERSION,
           "goals_fixed_by": "transfer.episode_specs + transfer.build (before any extraction)",
           **{f"{p}_sha256": sha(data / f"{a.set}-{p}.jsonl") for p in ("episodes", "calls", "gold")}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "episodes", "calls", "calls_sha256")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
