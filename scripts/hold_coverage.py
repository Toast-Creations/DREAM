"""V1.19.0 semantic-coverage check (no model): every scored source constraint is deliberately changed or dropped in
the canonical FACT-v1 reply of every committed target, and the relevant check must fail. Also records whether the
restricted replay detects each mutation and whether perfect canonical extractions carry the compilation-loss flag.
Usage: hold_coverage.py --hub HUB --set SET [--out DIR]"""
import argparse
import collections
import copy
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA, holdeval as HE, holdout as HO


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def mutations(o, case, w):
    k = case["records"][-1]["kind"]
    out = {"rid": lambda x: x.update(rid="r99"), "received_at": lambda x: x.update(received_at=x["received_at"] + 1),
           "status": lambda x: x.update(status="provisional")}
    other = next(f for f in HO.registry(w, case) if f.endswith(".on_hand") and f != case["field"])
    if k == "change":
        out.update({"event.field": lambda x: [e.update(field=other) for e in x["events"]] + [s.update(field=other) for s in x["states"]],
                    "event.at": lambda x: [e.update(at=e["at"] + 1) for e in x["events"]] + [s.update(at=s["at"] + 1) for s in x["states"]],
                    "event.to": lambda x: ([e.update(to="no" if e["to"] == "yes" else "yes") for e in x["events"]], x.update(states=[])),
                    "event.dropped(state only)": lambda x: x.update(events=[]),
                    "extra.revision": lambda x: x["revisions"].append({"target": "r01", "field": case["field"], "value": "yes",
                                                                      "valid_from": 1, "valid_to": None})})
        if case["prior_stated"]:
            out["event.from(stated)->null"] = lambda x: [e.update({"from": None}) for e in x["events"]]
        out["event.from->wrong"] = lambda x: [e.update({"from": e["to"]}) for e in x["events"]]
    elif k == "observation":
        out.update({"state.field": lambda x: [s.update(field=other) for s in x["states"]],
                    "state.at": lambda x: [s.update(at=s["at"] + 1) for s in x["states"]],
                    "state.value": lambda x: [s.update(value="no") for s in x["states"]],
                    "extra.event": lambda x: x["events"].append({"field": case["field"], "at": x["states"][0]["at"], "from": None, "to": "yes"})})
    else:
        out.update({"revision.target": lambda x: [r.update(target="r01" if r["target"] != "r01" else "r02") for r in x["revisions"]],
                    "revision.field": lambda x: [r.update(field=other) for r in x["revisions"]],
                    "revision.value": lambda x: [r.update(value="yes") for r in x["revisions"]],
                    "revision.valid_from": lambda x: [r.update(valid_from=r["valid_from"] + 1) for r in x["revisions"]],
                    "revision.valid_to": lambda x: [r.update(valid_to=None if r["valid_to"] is not None else r["valid_from"] + 1) for r in x["revisions"]],
                    "revision->event": lambda x: x.update(events=[{"field": case["field"], "at": x["received_at"], "from": None, "to": "no"}], revisions=[])})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0" / a.set
    out.mkdir(parents=True, exist_ok=True)
    cases = load(hub / "data" / "hidden" / f"{a.set}-cases.jsonl")
    targets = {t["target"]: t for t in load(hub / "data" / "public" / f"{a.set}-targets.jsonl")}
    worlds = {}
    res = collections.defaultdict(lambda: collections.Counter())
    canon = collections.Counter()
    fails = []
    for c in cases:
        k = (c["world_seed"], c["pool"])
        if k not in worlds:
            worlds[k] = HO._world(*k)[0]
        w, case = worlds[k], c["case"]
        reg = targets[c["target"]]["registry"]
        base = dict(FA.canonical_factored(HO.public(case)[-1]), evidence=case["text"][-25:])
        s0 = HE.score(json.dumps(base), case, w, reg)[0]
        canon["exact_extraction"] += s0["exact_extraction"]
        canon["exact_end_to_end"] += s0["exact_end_to_end"]
        canon["compilation_loss"] += s0["compilation_loss"]
        canon["finite_targets"] += bool(case["finite"])
        canon["n"] += 1
        if s0["compilation_loss"] != bool(case["finite"]):
            fails.append(f"{c['target']}: canonical compilation-loss flag {s0['compilation_loss']} vs finite {case['finite']}")
        for name, mut in mutations(base, case, w).items():
            o = copy.deepcopy(base)
            mut(o)
            s = HE.score(json.dumps(o), case, w, reg)[0]
            key = f"{case['records'][-1]['kind']}|{name}" + ("|finite" if case["finite"] else "")
            res[key]["n"] += 1
            res[key]["extraction_check_fails"] += not s["exact_extraction"]
            res[key]["replay_detects"] += not s["replay_ok"]
            if s["exact_extraction"]:
                fails.append(f"{c['target']} {name}: mutation not detected by the extraction check")
    summary = {"canonical": dict(canon), "mutations": {k: dict(v) for k, v in sorted(res.items())},
               "undetected": fails[:50], "pass": not fails}
    (out / "COVERAGE.json").write_text(json.dumps(summary, indent=1) + "\n")
    print("PASS" if not fails else f"FAIL {len(fails)}: {fails[:3]}")


if __name__ == "__main__":
    main()
