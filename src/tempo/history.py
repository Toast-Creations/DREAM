"""V1.8.1 milestone 2: history interpretation over state engine v0.1 (generation and prompts; no model).

24 fresh six-record histories (12 delivery, 6 assembly-slot, 6 assembly-stock; patterns 1-6 x 2 per domain).
Pattern 6 uses side b (unrecorded result later settled), others side a. Checkpoints after records 2, 4, 6 at that
record's reception time. Gold supported state: resolver 1 = resolver 2 on the prefix. Hidden simulator truth:
the complete record set's retrospective state at the checkpoint time (the records are generated true of the hidden
trajectory, checked by generate.truth_check), never shown to any system.
"""
import copy
import hashlib
import json
import random

from ectx import keycheck
from . import diag, enumcheck, generate as G, render, resolve, worlds
from .worlds import UNKNOWN

N_RECORDS = 6
CHECKPOINTS = (2, 4, 6)
CONSONANTS = {"hist": "cjvwy", "histsmoke": "fhlnprs", "prose": "bdgkmtz", "prosesmoke": "fhlnprs"}
FAMILIES = [("delivery", None, p) for p in range(1, 7) for _ in range(2)] + \
           [("assembly", fk, p) for p in range(1, 7) for fk in ("slot", "stock")]
SMOKE = [("delivery", None, 3), ("delivery", None, 6), ("assembly", "stock", 2), ("assembly", "slot", 5)]
PUBLIC = ("rid", "kind", "status", "event_at", "received_at", "payload")


class Names3:
    def __init__(self, pool, rng):
        self.rng, self.cons, self.used = rng, CONSONANTS[pool], set()

    def word(self):
        while True:
            w = "".join(self.rng.choice(self.cons) + self.rng.choice(worlds.VOWELS) for _ in range(3)).capitalize()
            if w not in self.used:
                self.used.add(w)
                return w


def actions(w):
    if w.domain == "delivery":
        return [["take", w.x], ["take", w.y]]
    return [["install", w.g, w.t], ["order", w.g]]


def _kc_step(w, fields, action):
    static, state, _ = w.to_planner(fields)
    st = keycheck._normalize(state)
    fn = keycheck._delivery_step if w.domain == "delivery" else keycheck._assembly_step
    return fn(static, st, list(action)) is not None


def verdict_over(w, states, action):
    oks = {_kc_step(w, s, action) for s in states}
    return "allowed" if oks == {True} else ("blocked" if oks == {False} else "unresolved")


def public(r):
    return {k: r[k] for k in PUBLIC}


def build_history(hid, domain, fk, pattern, seed, pool):
    rng = random.Random(seed)
    names = Names3(pool, rng)
    w = worlds.make_world(domain, rng, names, fk)
    F, Y = w.focal, w.side
    u, v = rng.sample(w.focal_values, 2)
    y1, y2 = w.side_values(rng)
    assign = {F: u, Y: y1}
    assign.update(w.other_init(rng))
    assign = {f: assign[f] for f in w.asked}
    c0 = w.focal_start_uncertain if domain == "delivery" else u
    opts = rng.sample([u, v], 2)
    res = rng.choice(opts)
    side = "b" if pattern == 6 else "a"
    base, intended, _, truth = G.base_records(pattern, side, F, u, v, Y, y1, y2, assign, c0, opts, res)
    chains = G.padding_chains(w, rng, N_RECORDS)
    recs = G.finalize(base + copy.deepcopy(G.take_padding(chains, N_RECORDS - len(base))))
    G.check_no_ties(recs)
    if pattern != 6:
        G.truth_check(recs, truth, pattern, side)
    if G.flat({F: G.agree_state(recs, [F], G.NOW)[F]})[F] != intended:
        raise AssertionError("pattern intent")
    if any(r["received_at"] > G.NOW for r in recs):
        raise AssertionError("record after NOW")
    cps = []
    for k in CHECKPOINTS:
        prefix = recs[:k]
        now = prefix[-1]["received_at"]
        fields = resolve.fields_of(prefix)
        gold = G.flat(G.agree_state(prefix, fields, now))
        tfields = [f for f in resolve.fields_of(recs) if any(a[0] == f and a[1] <= now
                                                              for a in resolve._assertions(recs))]
        true_state = G.flat(G.agree_state(recs, tfields, now))
        if UNKNOWN in true_state.values():
            raise AssertionError("hidden truth must be fully determined")
        states = enumcheck.supported_set(prefix, w.asked, now)[1]
        tests = []
        for act in actions(w):
            tests.append({"action": act, "gold_verdict": verdict_over(w, states, act),
                          "true_legal": _kc_step(w, {f: true_state[f] for f in w.asked}, act)})
        cps.append({"k": k, "now": now, "gold_state": gold, "true_state": true_state, "tests": tests})
    world = {k: val for k, val in vars(w).items() if k != "pad_names"}
    return w, {"history_id": hid, "domain": domain, "focal_kind": fk, "pattern": pattern,
               "pattern_name": G.PATTERNS[pattern], "side": side, "seed": seed, "pool": pool, "asked": w.asked,
               "focal_field": F, "world": world, "records": recs, "public_records": [public(r) for r in recs],
               "checkpoints": cps}


def specs(pool, base_seed, smoke=False):
    out = []
    for i, (dom, fk, p) in enumerate(SMOKE if smoke else FAMILIES):
        hid = f"{pool}-{dom[:3]}-{fk or 'loc'}-p{p}-{i:02d}"
        out.append((hid, dom, fk, p, int(hashlib.sha256(f"{base_seed}|{hid}".encode()).hexdigest()[:12], 16)))
    return out


# ------------------------------------------------------------------ prompts

def registry_fields(w, records_upto):
    """Fields of every entity named in the fixed facts or in the records shown so far (no future names)."""
    out = list(w.asked)
    for r in records_upto:
        p = r["payload"]
        for f in (list(p["assign"]) if r["kind"] == "initial" else [p["field"]]):
            if f not in out:
                out.append(f)
    return out


def allowed_values(w, f):
    return [x for x in w.allowed(f) if x != UNKNOWN]


EXTRACT_QUERY = [
    "QUERY (record extraction)",
    "Convert the new record into exactly one typed record. Report what the record itself states: its kind, whether "
    "it is verified or provisional, the time it is about, the time it was received, and its content. Do not decide "
    "what is true now and do not apply the record rules; only transcribe this record.",
    "Kinds: \"initial\" (facts about one time), \"observation\" (one fact), \"change\" (an event with a recorded "
    "result), \"uncertain_change\" (an event whose result was not recorded), \"correction\" (withdraws an earlier "
    "report's statement about one fact).",
]
EXTRACT_REPLY = [
    "Reply with only a JSON object:",
    '{"rid": "<record ID>", "kind": "...", "status": "verified" or "provisional", "event_at": <integer, or null for '
    'a correction>, "received_at": <integer>, "payload": {...}, "evidence": "<exact words from the new record>"}',
    "Payload by kind: initial {\"assign\": {\"<field>\": \"<value>\", ...}}; observation {\"field\": \"<field>\", "
    "\"value\": \"<value>\"}; change {\"field\": \"<field>\", \"from\": \"<value>\", \"to\": \"<value>\"}; "
    "uncertain_change {\"field\": \"<field>\", \"from\": \"<value>\", \"options\": [\"<value>\", ...]}; correction "
    "{\"target\": \"<record ID>\", \"field\": \"<field>\", \"value\": \"<value>\", \"valid_from\": <integer>, "
    "\"valid_to\": null}",
]


def extraction_prompt(w, records, k):
    """Call for record k (1-based): header, earlier records as context, the new record, schema."""
    prior, new = records[:k - 1], records[k - 1]
    lines = diag.header_complete(w)
    lines += ["", "Records received before this one (context only):"]
    lines += [render.record_line(w, r) for r in prior] if prior else ["(none)"]
    lines += ["", "New record to convert:", render.record_line(w, new), ""] + EXTRACT_QUERY
    lines += ["Fields and allowed values:"]
    lines += [f"- {json.dumps(f)}: one of " + ", ".join(json.dumps(x) for x in allowed_values(w, f))
              for f in registry_fields(w, records[:k])]
    lines += EXTRACT_REPLY
    return "\n".join(lines)


def readout_prompt(w, records, k):
    prefix = records[:k]
    now = prefix[-1]["received_at"]
    lines = diag.header_complete(w) + render.evidence_block(w, "C1", prefix, None, now)
    return "\n".join(lines + render.facts_query(w, "S0", None))
