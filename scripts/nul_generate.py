"""Commit the V1.16.0 paired-interface inputs (no model, no controller output).
Usage: nul_generate.py --hub HUB --set nul|nulsmoke [--base-seed N]
Like ftx_generate.py (same files), plus: two calls per past report, ORIGINAL (the frozen 1.15.1 prompt, byte-
identical) and NULL_PRIOR (nullprior.null_prompt of it); call ids "<world>|prose|r<k>|<INTERFACE>". The commitment
records exact counts, per-interface prompt hashes and the source-kind counts (gold kind; stock arrival / removal)."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import freshness as F, nullprior as NP, render

DEFAULT_SEED = {"nul": 20261301, "nulsmoke": 20261302}
CEILING = {"nul": 1536, "nulsmoke": 64}
SCHEDULE_SEED = 20261106


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def kind_class(r):
    p = r["payload"]
    if r["kind"] == "change" and p["field"].endswith(".on_hand"):
        return "stock_arrival" if p["to"] == "yes" else "stock_removal"
    f = (p.get("field") or "multi").split(".")[-1] if r["kind"] != "initial" else "initial"
    return f"{r['kind']}:{f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["nul", "nulsmoke"], required=True)
    ap.add_argument("--base-seed", type=int)
    a = ap.parse_args()
    seed = a.base_seed or DEFAULT_SEED[a.set]
    data = Path(a.hub) / "data"
    (data / "public").mkdir(parents=True, exist_ok=True)
    (data / "hidden").mkdir(parents=True, exist_ok=True)
    commit = data / f"COMMITMENT-{a.set}.json"
    if commit.exists():
        raise SystemExit(f"{commit} exists")
    built, rejected = [], []
    for domain, row, s in NP.specs(a.set, seed, smoke=a.set.endswith("smoke")):
        for att in range(80):
            try:
                w, pub, hid = NP.build(row, domain, s + att, a.set)
                for tr in pub["transitions"]:
                    F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
                ti = NP.text_inputs(w, hid)
                break
            except (AssertionError, F.DeclarationError) as e:
                rejected.append({"world_id": row[0], "seed": s + att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {row[0]}")
        built.append((pub, hid) + ti)
    n_calls = 2 * sum(len(b[2]) for b in built)
    if n_calls > CEILING[a.set]:
        raise SystemExit(f"{n_calls} calls exceed the ceiling {CEILING[a.set]}")
    paths = {k: data / f"public/{a.set}-{k}.jsonl" for k in ("worlds", "text")}
    paths.update(hidden=data / f"hidden/{a.set}-hidden.jsonl", gold=data / f"hidden/{a.set}-gold.jsonl",
                 calls=data / f"{a.set}-calls.jsonl")
    fh = {k: open(p, "w") for k, p in paths.items()}
    call_rows = []
    kinds = collections.Counter()
    phash = {i: hashlib.sha256() for i in NP.INTERFACES}
    for pub, hid, recs, texts, prompts, regs in built:
        wid = pub["world_id"]
        fh["worlds"].write(json.dumps(pub, sort_keys=True) + "\n")
        fh["hidden"].write(json.dumps(hid, sort_keys=True) + "\n")
        base_ids = [f"{wid}|prose|r{k}" for k in range(1, len(recs) + 1)]
        fh["text"].write(json.dumps({"world_id": wid, "call_ids": base_ids, "texts": texts, "registries": regs,
                                     "received": [r["received_at"] for r in recs]}, sort_keys=True) + "\n")
        for k, (bid, u) in enumerate(zip(base_ids, prompts), 1):
            kinds[kind_class(recs[k - 1])] += 1
            for iface in NP.INTERFACES:
                uu = u if iface == "ORIGINAL" else NP.null_prompt(u)
                phash[iface].update(uu.encode())
                call_rows.append(({"call_id": f"{bid}|{iface}", "group_id": wid, "domain": pub["domain"],
                                              "surface": "prose", "k": k, "length": "short", "arm": iface,
                                              "pattern": NP.family(wid), "qtype": "X", "variant": f"r{k}",
                                              "n_records": k, "evidence_cutoff": recs[k - 1]["received_at"],
                                              "max_new_tokens": 256, "system": render.SYSTEM, "user": uu,
                                              "user_sha256": hashlib.sha256(uu.encode()).hexdigest()}))
            fh["gold"].write(json.dumps({"call_id": bid, "world_id": wid, "k": k, "gold": recs[k - 1],
                                         "text": texts[k - 1], "kind_class": kind_class(recs[k - 1])},
                                        sort_keys=True) + "\n")
    # precommitted balanced schedule: reports in a seeded order; interface order alternates pair by pair
    import random
    pairs = collections.defaultdict(dict)
    for c in call_rows:
        pairs[c["call_id"].rsplit("|", 1)[0]][c["arm"]] = c
    keys = sorted(pairs)
    random.Random(SCHEDULE_SEED).shuffle(keys)
    for j, key in enumerate(keys):
        for iface in (NP.INTERFACES if j % 2 == 0 else NP.INTERFACES[::-1]):
            fh["calls"].write(json.dumps(pairs[key][iface], sort_keys=True) + "\n")
    for f in fh.values():
        f.close()
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "worlds": len(built),
           "reports": n_calls // 2, "calls": n_calls, "calls_ceiling": CEILING[a.set], "source_kind_counts": dict(kinds),
           "rejected_attempts": rejected, "interfaces": list(NP.INTERFACES), "schedule": f"seeded report order (seed {SCHEDULE_SEED}), interface order alternating by pair; run with order=as_committed",
           "prompt_stream_sha256": {i: h.hexdigest() for i, h in phash.items()},
           "clarification": NP.CLARIFICATION, "payload_line_original": NP.PAYLOAD_LINE,
           "payload_line_null_prior": NP.NULL_PAYLOAD_LINE,
           "system_prompt_sha256": hashlib.sha256(render.SYSTEM.encode()).hexdigest(),
           **{f"{k}_sha256": sha(p) for k, p in paths.items()}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "worlds", "reports", "calls", "source_kind_counts")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
