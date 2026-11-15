"""Commit the V1.15.0 frozen-text integration inputs (no model, no controller output).
Usage: ftx_generate.py --hub HUB --set ftx|ftxsmoke [--base-seed N]
Writes (refuses to overwrite):
  HUB/data/public/<set>-worlds.jsonl   structured public world (controller input for the structured channel)
  HUB/data/public/<set>-text.jsonl     per world: call ids, prose texts, prefix registries, reception times
                                       (public adapter inputs for the text channel; goal-blind)
  HUB/data/<set>-calls.jsonl           one extraction call per past report (scripts/tempo_run.py input)
  HUB/data/hidden/<set>-hidden.jsonl   environment only: truth, tape, seed, labels, generator records
  HUB/data/hidden/<set>-gold.jsonl     scorer only: the public record each call converts (meaning audit)
  HUB/data/COMMITMENT-<set>.json       hashes, exact call count, prompt hashes, ceilings
Redraws follow the existing input-validity rules (declaration check; build assertions; prose equivalence) and are
logged with reasons. Histories are never truncated and no report is discarded to reach a call count."""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import freshness as F, ftxgen as XG, render

DEFAULT_SEED = {"ftx": 20261230, "ftxsmoke": 20261231}
CEILING = {"ftx": 192, "ftxsmoke": 32}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_set(set_name, base_seed):
    out, rejected = [], []
    for domain, row, seed in XG.specs(set_name, base_seed, smoke=set_name.endswith("smoke")):
        for att in range(80):
            try:
                w, pub, hid = XG.build(row, domain, seed + att, set_name)
                for tr in pub["transitions"]:
                    F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
                recs, texts, prompts, regs = XG.text_inputs(w, hid)
                break
            except (AssertionError, F.DeclarationError) as e:
                rejected.append({"world_id": row[0], "seed": seed + att, "reason": str(e)[:200]})
        else:
            raise SystemExit(f"cannot build {row[0]}")
        out.append((pub, hid, recs, texts, prompts, regs))
    return out, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", choices=["ftx", "ftxsmoke"], required=True)
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
    n_calls = sum(len(b[2]) for b in built)
    if n_calls > CEILING[a.set]:
        raise SystemExit(f"{n_calls} calls exceed the ceiling {CEILING[a.set]}; stop before model calls")
    paths = {k: data / f"public/{a.set}-{k}.jsonl" for k in ("worlds", "text")}
    paths.update(hidden=data / f"hidden/{a.set}-hidden.jsonl", gold=data / f"hidden/{a.set}-gold.jsonl",
                 calls=data / f"{a.set}-calls.jsonl")
    fh = {k: open(p, "w") for k, p in paths.items()}
    per_world = {}
    for pub, hid, recs, texts, prompts, regs in built:
        wid = pub["world_id"]
        cids = [f"{wid}|prose|r{k}" for k in range(1, len(recs) + 1)]
        per_world[wid] = len(recs)
        fh["worlds"].write(json.dumps(pub, sort_keys=True) + "\n")
        fh["hidden"].write(json.dumps(hid, sort_keys=True) + "\n")
        fh["text"].write(json.dumps({"world_id": wid, "call_ids": cids, "texts": texts, "registries": regs,
                                     "received": [r["received_at"] for r in recs]}, sort_keys=True) + "\n")
        for k, (cid, u) in enumerate(zip(cids, prompts), 1):
            fh["calls"].write(json.dumps({"call_id": cid, "group_id": wid, "domain": pub["domain"], "surface": "prose",
                                          "k": k, "length": "short", "arm": "text", "pattern": "coverage", "qtype": "X", "variant": f"r{k}",
                                          "n_records": k, "evidence_cutoff": recs[k - 1]["received_at"],
                                          "max_new_tokens": 256, "system": render.SYSTEM, "user": u,
                                          "user_sha256": hashlib.sha256(u.encode()).hexdigest()}, sort_keys=True) + "\n")
            fh["gold"].write(json.dumps({"call_id": cid, "world_id": wid, "k": k, "gold": recs[k - 1],
                                         "text": texts[k - 1]}, sort_keys=True) + "\n")
    for f in fh.values():
        f.close()
    rec = {"set": a.set, "base_seed": seed, "source_sha256": release_source_hash(ROOT), "worlds": len(built),
           "calls": n_calls, "calls_ceiling": CEILING[a.set], "reports_per_world": per_world,
           "rejected_attempts": rejected, "allocation": "tempo.depgen." + ("SMOKE_ROWS" if a.set.endswith("smoke") else "ROWS"),
           "window": [12, 14], "system_prompt_sha256": hashlib.sha256(render.SYSTEM.encode()).hexdigest(),
           **{f"{k}_sha256": sha(p) for k, p in paths.items()}}
    commit.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: rec[k] for k in ("set", "worlds", "calls", "calls_sha256")}), "rejected:", len(rejected))


if __name__ == "__main__":
    main()
