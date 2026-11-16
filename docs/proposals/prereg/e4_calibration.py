#!/usr/bin/env python3
"""E4 human-calibration gate for E1 (PREREGISTRATION_E1_E5.md, Section 9.1, item 2). No model calls.

  e4_calibration.py select --pilot-pairs PILOT_PAIRS.jsonl
  e4_calibration.py packet --pilot-pairs PILOT_PAIRS.jsonl --units qwen3-8b=DIR --units mistral-7b=DIR --out DIR
  e4_calibration.py record --key DIR/KEY-SEALED.json --sheets SHEET1.csv [SHEET2.csv ...] --out e4_record.json

select : prints the 24 registered pilot pairs (8 practical, 8 analogy, 8 artistic; two per family x model x
         baseline cell, one per pilot task), chosen deterministically by hash (analyze_e1_pairwise.e4_selection).
packet : writes a condition-masked reviewer packet (PACKET.md), a blank rating sheet (SHEET-TEMPLATE.csv) and
         a sealed key (KEY-SEALED.json, A/B -> pilot candidate; never shown to reviewers). Arm names, model names
         and pairwise-v1 verdicts are not in the packet. A/B sides are set by hash, independently of the pilot's
         presentation orders.
record : combines one completed sheet per reviewer with the key into the E4 record read by
         analyze_e1_pairwise.py. `completed` is true only if every reviewer rated every item.

Gate (recomputed by analyze_e1_pairwise.py): directional agreement between the human verdict (majority of
reviewers) and the counterbalanced pairwise-v1 pilot verdict >= 75% on pairs that are non-tie for both, and 0
practical pairs in which the human-preferred answer is the one a majority of reviewers flagged as relying on a
physically impossible mechanism (the other answer not flagged).
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_e1_pairwise as an  # noqa: E402

SIDE_SALT = "e4-human-calibration-v1|sides"
INSTRUCTIONS = """# DREAM E4 human-calibration packet

You will compare 24 pairs of answers. Each pair answers the same creative task. The answers were written by
language models under different settings; you are not told which setting produced which answer, and nothing
about the order or the letters A and B tells you anything.

For each item, fill in one row of the rating sheet:

- **useful_originality**: `A`, `B` or `TIE`. Which answer contains more ideas that are BOTH original AND
  genuinely usable or coherent? Novelty that only works by impossible or incoherent means does not count.
  Familiar ideas that work do count, but less than ideas that are both non-obvious and work. If one answer is
  original but unworkable and the other is plain but workable, prefer the one whose ideas would actually
  deliver value, unless the plain answer barely addresses the task. Judge the answers as wholes; length,
  formatting and confident tone are not evidence of quality. Use `TIE` only if you genuinely cannot separate them.
- **impossible_A**, **impossible_B**: `yes` or `no`. Does the answer rely, for at least one of its ideas, on a
  physically impossible mechanism, pseudoscience, or folklore treated as fact (luck, energy, spirits, memory in
  inert objects)? Answer this for every item; it matters most for the practical tasks. Magic in a story task
  is allowed and is not "impossible" in this sense.
- **note** (optional): anything that made the item hard to judge.

Work alone, do not look anything up about the study, and do not discuss items with other reviewers until
everyone has submitted.
"""


def pilot(path):
    return {r["pair_id"]: r for r in an.load_jsonl(path) if r.get("complete")}


def cmd_select(a):
    recs = pilot(a.pilot_pairs)
    for pid in an.e4_selection(list(recs.values())):
        print(pid, recs[pid]["meta"]["family"])


def final_text(u):
    v = next((c for c in u["calls"] if c["stage"] == "final"), None)
    return v["output"]["text"] if v and v.get("status") == "completed" and v.get("output") else None


def cmd_packet(a):
    if hashlib.sha256(Path(a.pilot_pairs).read_bytes()).hexdigest() != an.E4_PILOT_PAIRS_SHA256:
        raise SystemExit("--pilot-pairs is not the registered pilot pairs file")
    recs = pilot(a.pilot_pairs)
    units = {}
    for spec in a.units:
        model, d = spec.split("=", 1)
        for p in Path(d).glob("*.json"):
            u = json.loads(p.read_text())
            units[(model, u["unit_id"])] = u
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    md, key = [INSTRUCTIONS], {"gate": an.E4_GATE_ID, "pilot_pairs_sha256": an.E4_PILOT_PAIRS_SHA256, "items": []}
    for i, pid in enumerate(an.e4_selection(list(recs.values())), 1):
        m = recs[pid]["meta"]
        s, b = units[(m["model"], m["steer_id"])], units[(m["model"], m["baseline_id"])]
        ids = [m["steer_id"], m["baseline_id"]]
        if int(an.hrank(SIDE_SALT, pid), 16) % 2:
            ids.reverse()
        text = {m["steer_id"]: final_text(s), m["baseline_id"]: final_text(b)}
        item = f"E4-{i:02d}"
        md += [f"\n---\n\n## {item}\n", f"**Task:** {s['task']['prompt']}\n",
               "### Answer A\n", text[ids[0]], "\n### Answer B\n", text[ids[1]], ""]
        key["items"].append({"item": item, "pair_id": pid, "A_B": {"A": ids[0], "B": ids[1]}})
    (out / "PACKET.md").write_text("\n".join(md) + "\n")
    with open(out / "SHEET-TEMPLATE.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["reviewer", "item", "useful_originality", "impossible_A", "impossible_B", "note"])
        for it in key["items"]:
            w.writerow(["", it["item"], "", "", "", ""])
    (out / "KEY-SEALED.json").write_text(json.dumps(key, indent=1) + "\n")
    print(f"packet: {len(key['items'])} items in {out}; give reviewers PACKET.md and SHEET-TEMPLATE.csv only")


def cmd_record(a):
    key = json.loads(Path(a.key).read_text())
    yn = {"yes": True, "no": False}
    reviews, reviewers, complete = {it["item"]: [] for it in key["items"]}, [], True
    for sheet in a.sheets:
        rows = list(csv.DictReader(open(sheet, newline="")))
        names = {r["reviewer"].strip() for r in rows}
        if len(names) != 1 or "" in names:
            raise SystemExit(f"{sheet}: every row needs the same non-empty reviewer id")
        name = names.pop()
        if name in reviewers:
            raise SystemExit(f"{sheet}: reviewer {name} appears twice")
        reviewers.append(name)
        seen = set()
        for r in rows:
            v = r["useful_originality"].strip().upper()
            ia, ib = r["impossible_A"].strip().lower(), r["impossible_B"].strip().lower()
            if r["item"] not in reviews or r["item"] in seen:
                raise SystemExit(f"{sheet}: unknown or repeated item {r['item']}")
            if v not in an.E4_VERDICTS or ia not in yn or ib not in yn:
                complete = False
                continue
            seen.add(r["item"])
            reviews[r["item"]].append({"reviewer": name, "useful_originality": v,
                                       "impossible_mechanism": {"A": yn[ia], "B": yn[ib]},
                                       "note": r.get("note", "")})
        complete &= seen == set(reviews)
    rec = {"gate": an.E4_GATE_ID, "completed": complete, "pilot_pairs_sha256": key["pilot_pairs_sha256"],
           "reviewers": reviewers,
           "rows": [{"pair_id": it["pair_id"], "item": it["item"], "A_B": it["A_B"], "reviews": reviews[it["item"]]}
                    for it in key["items"]]}
    Path(a.out).write_text(json.dumps(rec, indent=1) + "\n")
    print(f"E4 record: {len(reviewers)} reviewer(s), completed={complete} -> {a.out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select"); s.add_argument("--pilot-pairs", required=True)
    p = sub.add_parser("packet"); p.add_argument("--pilot-pairs", required=True)
    p.add_argument("--units", action="append", required=True); p.add_argument("--out", required=True)
    r = sub.add_parser("record"); r.add_argument("--key", required=True)
    r.add_argument("--sheets", nargs="+", required=True); r.add_argument("--out", required=True)
    a = ap.parse_args()
    {"select": cmd_select, "packet": cmd_packet, "record": cmd_record}[a.cmd](a)


if __name__ == "__main__":
    main()
