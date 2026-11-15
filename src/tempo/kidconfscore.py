"""V1.22.0 KIDCONF-v1 per-record scoring (no model). HOLD-EVAL-v1 (tempo.holdeval.score, unchanged) against the
ORIGINAL target and prefix, plus the declared secondary classifications. A missing or non-ok record is scored as
incomplete; the analyzer never turns incompleteness into an error or a success for the gates (it blocks them)."""
import collections

from . import factored as FA, holdeval as HE, holdout as HO, kidconfgen as KG

_WORLDS = {}


def world(h, consonants=KG.DEFAULT_CONSONANTS):
    KG.register_pool(h["pool"], consonants)
    k = (h["world_seed"], h["pool"])
    if k not in _WORLDS:
        _WORLDS[k] = HO._world(*k)[0]
    return _WORLDS[k]


def val(x):
    return x.get("value", x.get("to"))


def score_record(rec, hidden, pub, consonants=KG.DEFAULT_CONSONANTS):
    case, w, reg = hidden["case"], world(hidden, consonants), pub["registry"]
    gold = case["records"][-1]
    gv = gold["payload"].get("to", gold["payload"].get("value"))
    ok = rec is not None and rec.get("status") == "ok"
    raw = rec["raw"] if ok else None
    s, _, tr = HE.score(raw, case, w, reg, None if rec is None else rec.get("stop"))
    s = {k: v for k, v in s.items() if k not in ("replay", "replay_ref")}
    claims, red = tr.get("claims"), tr.get("reduced")
    byf = collections.defaultdict(set)
    for k in FA.LISTS:
        for x in (claims or {}).get(k, []):
            if val(x) is not None:
                byf[x.get("field")].add(val(x))
    n_claims = sum(len((claims or {}).get(k, [])) for k in FA.LISTS)
    is_corr = gold["kind"] == "correction"
    s.update(
        incomplete=not ok,
        empty_extraction=ok and claims is not None and n_claims == 0,
        mixed_correction=is_corr and bool(red) and bool(red["states"]) and bool(red["revisions"]),
        value_conflict_internal=any(len(v) > 1 for v in byf.values()),
        value_contradicts_gold=any(v != gv for v in byf.get(case["field"], set())),
        contradictory_correction=is_corr and any(len(v) > 1 for v in byf.values()),
        rejected=ok and not s.get("accepted"),
        event_omitted=gold["kind"] == "change" and not s.get("event_on_X"),
        # raw event presence vs rejected extra-state claims (arrivals)
        arrival_event_present_raw=gold["kind"] == "change" and bool(s.get("event_on_X")),
        arrival_rejected_extra_state=(gold["kind"] == "change" and ok and not s.get("accepted")
                                      and bool(s.get("event_on_X")) and bool(s.get("raw_states"))),
        raw=raw, stop=None if rec is None else rec.get("stop"),
        input_tokens=None if rec is None else rec.get("input_tokens"),
        output_tokens=None if rec is None else rec.get("output_tokens"),
        seconds=None if rec is None else rec.get("seconds"))
    return s


def outcome(r):
    if r.get("incomplete"):
        return "incomplete (no ok record)"
    if r["exact"]:
        return "exact"
    if r.get("empty_extraction"):
        return "empty extraction" + (" (rejected)" if r.get("rejected") else "")
    if not r.get("accepted"):
        code = r.get("contract_code") or r.get("pending_code")
        if r.get("mixed_correction"):
            return f"rejected mixed state/revision ({code})"
        if r.get("arrival_rejected_extra_state"):
            return f"rejected event + extra state ({code})"
        return f"rejected ({code})"
    if not r.get("bound_ok_accepted"):
        return "accepted wrong binding"
    if r.get("state_only_event_accepted"):
        return "accepted state-only"
    if r.get("mixed_correction"):
        return "accepted mixed state/revision"
    return "accepted other inexact"
