"""V1.20.0 panel for REFRES-v1 (fresh instances of the inspected 1.19 dependency families; OPEN correction intervals
only, so the canonical mapper loss is zero by construction). No model.

Main: 48 groups (F3 historical 16, F4 measurement 16, F1 two-hop 8, F2 slot join 8), each family split equally
between immediate and delayed target reception (8 strata: 8/8/4/4 groups per reception). Within a stratum the four
(b0, b1) settings (record order, stated/unstated prior) cycle and repeat on fresh seeds; b2 = 0 (open intervals).
Each group: 4 acts x 2 histories (tempo.holdout.build_group, unchanged) -> 384 targets.
Controls (32 targets, excluded from the primary):
  16 refusal controls: 8 declared types x 2 independent constructions:
     measure_missing, measure_tie, measure_wrong_predicate, measure_multiple_parts,
     hist_missing_support, hist_contradictory_tie, hist_unsupported_report, hist_nonunique_occupant
  8 bare genuine corrections with an explicit entity; 8 explicit-name targets (2 per act).
Smoke (disjoint pools): one main-style group per family (32 targets) + 4 refusal + 4 unchanged-form controls.
Public envelopes {record_id, raw_text} are the exact prefix lines shown in the extraction prompt."""
import random

from . import freshgen as FG, generate as G, history as Hm, holdout as HO, prose, worlds
from .worlds import EMPTY, NO, YES

POOLS = {"ref": "bcdfhjk", "refctl": "glmnprt", "refsmoke": "dfgkmsv", "refsmokectl": "bhjlnpz"}
FG.CONS.update(POOLS)
WEIGHTS = {"F3_historical_occupant": 16, "F4_measurement_order": 16, "F1_two_hop": 8, "F2_slot_join": 8}
REFUSAL_TYPES = ("measure_missing", "measure_tie", "measure_wrong_predicate", "measure_multiple_parts",
                 "hist_missing_support", "hist_contradictory_tie", "hist_unsupported_report", "hist_nonunique_occupant")
EXPECTED_REFUSAL = {"measure_missing": "missing_record", "measure_tie": "tie", "measure_wrong_predicate": "wrong_predicate",
                    "measure_multiple_parts": "multiple_parts", "hist_missing_support": "missing_support",
                    "hist_contradictory_tie": "contradictory_tie", "hist_unsupported_report": "unsupported_relevant_report",
                    "hist_nonunique_occupant": "nonunique_occupant"}


def main_plan(smoke=False):
    out = []
    fams = {f: (1 if smoke else n) for f, n in WEIGHTS.items()}
    for fam, n in fams.items():
        for i in range(n):
            rec = HO.RECEPTION[i % 2]
            k = i // 2
            out.append((fam, rec, (k & 1, (k >> 1) & 1, 0)))
    return out


def envelopes(w, case, rseed):
    recs = [Hm.public(r) for r in case["records"][:-1]]
    line = lambda r: case["custom"].get(r["rid"]) or prose.prose_line(w, r, rseed)
    return [{"record_id": r["rid"], "raw_text": line(r)} for r in recs]


# ---------------------------------------------------------------------------------------------- controls

def _world(seed, pool):
    rng = random.Random(seed)
    return worlds.make_world("assembly", rng, FG.Names(pool, rng), "stock"), rng


def _obs(f, v, t, status="verified", key=None):
    return G.R("observation", t, t, {"field": f, "value": v}, status=status, key=key)


def refusal_control(kind, seed, pool):
    """One target whose recognized description is unsupported or non-unique. Returns a case-like dict (records with
    custom texts, target text, act) and the world; no unique gold binding exists."""
    w, rng = _world(seed, pool)
    G_, D_, W_ = w.g, w.d, w.w
    fG, fD, fW, fT = f"{G_}.on_hand", f"{D_}.on_hand", f"{W_}.on_hand", w.slot_f
    recs, desc = [], None
    if kind.startswith("measure"):
        a = _obs(fG, NO, 3, key="a")
        b = _obs(fD, NO, 2, key="b")
        b["received_at"] = 5
        a["received_at"] = 4
        if kind == "measure_tie":
            b["event_at"] = 3
            recs = [a, b]
        elif kind == "measure_missing":
            recs = [a, b]
        elif kind == "measure_wrong_predicate":
            b = G.R("observation", 2, 5, {"field": fT, "value": EMPTY}, key="b")
            recs = [a, b]
        else:
            b = G.R("initial", 2, 5, {"assign": {fD: NO, fW: YES}}, key="b")
            recs = [a, b]
    else:
        if kind == "hist_missing_support":
            recs = [_obs(fG, NO, 3, key="a"), G.R("change", 6, 6, {"field": fT, "from": EMPTY, "to": G_}, key="fit")]
            desc_t = 4
        elif kind == "hist_contradictory_tie":
            recs = [G.R("observation", 3, 3, {"field": fT, "value": G_}, key="o1"), _obs(fG, NO, 4, key="a"),
                    G.R("observation", 3, 5, {"field": fT, "value": W_}, key="o2")]
            desc_t = 4
        elif kind == "hist_unsupported_report":
            recs = [G.R("change", 2, 2, {"field": fT, "from": EMPTY, "to": G_}, key="fit"), _obs(fG, NO, 3, key="a"),
                    G.R("observation", 4, 4, {"field": fT, "value": W_}, status="provisional", key="prov")]
            desc_t = 5
        else:
            recs = [G.R("uncertain_change", 2, 2, {"field": fT, "from": EMPTY, "options": [G_, W_]}, key="unc"),
                    _obs(fG, NO, 3, key="a")]
            desc_t = 4
    recs = G.finalize(recs + [G.R("change", 9, 9, {"field": fG, "from": NO, "to": YES})])
    byk = {r["key"]: r for r in recs if r.get("key")}
    if kind.startswith("measure"):
        r2 = "r09" if kind == "measure_missing" else byk["b"]["rid"]
        desc = f"the part whose stock check, of {byk['a']['rid']} and {r2}, was measured earlier"
    else:
        desc = f"the part that slot {w.t} held at time {desc_t}"
    rseed = rng.randint(0, 10 ** 9)
    trid = recs[-1]["rid"]
    text = HO.target_text("arrival", desc, trid, 9, 9, False, None, random.Random(f"{rseed}|{trid}"))
    case = {"records": recs, "custom": {trid: text}, "text": text, "field": None, "selected": None, "act": "arrival",
            "prior_stated": False, "anchor": 3, "t_event": 9, "recv": 9, "finite": False, "desc": desc,
            "unaffected": None, "target_rid": trid, "control": kind, "expected": EXPECTED_REFUSAL[kind]}
    return w, case, rseed
