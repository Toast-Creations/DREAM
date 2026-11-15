"""Write PLAN.json, DEPENDENCIES.json and INPUT-MANIFEST.json into the results hub BEFORE the replay.

Also re-verifies the owning frozen manifests: each study's FROZEN-PROTOCOL.json source_sha256 against the frozen
source tree (dream_core.ledger.release_source_hash, unchanged) and its listed data/config/design/phase0 file hashes.
Usage: PYTHONDONTWRITEBYTECODE=1 python -B scripts/ig_plan.py --hub RESULTS_HUB --commit GIT_SHA
"""
import os as _os  # public release: local paths from environment
import sys as _sys
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from guard import pins  # noqa: E402

pins.activate()
from dream_core.ledger import release_source_hash  # noqa: E402
from guard import decide as D, studies as ST  # noqa: E402
import ig_decide  # noqa: E402
import ig_evaluate  # noqa: E402

SOURCES = {"V1.24": Path((_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Code/DREAM-project-1.24.0-clarified-keep-confirm-20261111")),
           "V1.22": Path((_os.path.expanduser(_os.environ.get("DREAM_HOME", "~/DREAM")) + "/Code/DREAM-project-1.22.0-keepid-confirm-20261110"))}
SECTION_DIRS = {"data": "data", "config": "config", "design": "design", "phase0": "phase0"}


def sha(p):
    return pins.sha256_file(p)


def verify_frozen(study):
    hub = ST.STUDIES[study]["hub"]
    fz = json.loads((hub / "config" / "FROZEN-PROTOCOL.json").read_text())
    out = {"frozen_protocol_sha256": sha(hub / "config" / "FROZEN-PROTOCOL.json"),
           "source_dir": fz["source_dir"], "frozen_source_sha256": fz["source_sha256"],
           "recomputed_source_sha256": release_source_hash(SOURCES[study]), "files": {}, "problems": []}
    if Path(fz["source_dir"]).resolve() != SOURCES[study].resolve():
        out["problems"].append("frozen source_dir differs from the expected tree")
    if out["frozen_source_sha256"] != out["recomputed_source_sha256"]:
        out["problems"].append("frozen source hash does not match the source tree")
    for section, sub in SECTION_DIRS.items():
        for rel, want in (fz.get(section) or {}).items():
            if not isinstance(want, str):
                continue
            p = hub / sub / rel
            got = sha(p) if p.exists() else None
            out["files"][f"{sub}/{rel}"] = {"frozen": want, "now": got}
            if got != want:
                out["problems"].append(f"{sub}/{rel}: hash differs from frozen manifest")
    # Declared membership: re-derive the pinned digests from the frozen stage-main.json "select" list (hash-checked
    # above via the config section) and require the schedule and public targets to equal it exactly.
    spec = ST.STUDIES[study]
    select = json.loads((hub / "config" / "stage-main.json").read_text())["select"]
    sched = [json.loads(x)["call_id"] for x in (hub / "data" / "main-calls.jsonl").read_text().splitlines() if x.strip()]
    targets = [json.loads(x)["target"] for x in (hub / "data" / "public" / "main-targets.jsonl").read_text().splitlines()
               if x.strip()]
    out["membership"] = {"frozen_select_calls": len(select), "frozen_select_sha256": ST.id_digest(select),
                         "pinned_calls_sha256": spec["calls_sha256"], "schedule_sha256": ST.id_digest(sched),
                         "targets_from_select_sha256": ST.id_digest({ST.target_of(c) for c in select}),
                         "pinned_targets_sha256": spec["targets_sha256"], "public_targets_sha256": ST.id_digest(targets)}
    if "config/stage-main.json" not in out["files"]:
        out["problems"].append("stage-main.json is not covered by the frozen manifest")
    if len(select) != len(set(select)) or len(sched) != len(set(sched)):
        out["problems"].append("duplicate call IDs in the frozen select list or schedule")
    mem = out["membership"]
    if not (mem["frozen_select_sha256"] == mem["pinned_calls_sha256"] == mem["schedule_sha256"]):
        out["problems"].append("frozen select list, pinned call digest and schedule disagree")
    if not (mem["targets_from_select_sha256"] == mem["pinned_targets_sha256"] == mem["public_targets_sha256"]):
        out["problems"].append("frozen select targets, pinned target digest and public targets disagree")
    for rel in ("src/tempo/refres.py", "src/tempo/factored.py"):
        h = sha(SOURCES[study] / rel)
        if h != pins.DECISION_PINS[rel]:
            out["problems"].append(f"{study} {rel} differs from the pinned decision dependency")
    out["ok"] = not out["problems"]
    return out


def tree_hash(d):
    rows = [[p.name, sha(p)] for p in sorted(Path(d).glob("*.json"))]
    return {"files": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}


def input_manifest():
    m = {"disclosure": ("Retrospective replay of already-completed and already-inspected panels. Before the original "
                        "IGUARD-v0.1 utility/plan commit (a516c61) and its formal replay, a development smoke of the "
                        "decision stage alone was run into a scratch directory (disposition counts only: V1.24 pass "
                        "2289 / compile_rejected 11 / identity_mismatch 4; V1.22 pass 2160 / compile_rejected 76 / "
                        "identity_mismatch 4). The evaluator had not been run at that point. The decision rule is the "
                        "one fixed in NEXT-STEP-PLAN.md and was not changed after that smoke. The original replay hub "
                        "(commit a516c61, report text regenerated at c3af115) and any later hardening reruns are "
                        "separate historical records; this manifest belongs only to the hub that contains it."),
         "studies": {}}
    for study, spec in ST.STUDIES.items():
        hub = spec["hub"]
        m["studies"][study] = {
            "hub": str(hub), "expected": {k: v for k, v in spec.items() if k != "hub"},
            "decision_inputs": {"data/public/main-targets.jsonl": sha(hub / "data/public/main-targets.jsonl"),
                                "data/main-calls.jsonl": sha(hub / "data/main-calls.jsonl"),
                                "stages/main/calls/*.json": tree_hash(hub / "stages/main/calls")},
            "evaluator_only_inputs": {"data/hidden/main-cases.jsonl": sha(hub / "data/hidden/main-cases.jsonl"),
                                      "analysis/confirm/scored.jsonl": sha(hub / "analysis/confirm/scored.jsonl")},
            "smoke_records_excluded_from_outcomes": True,
            "frozen_manifest_check": verify_frozen(study)}
    return m


def plan(commit):
    return {
        "rule": D.RULE, "status": "COMMITTED BEFORE REPLAY", "utility_commit": commit,
        "utility_source_sha256": ig_decide.source_hash(),
        "plan_documents": "<private-notes>/Publication/Temporal-pilot-follow-up-2026-11-05/"
                          "identity-guard-next-step-2026-11-11/{NEXT-STEP-PLAN,CLAUDE-IMPLEMENTATION-HANDOFF,"
                          "ACCEPTANCE-CHECKLIST}.md",
        "decision_interface": ["prefix", "target_text", "registry", "registry_order", "raw"],
        "decision_rule": [
            "refres.detect + refres.resolve_det (unchanged) on the ORIGINAL target and prefix for every condition",
            "non-resolve routes (literal-only bypass, multiple descriptions, no entity) and unresolved -> abstain",
            "factored.compile_reply (unchanged, public registry); compile failure stays rejected with its code",
            "compiled assertion field set must be nonempty and equal {resolved field}; else identity_mismatch",
            "guard_pass only for disposition 'pass'; final_accepted = original_accepted AND guard_pass"],
        "evaluation": ["evaluator runs only after SEAL; verifies sealed hash",
                       "rescore every call with tempo.kidconfscore.score_record (pinned) and require agreement with "
                       "the saved scored.jsonl on " + ", ".join(ig_evaluate.COMPARED),
                       "usable_exact = original_exact AND guard_pass; rejection cannot create a rescue"],
        "known_fixtures_evaluator_only": ig_evaluate.KNOWN,
        "known_correction_failures_evaluator_only": ig_evaluate.KNOWN_CORRECTION_FAILURES,
        "readiness_criteria": [
            "coverage: 2304 V1.24 and 2240 V1.22 main responses, exact membership, no problems",
            "preservation: all before/after hashes of both hubs and both frozen source trees unchanged",
            "isolation: decision stage public-only; poisoning and no-hidden tests pass",
            "controls: supported matches pass; refusal controls abstain",
            "all seven known accepted wrong bindings blocked",
            "no previously exact output in either panel newly blocked",
            "acceptance never expands"],
        "cap_seconds": 1800,
        "not_in_scope": ["model calls", "prompt variants", "live acceptance-policy change", "baseline adoption",
                         "qualification", "statistical tests", "population claims"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--commit", required=True)
    a = ap.parse_args()
    hub = Path(a.hub)
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "PLAN.json").write_text(json.dumps(plan(a.commit), indent=1) + "\n")
    (hub / "DEPENDENCIES.json").write_text(json.dumps({"pinned_root": str(pins.PINNED_ROOT),
                                                       "decision_pins": pins.DECISION_PINS,
                                                       "all_imported_package_files": pins.dependency_hashes()},
                                                      indent=1) + "\n")
    m = input_manifest()
    (hub / "INPUT-MANIFEST.json").write_text(json.dumps(m, indent=1) + "\n")
    ok = all(s["frozen_manifest_check"]["ok"] for s in m["studies"].values())
    print(json.dumps({s: v["frozen_manifest_check"]["problems"][:5] for s, v in m["studies"].items()}))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
