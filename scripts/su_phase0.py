"""Phase0 evidence for study D (V1.29.0, Codex pre-freeze review F1/F2): build the historical inventory and validate
the CONTENT of every phase0 record, not only VALIDATION.json's summary. Stdlib only; no model calls.

validate(hub, cfg, source_sha256) -> list of problems (empty = pass). It is called by su_prepare.freeze() and by
su_certify.check_freeze(), so a failed, stale, contradictory or selectively assembled record cannot be frozen or
certified. Studies A-C (frozen on V1.27.0) are not checked here; their behavior is unchanged.

Checks for D:
- FULL-TESTS.json: the full container suite on this exact source: success, no failures/errors/skips, consistent
  counts, ML dependencies present (the --require-ml run).
- TOKENS.json: all_pass, exactly the declared calls per stage x arm, bound to the hashes of the checked schedules,
  positive ranges with maxima <= the stage limit.
- VALIDATION.json: all_pass on this source, and its components agree with FULL-TESTS/TOKENS.
- HISTORICAL.json: recomputed from the files themselves; every emitted summary field must equal the recomputation. Every required earlier hub (13) is inventoried with
  exactly the JSONL files under its data/ that carry a BASE prompt or world seed (nested suite hubs included, all
  of public/hidden x main/smoke); each entry's hash and counts match the file; per-hub sums match; malformed rows
  fail; and this panel has zero prompt/seed overlap with the union, recomputed here.
- COMMITMENT.json: the generator's historical inputs are, by exact canonical path, every inventoried file of every
  required hub that carries BASE prompts (its prompt and seed files alike), and its recorded counts match them.
"""
import hashlib
import json
from pathlib import Path
from dream_core import localpaths as LP  # public release: local paths from environment

HISTORICAL_ROOT = Path(f"{LP.RUNS}")   # production; CPU fixtures inject a synthetic tree
MAX_INPUT_TOKENS = 2048
PANEL_FILES = ("data/public/main-targets.jsonl", "data/public/smoke-targets.jsonl",
               "data/hidden/main-cases.jsonl", "data/hidden/smoke-cases.jsonl")
SUITE_HUBS = tuple(f"temporal-event-suite-20261112-195430/{n}" for n in ("A-confirm", "B-narrowed", "C-wrongbind"))
REQUIRED_HUBS_D = frozenset({
    "temporal-keepid-confirm-20261110-150658", "temporal-keepid-dev-20261110-104944",
    "temporal-reference-resolution-20261106-171704", "temporal-revision-value-clarification-20261111-015000",
    "temporal-clarified-keep-confirm-20261111-063336", "temporal-explicit-subject-dev-20261111-210104",
    "temporal-event-report-dev-20261112-070245",
    # seed-only earlier hubs (no BASE prompts): covered by phase0, not by the generator's input list
    "temporal-factored-assertions-20261106-101739", "temporal-larger-extractor-20261106-123049",
    "temporal-record-context-20261106-075907", *SUITE_HUBS})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scan(path):
    """-> (rows, prompt rows, seed rows, prompt set, seed set). Malformed or non-object rows raise (F2)."""
    rows = prompt_rows = seed_rows = 0
    prompts, seeds = set(), set()
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)   # ValueError on malformed JSON
        if not isinstance(r, dict):
            raise ValueError(f"{path}:{n}: non-object row")
        rows += 1
        if "base_prompt" in r:
            prompt_rows += 1
            prompts.add(r["base_prompt"])
        if "world_seed" in r:
            seed_rows += 1
            seeds.add(r["world_seed"])
    return rows, prompt_rows, seed_rows, prompts, seeds


def hub_files(name, root=None):
    """Every JSONL file under the hub's data/ that carries a BASE prompt or world seed, relative to the hub."""
    hub = Path(root or HISTORICAL_ROOT) / name
    out = {}
    for f in sorted((hub / "data").rglob("*.jsonl")):
        res = scan(f)
        if res[3] or res[4]:
            out[str(f.relative_to(hub))] = res
    return out


def panel_sets(hub):
    p, s = set(), set()
    for rel in PANEL_FILES:
        res = scan(Path(hub) / rel)
        p |= res[3]
        s |= res[4]
    return p, s


def build_historical(hub, root=None):
    """The phase0 HISTORICAL.json record for a D hub (raises on overlap or a malformed row)."""
    root = Path(root or HISTORICAL_ROOT)
    inventory, all_p, all_s = [], set(), set()
    for name in sorted(REQUIRED_HUBS_D):
        for rel, (rows, _pr, _sr, prompts, seeds) in hub_files(name, root).items():
            inventory.append({"hub": name, "file": rel, "sha256": sha(root / name / rel), "rows": rows,
                              "base_prompts": len(prompts), "world_seeds": len(seeds)})
            all_p |= prompts
            all_s |= seeds
    by_hub = {}
    for e in inventory:
        b = by_hub.setdefault(e["hub"], {"files": 0, "base_prompts": 0, "world_seeds": 0})
        b["files"] += 1
        b["base_prompts"] += e["base_prompts"]
        b["world_seeds"] += e["world_seeds"]
    p, s = panel_sets(hub)
    overlap = {"historical_prompts": len(p & all_p), "historical_seeds": len(s & all_s)}
    if any(overlap.values()):
        raise ValueError("overlap found: " + json.dumps(overlap))
    return {"purpose": "pre-freeze historical-coverage evidence (EVTT-v1, su_phase0); no model calls",
            "root": str(root), "required_hubs": sorted(REQUIRED_HUBS_D),
            "unique_historical_base_prompts": len(all_p), "unique_historical_world_seeds": len(all_s),
            "by_hub": by_hub, "inventory": inventory,
            "panel_sizes": {"base_prompts": len(p), "world_seeds": len(s)},
            "overlap_with_historical": overlap, "all_zero_overlap": True}


def _int(x):
    return type(x) is int


def _full_tests(hub, source, problems):
    ft = json.loads((Path(hub) / "phase0/FULL-TESTS.json").read_text())
    if not isinstance(ft, dict):
        problems.append("FULL-TESTS: not an object")
        return {}
    counts = [ft.get(k) for k in ("tests_run", "passed", "failures", "errors", "skipped")]
    if not all(_int(c) for c in counts):
        problems.append("FULL-TESTS: missing or non-integer counts")
        return ft
    run, passed, failures, errors, skipped = counts
    if ft.get("source_sha256") != source:
        problems.append("FULL-TESTS: not run on the current source")
    if ft.get("success") is not True or failures or errors:
        problems.append("FULL-TESTS: the full suite did not pass")
    if run <= 0 or skipped != 0 or passed != run or ft.get("skipped_tests", []) != []:
        problems.append("FULL-TESTS: counts inconsistent, empty or with skips")
    if ft.get("ml_dependencies_available") is not True:
        problems.append("FULL-TESTS: not the full container (--require-ml) run")
    return ft


def _tokens(hub, cfg, problems):
    tok = json.loads((Path(hub) / "phase0/TOKENS.json").read_text())
    if not isinstance(tok, dict):
        problems.append("TOKENS: not an object")
        return {}
    arms = list(cfg["arms"])
    want = {f"{stage}|{arm}": cfg[f"{stage}_calls"] // len(arms) for stage in ("smoke", "main") for arm in arms}
    got = tok.get("by_stage_arm")
    if tok.get("all_pass") is not True:
        problems.append("TOKENS: token validation did not pass")
    if tok.get("calls_checked") != cfg["main_calls"] + cfg["smoke_calls"]:
        problems.append("TOKENS: wrong number of checked calls")
    if not isinstance(got, dict) or set(got) != set(want):
        problems.append("TOKENS: stage x arm cells differ from the declared arms")
    else:
        for k, n in want.items():
            v = got[k]
            if not isinstance(v, dict) or v.get("count") != n or not all(_int(v.get(x)) for x in ("min", "max")) \
                    or not 0 < v["min"] <= v["max"] <= MAX_INPUT_TOKENS:
                problems.append(f"TOKENS: cell {k} count/range invalid")
    bound = tok.get("calls_sha256")
    if not isinstance(bound, dict) or any(bound.get(s) != sha(Path(hub) / f"data/{s}-calls.jsonl")
                                          for s in ("smoke", "main")):
        problems.append("TOKENS: not bound to the committed smoke/main schedules")
    return tok


def _historical(hub, cfg, problems, root):
    hub = Path(hub)
    hist = json.loads((hub / "phase0/HISTORICAL.json").read_text())
    inv = hist.get("inventory") if isinstance(hist, dict) else None
    if not isinstance(inv, list):
        problems.append("HISTORICAL: inventory missing")
        return
    if hist.get("all_zero_overlap") is not True:
        problems.append("HISTORICAL: overlap recorded")
    listed = {}
    for e in inv:
        if not isinstance(e, dict) or (e.get("hub"), e.get("file")) in listed:
            problems.append("HISTORICAL: malformed or duplicate inventory entry")
            return
        listed[(e["hub"], e["file"])] = e
    all_p, all_s, prompt_files, prompt_rows, seed_rows = set(), set(), set(), 0, 0
    by_hub = {}
    for name in sorted(REQUIRED_HUBS_D):
        try:
            actual = hub_files(name, root)
        except (OSError, ValueError) as e:
            problems.append(f"HISTORICAL: {name} unreadable or malformed: {e!r}"[:300])
            continue
        if not actual:
            problems.append(f"HISTORICAL: required hub {name} has no panel files")
        if name in SUITE_HUBS and not set(PANEL_FILES) <= set(actual):
            problems.append(f"HISTORICAL: nested hub {name} lacks a public/hidden main/smoke file")
        mine = {f for (h, f) in listed if h == name}
        if mine != set(actual):
            problems.append(f"HISTORICAL: {name} inventory differs from its files "
                            f"(missing {sorted(set(actual) - mine)[:3]}, extra {sorted(mine - set(actual))[:3]})")
        for rel, (rows, pr, sr, prompts, seeds) in actual.items():
            e = listed.get((name, rel))
            if e is not None and (e.get("sha256") != sha(Path(root) / name / rel) or e.get("rows") != rows
                                  or e.get("base_prompts") != len(prompts) or e.get("world_seeds") != len(seeds)):
                problems.append(f"HISTORICAL: entry {name}/{rel} differs from the file")
            b = by_hub.setdefault(name, {"files": 0, "base_prompts": 0, "world_seeds": 0})
            b["files"] += 1
            b["base_prompts"] += len(prompts)
            b["world_seeds"] += len(seeds)
            all_p |= prompts
            all_s |= seeds
        if any(res[3] for res in actual.values()):   # a prompt-bearing hub: all its files feed the generator
            for rel, (_rows, pr, sr, _p, _s) in actual.items():
                prompt_files.add(str((Path(root) / name / rel).resolve()))
                prompt_rows += pr
                seed_rows += sr
    if {h for (h, _f) in listed} - REQUIRED_HUBS_D:
        problems.append("HISTORICAL: inventory lists hubs outside the declared set")
    if hist.get("by_hub") != by_hub:
        problems.append("HISTORICAL: per-hub coverage differs from the files")
    # every emitted summary field must equal the recomputation (Codex recheck RC1)
    if hist.get("required_hubs") != sorted(REQUIRED_HUBS_D):
        problems.append("HISTORICAL: required_hubs differs from the declared hubs")
    if hist.get("unique_historical_base_prompts") != len(all_p) or \
            hist.get("unique_historical_world_seeds") != len(all_s):
        problems.append("HISTORICAL: unique historical counts differ from the files")
    p, s = panel_sets(hub)
    if p & all_p or s & all_s:
        problems.append("HISTORICAL: this panel overlaps the historical inventory")
    if hist.get("overlap_with_historical") != {"historical_prompts": len(p & all_p),
                                               "historical_seeds": len(s & all_s)}:
        problems.append("HISTORICAL: recorded overlap counts differ from the recomputation")
    if hist.get("panel_sizes") != {"base_prompts": len(p), "world_seeds": len(s)}:
        problems.append("HISTORICAL: panel sizes do not describe this panel")
    commit = json.loads((hub / "data/COMMITMENT.json").read_text())["historical_checked"]
    used = {str(Path(f).resolve()) for f in commit["files"]}
    if used != prompt_files or len(used) != len(commit["files"]):
        problems.append(f"COMMITMENT: generator historical inputs differ from the inventory "
                        f"(missing {sorted(prompt_files - used)[:3]}, extra {sorted(used - prompt_files)[:3]})")
    if commit["prompts"] != prompt_rows or commit["world_seeds"] != seed_rows:
        problems.append("COMMITMENT: recorded historical counts differ from the input files")


FULL_COMPONENT_KEYS = {"tests_run", "passed", "failures", "errors", "skipped", "success", "env"}
TOKEN_COMPONENT_KEYS = {"calls_checked", "max_input_tokens", "limit", "all_pass"}


def _validation(hub, source, ft, tok, problems):
    v = json.loads((Path(hub) / "phase0/VALIDATION.json").read_text())
    comp = v.get("components", {}) if isinstance(v, dict) else {}
    if not isinstance(v, dict) or v.get("all_pass") is not True or v.get("source_sha256") != source:
        problems.append("VALIDATION: did not pass on the current source")
        return
    fts, toks = comp.get("full_test_suite", {}), comp.get("tokens", {})
    if not isinstance(fts, dict) or fts.get("tests_run") != ft.get("tests_run") or fts.get("passed") != ft.get("passed") \
            or "--require-ml" not in str(fts.get("env", "")):
        problems.append("VALIDATION: full-suite component contradicts FULL-TESTS or is not --require-ml")
    # closed component schemas; every optional status/counter field must agree with the record (Codex recheck RC2)
    if isinstance(fts, dict):
        if set(fts) - FULL_COMPONENT_KEYS:
            problems.append(f"VALIDATION: unsupported full-suite component fields {sorted(set(fts) - FULL_COMPONENT_KEYS)}")
        for k in ("failures", "errors", "skipped", "success"):
            if k in fts and fts[k] != ft.get(k):
                problems.append(f"VALIDATION: full-suite component {k} contradicts FULL-TESTS")
    if isinstance(toks, dict):
        if set(toks) - TOKEN_COMPONENT_KEYS:
            problems.append(f"VALIDATION: unsupported token component fields {sorted(set(toks) - TOKEN_COMPONENT_KEYS)}")
        if "limit" in toks and toks["limit"] != MAX_INPUT_TOKENS:
            problems.append("VALIDATION: token component limit differs from the declared limit")
        if "all_pass" in toks and toks["all_pass"] is not tok.get("all_pass"):
            problems.append("VALIDATION: token component all_pass contradicts TOKENS")
    cells = tok.get("by_stage_arm") if isinstance(tok.get("by_stage_arm"), dict) else {}
    top = max((c.get("max", 0) for c in cells.values() if isinstance(c, dict)), default=None)
    if not isinstance(toks, dict) or toks.get("calls_checked") != tok.get("calls_checked") or \
            toks.get("max_input_tokens") != top:
        problems.append("VALIDATION: token component contradicts TOKENS")


def validate(hub, cfg, source, root=None):
    """-> problems (empty = pass). Only study D is checked (A-C frozen on V1.27.0 are unchanged)."""
    if cfg["key"] != "D":
        return []
    problems = []
    root = Path(root or HISTORICAL_ROOT)
    for part, fn in (("FULL-TESTS", lambda: _full_tests(hub, source, problems)),
                     ("TOKENS", lambda: _tokens(hub, cfg, problems))):
        try:
            fn()
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            problems.append(f"{part}: unreadable or invalid: {e!r}"[:300])
    try:
        ft = json.loads((Path(hub) / "phase0/FULL-TESTS.json").read_text())
        tok = json.loads((Path(hub) / "phase0/TOKENS.json").read_text())
        _validation(hub, source, ft if isinstance(ft, dict) else {}, tok if isinstance(tok, dict) else {}, problems)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        problems.append(f"VALIDATION: unreadable or invalid: {e!r}"[:300])
    try:
        _historical(hub, cfg, problems, root)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        problems.append(f"HISTORICAL: unreadable or invalid: {e!r}"[:300])
    return problems


if __name__ == "__main__":   # su_phase0.py historical HUB  -> writes HUB/phase0/HISTORICAL.json
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "historical":
        raise SystemExit("usage: su_phase0.py historical HUB")
    rec = build_historical(sys.argv[2])
    (Path(sys.argv[2]) / "phase0/HISTORICAL.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("unique_historical_base_prompts", "unique_historical_world_seeds",
                                         "panel_sizes", "all_zero_overlap")}), len(rec["by_hub"]), "hubs")
