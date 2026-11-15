"""V1.20.0 reference resolution before frozen FACT-v1 extraction (REFRES-v1). Public text only.

Public input allowlist (the only thing the detector, both resolvers and the rewriter receive):
  PublicInput(prefix=[{"record_id", "raw_text"}...], target=<original target raw text>, registry=<public registry>)
No canonical record, hidden selected field/entity, generator role, renderer seed, actual state or future information.

Detector (declared reference grammar; exactly the inspected 1.19 constructions):
  one_hop     "the part whose stock was checked in rK"
  two_hop     "the part described in rL"
  slot_join   "the part that rK found installed in slot S"
  historical  "the part that slot S held at time t"
  measure     "the part whose stock check, of rI and rJ, was measured earlier|later"
  0 descriptions and a literal "part <Name>" -> bypass (all arms use the BASE prompt); >1 description -> pending;
  0 descriptions and no literal part -> pending.

Raw-record grammar: ONLY complete declared report forms are recognized (the frozen prose templates for observations,
events and uncertain changes, corrections, plus the HOLD-v1 link wording). Anything else is "unrecognized". Mentions
of parts/slots are read from the whole raw text first, so a record with an unknown header or body still counts as
relevant evidence. Duplicate envelope IDs or a header rid different from its envelope ID -> refuse.

Deterministic resolver (RES-DET), declared rules (Codex reviews 01-03):
  stock check   a complete stock-observation form about exactly one named part (an event that ends "now on hand" is
                NOT a stock check); status does not matter for identity (a provisional report may identify its named
                part); a record revised by a later correction -> refuse; a link record is resolved recursively
                (one-hop only; depth <= 2)
  one_hop       rK must be a stock check -> its part
  two_hop       rL must be a link record; its antecedent rK must be a plain stock check -> its part
  slot_join     rK must be a complete slot observation of S with exactly one part, and S's verified timeline must be
                consistent -> that part
  historical    S's timeline: verified slot observations are CONSTRAINTS and events are transitions whose stated
                priors are checked (fit: prior empty; pull: prior = the pulled part; swap: prior = the swapped-out part).
                Values change only at recorded events. Any inconsistency (observation vs current value, prior
                mismatch, same-time disagreement) -> refuse. Any provisional, correction or unrecognized record that
                mentions S -> refuse (unsupported relevant report). An uncertain change on S -> refuse (non-unique).
                The value at t comes from the last consistent item at or before t; none -> refuse (missing support);
                empty -> refuse (presupposition). Never "the latest occupant overall".
  measure       rI and rJ must both be plain stock checks of different single parts with measured times; equal
                times -> refuse (tie). Compares measured times, never positions or reception order.
Rewrite: replace exactly the detected noun phrase with "part <Name>" (Name from the selected stock field); every
other byte is kept; the ledger records offsets, both texts and their hashes.

Model resolver (RES-MODEL): one narrow call, fixed instruction, no worked examples; reply {"field": <registered
stock field> | null, "records": [<prefix record IDs>]}; 128 output tokens. Invalid JSON / unknown field / empty or
unknown record IDs / null -> pending (no extraction call, no fallback to BASE). A legal wrong field is rewritten.
"""
import hashlib
import json
import re
from dataclasses import dataclass

from . import score as S

RULE = "REFRES-v1"
NAME = r"[A-Z][a-z]+"
RID = r"r\d\d"
DESC = [
    ("measure", re.compile(rf"the part whose stock check, of ({RID}) and ({RID}), was measured (earlier|later)")),
    ("one_hop", re.compile(rf"the part whose stock was checked in ({RID})")),
    ("two_hop", re.compile(rf"the part described in ({RID})")),
    ("slot_join", re.compile(rf"the part that ({RID}) found installed in slot ({NAME})")),
    ("historical", re.compile(rf"the part that slot ({NAME}) held at time (\d+)")),
]
LITERAL = re.compile(rf"\bpart ({NAME})\b")


@dataclass(frozen=True)
class PublicInput:
    prefix: tuple      # ((record_id, raw_text), ...)
    target: str
    registry: tuple    # registered field names, in order

    @staticmethod
    def make(prefix, target, registry):
        return PublicInput(tuple((p["record_id"], p["raw_text"]) for p in prefix), target, tuple(registry))


def stock_fields(pi):
    return [f for f in pi.registry if f.endswith(".on_hand")]


# ---------------------------------------------------------------------------------------------- detector

def detect(target):
    found = []
    for kind, rx in DESC:
        for m in rx.finditer(target):
            if not any(m.start() < e and s < m.end() for s, e, *_ in found):
                found.append((m.start(), m.end(), kind, m.groups()))
    if len(found) == 1:
        s, e, kind, g = found[0]
        return {"route": "resolve", "kind": kind, "span": [s, e], "text": target[s:e], "args": list(g)}
    if len(found) > 1:
        return {"route": "pending", "reason": "multiple_descriptions", "spans": [[s, e] for s, e, *_ in found]}
    if LITERAL.search(target):
        return {"route": "bypass", "reason": "literal_entity_no_description"}
    return {"route": "pending", "reason": "no_entity"}


# ---------------------------------------------------------------------------------------------- raw record parser
# Only COMPLETE declared report forms are recognized (frozen prose templates + HOLD-v1 link wording). A record
# matching none is "unrecognized"; an unrecognized, correction or provisional record that is relevant to a query is
# never ignored: the resolver refuses (review 01, items 1 and 4).

HEAD = [re.compile(rf"^Message ({RID}), received at time (\d+): "), re.compile(rf"^({RID}) \(came in at time (\d+)\): "),
        re.compile(rf"^At time (\d+) we received ({RID})\. ")]
F_STOCK = [re.compile(rf"^part ({NAME}) is (not )?on hand$"), re.compile(rf"^you (do not )?have part ({NAME}) on hand$")]
F_SLOT = [re.compile(rf"^slot ({NAME}) holds part ({NAME})$"), re.compile(rf"^part ({NAME}) is installed in slot ({NAME})$"),
          re.compile(rf"^slot ({NAME}) is empty$"), re.compile(rf"^nothing is installed in slot ({NAME})$")]
OBS = [(re.compile(r"^a confirmed check shows that at time (\d+) (.+)\.$"), "verified"),
       (re.compile(r"^someone verified that, as of time (\d+), (.+)\.$"), "verified"),
       (re.compile(r"^checked and confirmed \(verified\): at time (\d+), (.+)\.$"), "verified"),
       (re.compile(r"^an early, unconfirmed \(provisional\) report says that at time (\d+) (.+)\. It has not been verified yet\.$"), "provisional"),
       (re.compile(r"^a provisional report, not yet verified, states that as of time (\d+) (.+)\.$"), "provisional")]
LINK = [(re.compile(rf"^it is verified that at time (\d+) the part whose stock was checked in ({RID}) is (not )?on hand\.$"), "verified"),
        (re.compile(rf"^a provisional report, not yet verified, states that at time (\d+) the part whose stock was checked in ({RID}) is (not )?on hand\.$"), "provisional")]
EVT = [re.compile(r"^confirmed \(verified\) event: at time (\d+), (.+)\.$"), re.compile(r"^it is verified that at time (\d+) (.+)\.$")]
CHG_STOCK = [re.compile(rf"^part ({NAME}) was delivered to you, so it is now on hand$"),
             re.compile(rf"^part ({NAME}) arrived for you and is now on hand$"),
             re.compile(rf"^another team took part ({NAME}) away, so it is no longer on hand$"),
             re.compile(rf"^part ({NAME}) was taken by another team and is no longer on hand$")]
CHG_FIT = re.compile(rf"^another technician fitted part ({NAME}) into slot ({NAME}), using their own stock$")
CHG_PULL = re.compile(rf"^another technician pulled part ({NAME}) out of slot ({NAME}) and took it away, leaving the slot empty$")
CHG_SWAP = re.compile(rf"^another technician swapped part ({NAME}) in slot ({NAME}) for part ({NAME}), taking ({NAME}) away$")
CHG_CRATE = [re.compile(rf"^another worker carried crate ({NAME}) from ({NAME}) over to ({NAME})$"),
             re.compile(rf"^crate ({NAME}) was moved by another worker from ({NAME}) to ({NAME})$")]
UNC = re.compile(r"^verified event at time (\d+): (.+)\.$")
UNC_SLOT = re.compile(rf"^another technician worked on slot ({NAME}) and the result was not written down; afterwards the slot is either (.+) or (.+)$")
CORR = re.compile(rf"^(?:this is a verified correction of ({RID})\.|verified correction to ({RID}):) ")


def _facts(text):
    pieces = re.split(r", | and ", text)
    out = []
    for pc in pieces:
        for k, rx in enumerate(F_STOCK):
            m = rx.match(pc)
            if m:
                out.append(("stock", m.group(1), "no" if m.group(2) else "yes") if k == 0 else
                           ("stock", m.group(2), "no" if m.group(1) else "yes"))
                break
        else:
            for k, rx in enumerate(F_SLOT):
                m = rx.match(pc)
                if m:
                    out.append(("slot", m.group(1), m.group(2)) if k == 0 else ("slot", m.group(2), m.group(1)) if k == 1
                               else ("slot", m.group(1), None))
                    break
            else:
                return None
    return out


def parse_record(rid, raw):
    out = {"rid": rid, "raw": raw, "head_rid": None, "recv": None, "kind": "unrecognized", "status": "verified",
           "time": None, "facts": [], "slot_event": None, "link": None, "correction_of": None, "uncertain_slot": None}
    # mentions are taken from the whole raw text first, so an unrecognized header can never hide relevant evidence
    out["mentions"] = sorted(set(re.findall(rf"(?:[Pp]art|[Ss]lot) ({NAME})", raw)))
    for i, rx in enumerate(HEAD):
        m = rx.match(raw)
        if m:
            out["head_rid"], out["recv"] = (m.group(1), int(m.group(2))) if i < 2 else (m.group(2), int(m.group(1)))
            body = raw[m.end():]
            break
    else:
        return out
    body = body[:1].lower() + body[1:]
    m = CORR.match(body)
    if m:
        return dict(out, kind="correction", correction_of=m.group(1) or m.group(2))
    for rx, st in LINK:
        m = rx.match(body)
        if m:
            return dict(out, kind="link", status=st, time=int(m.group(1)),
                        link={"ref": m.group(2), "value": "no" if m.group(3) else "yes"})
    for rx, st in OBS:
        m = rx.match(body)
        if m:
            f = _facts(m.group(2))
            if f is None:
                return out
            return dict(out, kind="observation", status=st, time=int(m.group(1)), facts=f)
    for rx in EVT:
        m = rx.match(body)
        if m:
            t, c = int(m.group(1)), m.group(2)
            if any(x.match(c) for x in CHG_STOCK):
                return dict(out, kind="stock_event", time=t)
            if any(x.match(c) for x in CHG_CRATE):
                return dict(out, kind="crate_event", time=t)
            mf, mp, ms = CHG_FIT.match(c), CHG_PULL.match(c), CHG_SWAP.match(c)
            if mf:
                return dict(out, kind="slot_event", time=t, slot_event=(mf.group(2), None, mf.group(1)))
            if mp:
                return dict(out, kind="slot_event", time=t, slot_event=(mp.group(2), mp.group(1), None))
            if ms and ms.group(1) == ms.group(4):
                return dict(out, kind="slot_event", time=t, slot_event=(ms.group(2), ms.group(1), ms.group(3)))
            return out
    m = UNC.match(body)
    if m:
        mu = UNC_SLOT.match(m.group(2))
        if mu:
            return dict(out, kind="uncertain_slot", time=int(m.group(1)), uncertain_slot=mu.group(1))
        return dict(out, kind="uncertain_other", time=int(m.group(1)))
    return out


def _records(pi):
    ids = [rid for rid, _ in pi.prefix]
    if len(set(ids)) != len(ids):
        return None, "duplicate_record_ids"
    recs = {rid: parse_record(rid, raw) for rid, raw in pi.prefix}
    for rid, r in recs.items():
        if r["head_rid"] is not None and r["head_rid"] != rid:
            return None, "record_id_mismatch"
    return recs, None


def _revised(recs, rid):
    return any(r["kind"] == "correction" and r["correction_of"] == rid for r in recs.values())


def _stock_part(recs, rid, depth=0, allow_link=True):
    """(part, None) or (None, reason) for 'the part whose stock was checked in rid' (a complete stock-observation form,
    one part, not revised; or a link record resolved recursively)."""
    r = recs.get(rid)
    if r is None:
        return None, "missing_record"
    if _revised(recs, rid):
        return None, "unsupported_relevant_report"
    if r["kind"] == "link" and allow_link:
        if depth >= 2:
            return None, "recursion_limit"
        return _stock_part(recs, r["link"]["ref"], depth + 1)
    if r["kind"] == "unrecognized":
        return None, "unsupported_relevant_report"
    if r["kind"] != "observation" or any(f[0] != "stock" for f in r["facts"]):
        return None, "wrong_predicate"
    parts = {f[1] for f in r["facts"]}
    if len(parts) != 1:
        return None, "multiple_parts"
    return next(iter(parts)), None


def _slot_timeline(recs, slot):
    """Verified items about the slot, consistency-checked under persistence (values change only at recorded events;
    observations are constraints; stated event priors must match). Returns (items, reason)."""
    items = []
    for r in recs.values():
        rel = slot in r.get("mentions", []) or (r["slot_event"] and r["slot_event"][0] == slot) or \
            any(f[0] == "slot" and f[1] == slot for f in r["facts"])
        if not rel:
            continue
        if r["kind"] in ("unrecognized", "correction") or r["status"] == "provisional":
            return None, "unsupported_relevant_report"
        if r["kind"] == "uncertain_slot" and r["uncertain_slot"] == slot:
            return None, "nonunique_occupant"
        if r["kind"] == "observation":
            vals = [f[2] for f in r["facts"] if f[0] == "slot" and f[1] == slot]
            if len(vals) > 1:
                return None, "contradictory_tie"
            if vals:
                items.append((r["time"], 1, "obs", vals[0], r["rid"]))
        elif r["kind"] == "slot_event" and r["slot_event"][0] == slot:
            _, prior, result = r["slot_event"]
            items.append((r["time"], 0, "evt", (prior, result), r["rid"]))
        elif r["kind"] not in ("observation", "slot_event", "stock_event", "crate_event", "link"):
            return None, "unsupported_relevant_report"
    items.sort()
    cur, known = None, False
    for i, (t, _, k, v, rid) in enumerate(items):
        same_t = [x for x in items if x[0] == t]
        if len(same_t) > 1:
            kinds = {x[2] for x in same_t}
            if kinds == {"obs"} and len({x[3] for x in same_t}) > 1:
                return None, "contradictory_tie"
            if "evt" in kinds and "obs" in kinds:
                return None, "contradictory_tie"
            if [x[2] for x in same_t].count("evt") > 1:
                return None, "contradictory_tie"
        if k == "obs":
            if known and cur != v:
                return None, "inconsistent_evidence"
            cur, known = v, True
        else:
            prior, result = v
            if known and cur != prior:
                return None, "prior_mismatch"
            cur, known = result, True
    return items, None


def resolve_det(pi, det):
    """Deterministic resolver. Returns {"field": ... or None, "reason", "trace"}."""
    recs, bad = _records(pi)
    kind, a = det["kind"], det["args"]
    trace = {"kind": kind, "args": a}
    if recs is None:
        return {"field": None, "reason": bad, "trace": trace}
    part, why = None, None
    if kind == "one_hop":
        part, why = _stock_part(recs, a[0])
    elif kind == "two_hop":
        r = recs.get(a[0])
        if r is None:
            why = "missing_record"
        elif _revised(recs, a[0]):
            why = "unsupported_relevant_report"
        elif r["kind"] != "link":
            why = "wrong_predicate" if r["kind"] != "unrecognized" else "unsupported_relevant_report"
        else:
            part, why = _stock_part(recs, r["link"]["ref"], 1, allow_link=False)
            trace["link_ref"] = r["link"]["ref"]
    elif kind == "slot_join":
        r = recs.get(a[0])
        if r is None:
            why = "missing_record"
        elif _revised(recs, a[0]) or r["kind"] == "unrecognized":
            why = "unsupported_relevant_report"
        elif r["kind"] != "observation":
            why = "wrong_predicate"
        else:
            occ = [f[2] for f in r["facts"] if f[0] == "slot" and f[1] == a[1]]
            if len(occ) != 1:
                why = "wrong_predicate" if not occ else "multiple_parts"
            elif occ[0] is None:
                why = "presupposition_no_part"
            else:
                items, why = _slot_timeline(recs, a[1])
                part = occ[0] if why is None else None
    elif kind == "historical":
        slot, t = a[0], int(a[1])
        items, why = _slot_timeline(recs, slot)
        if why is None:
            upto = [x for x in items if x[0] <= t]
            if not upto:
                why = "missing_support"
            else:
                last = upto[-1]
                val = last[3] if last[2] == "obs" else last[3][1]
                trace["decisive"] = last[4]
                if val is None:
                    why = "presupposition_no_part"
                else:
                    part = val
    elif kind == "measure":
        ps = [_stock_part(recs, x, allow_link=False) for x in a[:2]]
        bad = next((w for _, w in ps if w), None)
        if bad:
            why = bad
        elif a[0] == a[1]:
            why = "wrong_predicate"
        else:
            tt = [recs[x]["time"] for x in a[:2]]
            if None in tt:
                why = "missing_time"
            elif tt[0] == tt[1]:
                why = "tie"
            elif ps[0][0] == ps[1][0]:
                why = "multiple_parts"
            else:
                earlier = 0 if tt[0] < tt[1] else 1
                part = ps[earlier if a[2] == "earlier" else 1 - earlier][0]
                trace["measured"] = dict(zip(a[:2], tt))
    field = f"{part}.on_hand" if part else None
    if field and field not in pi.registry:
        field, why = None, "unregistered_field"
    return {"field": field, "reason": why, "trace": trace}


# ---------------------------------------------------------------------------------------------- model resolver

def resolver_prompt(pi, det):
    """Built ONLY from PublicInput (prefix envelopes, target, registry) plus fixed instructions (review 01, item 5)."""
    lines = ["Records received before the new record (context only):"]
    lines += [raw for _, raw in pi.prefix] if pi.prefix else ["(none)"]
    lines += ["", "New record:", pi.target, "", "QUERY (reference resolution)",
              f"The new record refers to a part by a description instead of its name: \"{det['text']}\". Using only "
              "the records received before the new record, decide which registered part stock field that description "
              "refers to. If the description does not identify exactly one part, answer null.",
              "Registered part stock fields: " + ", ".join(json.dumps(f) for f in stock_fields(pi)),
              'Reply with only a JSON object: {"field": "<registered part stock field>" or null, "records": '
              '["<ID of each earlier record you used>", ...]}']
    return "\n".join(lines)


def parse_resolver(raw, pi):
    if raw is None:
        return {"field": None, "status": "invalid", "reason": "no_reply"}
    obj, err = S.parse_object(raw)
    if err is not None or not isinstance(obj, dict):
        return {"field": None, "status": "invalid", "reason": f"parse:{err}"}
    if "field" not in obj or "records" not in obj or not isinstance(obj["records"], list):
        return {"field": None, "status": "invalid", "reason": "missing_or_bad_keys"}
    f, rs = obj["field"], obj["records"]
    if f is None:
        return {"field": None, "status": "unresolved", "reason": "null", "records": rs}
    ids = {rid for rid, _ in pi.prefix}
    if not isinstance(f, str) or f not in stock_fields(pi):
        return {"field": None, "status": "invalid", "reason": "unknown_field", "claimed": f}
    if not isinstance(rs, list) or not rs or any(not isinstance(x, str) or x not in ids for x in rs):
        return {"field": None, "status": "invalid", "reason": "bad_record_ids", "claimed": f, "records": rs}
    return {"field": f, "status": "resolved", "records": rs}


# ---------------------------------------------------------------------------------------------- rewrite

def rewrite(target, det, field):
    s, e = det["span"]
    name = field.split(".")[0]
    new = target[:s] + f"part {name}" + target[e:]
    return new, {"rule": RULE, "span": [s, e], "original_phrase": target[s:e], "replacement": f"part {name}",
                 "original_sha256": hashlib.sha256(target.encode()).hexdigest(),
                 "rewritten_sha256": hashlib.sha256(new.encode()).hexdigest()}


def rewrite_prompt(extraction_prompt, target, new_target):
    if extraction_prompt.count(target) != 1:
        raise AssertionError("target line not unique in the extraction prompt")
    return extraction_prompt.replace(target, new_target)


def quote_contains_replacement(evidence, ledger):
    """Diagnostic: does an extraction's evidence quote contain the DERIVED replacement text of this arm's own rewrite?
    (BASE and bypass outputs have no ledger -> False.)"""
    return bool(ledger) and isinstance(evidence, str) and ledger["replacement"] in evidence


def ledger_for_arm(arm, source, det_ledger, model_ledger):
    if source == "use_BASE" or arm == "BASE":
        return None
    return det_ledger if arm == "RES_DET" else model_ledger
