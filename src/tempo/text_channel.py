"""V1.9.1 text input channel for the observation-policy study (frozen extractor -> versioned adapter -> engine v0.3).

Extraction call (unchanged from the repair/prose study): the 1.8.2 extraction instruction (prose_study.extraction_prompt
on the "prose" surface: header + domain statements, earlier prose reports as context, the new prose report, the v0.2
typed-record schema, the registry of fields named so far). Same model settings, cap 256, no retry.

Adapter v1 (deterministic; the only conversions allowed):
  1. parse: one JSON object, at most one code fence (score.parse_object); otherwise the report is unprocessed.
  2. normalise: the frozen 1.8.2 normaliser (repair.normalise: N0 extra keys dropped, N1 value spelling, N2 digit-string
     times, N3 a correction's event_at equal to its own valid_from -> null), every application logged.
  3. map: tempo.assertions.from_v02 (initial/observation -> state report; change -> event with from; uncertain_change
     -> event with to_options, keeping from only if given; correction -> correction), with two declared
     representation rules: (M1) an uncertain_change without "from" maps to an event with no stated prior value
     (contract v1 permits it); (M2) a correction whose event_at is still non-null after N3 is NOT mapped (conflicting
     time fields) and the report is unprocessed.
  4. ingest into engine v0.3; a structural rejection (ContractRejected) makes the report unprocessed.
An unprocessed report is registered with its raw prose (record_unprocessed), so the fields it names are incomplete.
Nothing is corrected against gold, nothing is retried, no missing assertion is filled.
"""
import copy

from . import assertions as A, engine as E, prose_study as PS, repair as RP, score as S

ADAPTER_VERSION = "adapter-v1"


def history_view(ep):
    """The minimal history dict prose_study.extraction_prompt needs."""
    return {"records": ep["records_v02"], "seed": ep["seed"]}


def prompts(w, ep):
    h = history_view(ep)
    return [PS.extraction_prompt(w, h, "prose", k) for k in range(1, len(ep["records_v02"]) + 1)]


def prose_texts(w, ep):
    h = history_view(ep)
    line = PS.line_fn(w, h, "prose")
    return [line(r) for r in ep["records_v02"]]


def adapt(raw, registry):
    """raw model reply -> (contract-v1 report or None, log dict)."""
    log = {"parse_error": None, "norm": [], "unmapped": None}
    if raw is None:
        log["parse_error"] = "no reply"
        return None, log
    obj, err = S.parse_object(raw)
    if err is not None:
        log["parse_error"] = err
        return None, log
    rec, nlog = RP.normalise(obj, registry)
    log["norm"] = nlog
    if rec is None:
        log["unmapped"] = "not an object"
        return None, log
    kind = rec.get("kind")
    if kind not in E.KINDS or not isinstance(rec.get("payload"), dict):
        log["unmapped"] = f"kind {kind!r} or payload not mappable"
        return None, log
    if kind == "correction" and rec.get("event_at") is not None:
        log["unmapped"] = "M2: correction with a non-null event_at"
        return None, log
    p = dict(rec["payload"])
    if kind == "uncertain_change":
        if "options" not in p:
            log["unmapped"] = "uncertain_change without options"
            return None, log
        p.setdefault("from", None)  # M1
    try:
        rep = A.from_v02({"rid": rec.get("rid"), "kind": kind, "status": rec.get("status"),
                          "event_at": rec.get("event_at"), "received_at": rec.get("received_at"), "payload": p})
    except (KeyError, TypeError, AttributeError) as e:
        log["unmapped"] = f"payload keys for {kind}: {e!r}"[:200]
        return None, log
    rep["source"] = "extractor:qwen3-8b"
    if isinstance(rec.get("evidence"), str):
        rep["evidence"] = rec["evidence"]
    return rep, log


def build_channel(ep, raws, registries, texts):
    """Ingest the six extractions in order. Returns {"sequence": [...], "rows": [...]} for engine_from()."""
    eng = A.AssertionEngine(ep["spec"], f"{ep['episode_id']}|text")
    seq, rows = [], []
    for k, (raw, reg, text) in enumerate(zip(raws, registries, texts), 1):
        rep, log = adapt(raw, reg)
        accepted, code = False, None
        if rep is not None:
            try:
                eng.ingest(rep)
                accepted = True
                seq.append({"kind": "report", "report": rep})
            except A.ContractRejected as e:
                code = e.code
        else:
            code = "parse" if log["parse_error"] else "unmapped"
        if not accepted:
            gold_rec = ep["records_v02"][k - 1]
            pend = {"rid": f"r{k:02d}", "received_at": gold_rec["received_at"], "raw": text,
                    "candidate": rep, "code": code, "message": log["parse_error"] or log["unmapped"]}
            eng.record_unprocessed(**{"rid": pend["rid"], "received_at": pend["received_at"], "raw_text": text,
                                      "candidate": rep, "code": code, "message": pend["message"]})
            seq.append({"kind": "pending", "pending": pend})
        rows.append({"k": k, "raw": raw, "report": rep, "adapter_log": log, "accepted": accepted, "code": code})
    return {"sequence": seq, "rows": rows}
