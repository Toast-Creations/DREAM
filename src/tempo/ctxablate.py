"""V1.17.0 record-context ablation corpus and prompts (CTXAB-v1). No model.

Conditions (both use the 1.16.0 NULL_PRIOR schema, nullprior.null_prompt, unchanged):
  FULL   the frozen extraction prompt (prose_study.extraction_prompt, "prose" surface): header, the prior raw reports,
         the new report, instruction, the field registry of the prefix + target, reply schema.
  LOCAL  FULL with the prior-report lines replaced by the frozen empty-context marker "(none)" (the marker the
         frozen prompt already prints when a record has no predecessors). Nothing else differs (asserted).

Main corpus: self-contained target reports in assembly worlds (worlds.make_world, unchanged). Target part P = the
world's part G; competitor part Q = D; registry = the world's fixed asked fields [T.part, G.on_hand, S2.part, D.on_hand]
(identical whatever the mention order). Each group forks one prefix skeleton into four variants:
  arrival      prefix: verified "P not on hand"           target: verified change P no -> yes ("delivered/arrived")
  observation  prefix: verified "P on hand"               target: verified observation P on hand
  removal      prefix: verified "P on hand"               target: verified change P yes -> no ("taken away")
  correction   prefix: provisional "P on hand" (rid rX)   target: verified correction of rX: P not on hand from t_p
Shared skeleton per group: the P record, a verified stock observation of Q, a verified installation into slot T
(the lure: part P itself, or the low-rated part W), and in long prefixes a verified observation of slot S2.
Strata (8 cells x 15 groups, precommitted): prefix length 3/4; P record before/after Q's; lure P/W.
Template allocation: the renderer seed of each group is chosen (before any output) so that the arrival target's
frozen phrasing cycles through all 12 (head x body x change) combinations, 10 groups each; the same seed renders
the group's other variants (their first draw, the head, is therefore matched across variants).

Context-required controls: one world, two alternative histories H_A / H_B (r01, r02 verified stock observations of
P and Q in swapped order, r03 an observation of slot T), and one identical new report r04 whose referent is only
"the part whose stock was checked in r02" (a declared control-only phrasing; the frozen renderer always names the
entity). Gold under H_A: Q's stock change; under H_B: P's. Header, registry (fixed asked fields) and new report are
byte-identical, so the two LOCAL prompts are identical (asserted) and LOCAL is called once (cached for both).
"""
import hashlib
import itertools
import random

from . import freshgen as FG, generate as G, history as Hm, nullprior as NP, prose, prose_study as PS, worlds
from .worlds import EMPTY, NO, YES

POOLS = {"cab": "bdhkmpt", "cabsmoke": "cfglrsv", "cabctl": "bjnpstz", "cabctlsmoke": "dfhkmrw"}
FG.CONS.update(POOLS)
VARIANTS = ("arrival", "observation", "removal", "correction")
CONDITIONS = ("FULL", "LOCAL")
CTX_HEAD = "Records received before this one (context only):"
EMPTY_MARK = "(none)"
STRATA = list(itertools.product((3, 4), ("P_first", "Q_first"), ("lure_P", "lure_W")))


def _world(seed, pool):
    rng = random.Random(seed)
    w = worlds.make_world("assembly", rng, FG.Names(pool, rng), "stock")
    return w, rng


def template_id(text):
    """(head, body, change) indices of an arrival rendering under the frozen templates."""
    h = 0 if text.startswith("Message ") else 1 if " (came in at time " in text.split(":")[0] else 2
    b = 0 if "confirmed (verified) event" in text.lower() else 1
    c = 0 if "was delivered to you" in text else 1
    return h * 4 + b * 2 + c


def _skeleton(w, rng, stratum, variant):
    length, order, lure = stratum
    P, Q = f"{w.g}.on_hand", f"{w.d}.on_hand"
    prov = variant == "correction"
    pval = NO if variant == "arrival" else YES
    p_rec = G.R("observation", None, None, {"field": P, "value": pval}, status="provisional" if prov else "verified",
                key="prec")
    q_rec = G.R("observation", None, None, {"field": Q, "value": rng.choice([YES, NO])})
    lure_part = w.g if lure == "lure_P" else w.w
    t_rec = G.R("change", None, None, {"field": w.slot_f, "from": EMPTY, "to": lure_part})
    recs = [p_rec, q_rec] if order == "P_first" else [q_rec, p_rec]
    recs.append(t_rec)
    if length == 4:
        recs.append(G.R("observation", None, None, {"field": w.side, "value": rng.choice([EMPTY, w.e, w.e2])}))
    return recs


def build_group(gid, seed, stratum, pool, want_template):
    """Returns {variant: (records, target index)} plus the world and renderer seed. All four variants share entities,
    skeleton values and times; only the P record (value/status) and the target differ."""
    w, rng = _world(seed, pool)
    state = rng.getstate()
    times = sorted(rng.sample(range(1, 10), stratum[0]))
    t_target = rng.randint(times[-1] + 1, 11)
    out = {}
    for v in VARIANTS:
        rng.setstate(state)
        rng.sample(range(1, 10), stratum[0]); rng.randint(times[-1] + 1, 11)
        recs = _skeleton(w, rng, stratum, v)
        for r, t in zip(recs, times):
            r["event_at"] = r["received_at"] = t
        P = f"{w.g}.on_hand"
        p_t = next(r for r in recs if r["key"] == "prec")["event_at"]
        if v == "arrival":
            tgt = G.R("change", t_target, t_target, {"field": P, "from": NO, "to": YES})
        elif v == "observation":
            tgt = G.R("observation", t_target, t_target, {"field": P, "value": YES})
        elif v == "removal":
            tgt = G.R("change", t_target, t_target, {"field": P, "from": YES, "to": NO})
        else:
            tgt = G.R("correction", None, t_target, {"target": "prec", "field": P, "value": NO, "valid_from": p_t,
                                                     "valid_to": None})
        recs = G.finalize(recs + [tgt])
        G.check_no_ties(recs)
        out[v] = recs
    for rs in seed_iter(seed):
        tx = prose.prose_line(w, out["arrival"][-1], rs)
        if template_id(tx) == want_template:
            return w, out, rs
    raise AssertionError("no renderer seed for the template")


def seed_iter(seed):
    for i in range(10000):
        yield int(hashlib.sha256(f"render|{seed}|{i}".encode()).hexdigest()[:12], 16)


def public(recs):
    return [Hm.public(r) for r in recs]


def full_prompt(w, recs, rseed, target_line=None):
    """FULL (null-prior schema) for the last record; target_line overrides the rendered new-record line (controls)."""
    h = {"records": public(recs), "seed": rseed}
    u = PS.extraction_prompt(w, h, "prose", len(recs))
    if target_line is not None:
        old = PS.line_fn(w, h, "prose")(h["records"][-1])
        if u.count(old) != 1:
            raise AssertionError("target line not unique")
        u = u.replace(old, target_line)
    return NP.null_prompt(u)


def local_prompt(full):
    lines = full.split("\n")
    i = lines.index(CTX_HEAD)
    j = lines.index("New record to convert:")
    if lines[j - 1] != "":
        raise AssertionError("unexpected prompt layout")
    out = lines[:i + 1] + [EMPTY_MARK, ""] + lines[j:]
    return "\n".join(out)


def check_diff(full, local):
    """The only difference: the prior-report lines become the empty marker."""
    fl, ll = full.split("\n"), local.split("\n")
    i = fl.index(CTX_HEAD)
    j = fl.index("New record to convert:")
    jl = ll.index("New record to convert:")
    assert fl[:i + 1] == ll[:i + 1] and fl[j:] == ll[jl:] and ll[i + 1:jl] == [EMPTY_MARK, ""], "LOCAL diff"
    return fl[i + 1:j - 1]


def registry(w, recs):
    return {f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, recs)}


def control_text(rid, t, rng):
    head = rng.choice([f"Message {rid}, received at time {t}: ", f"{rid} (came in at time {t}): "])
    return head + (f"it is verified that at time {t} the part whose stock was checked in r02 was delivered to you, so "
                   f"it is now on hand.")


def build_control(cid, seed, pool):
    w, rng = _world(seed, pool)
    P, Q = f"{w.g}.on_hand", f"{w.d}.on_hand"
    t1, t2, t3 = sorted(rng.sample(range(1, 8), 3))
    t4 = rng.randint(t3 + 1, 11)
    slot = G.R("observation", t3, t3, {"field": w.slot_f, "value": EMPTY})
    hist = {}
    for name, (first, second) in (("A", (P, Q)), ("B", (Q, P))):
        recs = [G.R("observation", t1, t1, {"field": first, "value": NO}),
                G.R("observation", t2, t2, {"field": second, "value": NO}), dict(slot)]
        tgt = G.R("change", t4, t4, {"field": second, "from": NO, "to": YES})
        hist[name] = G.finalize(recs + [tgt])
    rseed = next(seed_iter(seed))
    text = control_text("r04", t4, random.Random(rseed))
    return w, hist, rseed, text
