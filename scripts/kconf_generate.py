"""V1.22.0 KEEP+ID confirmation: commit the fresh panel and call schedule (no model).
Usage: kconf_generate.py --hub HUB --config HUB/config/PANEL.json [--historical PATH ...]

PANEL.json (frozen with the design; every value explicit):
  {"base_seed", "pool", "smoke_base_seed", "smoke_pool", "consonants", "id_prefix", "smoke_prefix",
   "n_correction_groups", "n_arrival_groups", "smoke_groups", "schedule_seed"}
Writes HUB/data/: public/{main,smoke}-targets.jsonl, hidden/{main,smoke}-cases.jsonl, {main,smoke}-calls.jsonl,
construction-rejections.jsonl, COMMITMENT.json. Refuses to overwrite. --historical gives prior public-target files
(1.20 ref-targets) whose prompts and world seeds must not reappear (asserted)."""
import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import ROOT
from dream_core.ledger import release_source_hash
from tempo import kidconf as KC, kidconfgen as KG

KEYS = ("base_seed", "pool", "smoke_base_seed", "smoke_pool", "consonants", "id_prefix", "smoke_prefix",
        "n_correction_groups", "n_arrival_groups", "smoke_groups", "schedule_seed")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")


def generate(cfg, historical_prompts=(), historical_seeds=()):
    missing = [k for k in KEYS if k not in cfg]
    if missing:
        raise SystemExit(f"config missing {missing}")
    if cfg["n_arrival_groups"] > cfg["n_correction_groups"]:
        raise SystemExit("arrival groups must be a nested subset of correction groups")
    if cfg["pool"] == cfg["smoke_pool"] or cfg["id_prefix"] == cfg["smoke_prefix"] or cfg["base_seed"] == cfg["smoke_base_seed"]:
        raise SystemExit("smoke must be disjoint from main (pool, id prefix, seed)")
    if any(p.startswith("g0") for p in (cfg["id_prefix"], cfg["smoke_prefix"])):
        raise SystemExit("id prefix would collide with historical gNNN ids")
    for pool in (cfg["pool"], cfg["smoke_pool"]):
        KG.register_pool(pool, cfg["consonants"])
    if cfg["smoke_groups"] != 4:
        raise SystemExit("smoke is fixed at 4 groups (F1 imm, F2 imm, F3 imm, F3 del), both acts")
    out = {}
    for part in ("main", "smoke"):
        if part == "main":
            groups = KC.plan(cfg["n_correction_groups"], cfg["id_prefix"])
            na, seed, pool = cfg["n_arrival_groups"], cfg["base_seed"], cfg["pool"]
        else:
            groups = [KC.plan(8, cfg["smoke_prefix"])[i] for i in (0, 2, 4, 6)]
            na, seed, pool = 8, cfg["smoke_base_seed"], cfg["smoke_pool"]
        pubs, hid, units, rej = KG.build_panel(groups, na, seed, pool)
        calls = KC.unit_order(units, cfg["schedule_seed"] + (1 if part == "smoke" else 0))
        out[part] = (groups, pubs, hid, calls, rej)
    # disjointness and uniqueness (asserted)
    allp = [p["base_prompt"] for part in out.values() for p in part[1]]
    if len(set(allp)) != len(allp):
        raise SystemExit("duplicate BASE prompts in the new panel")
    hist_p = set(historical_prompts)
    if hist_p & set(allp):
        raise SystemExit("a historical prompt reappears")
    seeds = [(h["world_seed"], h["pool"]) for part in out.values() for h in part[2]]
    if set(s for s, _ in seeds) & set(historical_seeds):
        raise SystemExit("a historical world seed reappears")
    ids = [c["call_id"] for part in out.values() for c in part[3]]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate call ids")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--historical", nargs="*", default=[])
    a = ap.parse_args()
    data = Path(a.hub) / "data"
    if any((data / n).exists() for n in ("COMMITMENT.json", "COMMITMENT-main.json", "COMMITMENT-smoke.json")):
        raise SystemExit("commitment exists")
    cfg = json.loads(Path(a.config).read_text())
    hp, hs = [], []
    for p in a.historical:
        for l in Path(p).read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                if "base_prompt" in r:
                    hp.append(r["base_prompt"])
                if "world_seed" in r:
                    hs.append(r["world_seed"])
    out = generate(cfg, hp, hs)
    files = {}
    for part, (groups, pubs, hid, calls, rej) in out.items():
        for name, rows in ((f"public/{part}-targets.jsonl", pubs), (f"hidden/{part}-cases.jsonl", hid),
                           (f"{part}-calls.jsonl", calls), (f"{part}-construction-rejections.jsonl", rej)):
            write(data / name, rows)
            files[name] = sha(data / name)
    for part in ("main", "smoke"):     # the runner (tempo_run) binds each stage to COMMITMENT-<set>.json
        (data / f"COMMITMENT-{part}.json").write_text(json.dumps(
            {"set": part, "calls": len(out[part][3]), "calls_sha256": files[f"{part}-calls.jsonl"]}, indent=1) + "\n")
    main_groups, main_pubs = out["main"][0], out["main"][1]
    rec = {"set": "kidconf", "rule": "KIDCONF-v1 / KEEPID-v1", "source_sha256": release_source_hash(ROOT),
           "config": cfg, "config_sha256": sha(a.config),
           "allocation": KC.allocation_table(main_groups, cfg["n_arrival_groups"]),
           "main_calls": len(out["main"][3]), "smoke_calls": len(out["smoke"][3]),
           "main_targets": len(main_pubs), "smoke_targets": len(out["smoke"][1]),
           "rejected_attempts": {p: len(v[4]) for p, v in out.items()},
           "historical_checked": {"files": a.historical, "prompts": len(hp), "world_seeds": len(hs)},
           "files_sha256": files}
    (data / "COMMITMENT.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("main_calls", "smoke_calls", "main_targets", "rejected_attempts")}))


if __name__ == "__main__":
    main()
