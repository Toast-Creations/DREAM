"""V1.8.2: frozen normaliser, one validation-feedback retry, and the shared extraction-pipeline replay.

Normaliser (identical in both branches). Only demonstrably equivalent representations are converted; every
conversion is logged with its rule ID and the original value. Nothing else is changed: no missing time is inferred,
no kind is changed, no alternatives are invented, no entity, target or value is altered.
  N1 value_spelling   a value that matches exactly one allowed value of its field ignoring case, surrounding spaces,
                      a trailing full stop, or a leading entity word ("crate ", "part ", "slot ", "place ")
  N2 int_string       a time given as a string of digits ("4") -> the integer 4
  N3 correction_event_at  kind "correction" with integer event_at equal to its own integer valid_from, a string
                      target and valid_to null: event_at (a redundant copy of the validity start) -> null.
                      Any other non-null event_at on a correction is left alone (the engine then rejects it).
Unrequested top-level keys are dropped and logged (rule N0); they are never read.

Retry policy (one-retry branch only): at most one retry per record, triggered only by a parse failure or an engine
RecordRejected (an enumerated input-contract rule). The feedback holds the original extraction prompt (raw prose,
permitted prefix, registry, schema), the previous reply, and the violated rule's text plus the engine message. It
never holds a gold value, a corrected kind, hidden state or a scorer explanation. If the retry also fails, the
record is registered as unprocessed (engine.record_unprocessed) and the pipeline continues; nothing is backfilled.
"""
import copy
import hashlib
import json
import re

from . import engine as E, score as S

TOP = ("rid", "kind", "status", "event_at", "received_at", "payload", "evidence")
PARSE_RULE = "the reply must be exactly one JSON object (optionally inside one code fence) and nothing else"


def _int_string(v):
    return int(v) if isinstance(v, str) and re.fullmatch(r"\s*\d+\s*", v) else v


def normalise(obj, registry):
    """(record or None, [rule applications]). registry: field -> allowed values."""
    if not isinstance(obj, dict):
        return None, []
    log = []
    extra = [k for k in obj if k not in TOP]
    if extra:
        log.append({"rule": "N0", "dropped_keys": extra})
    rec = {k: copy.deepcopy(obj.get(k)) for k in ("rid", "kind", "status", "event_at", "received_at", "payload")}
    if isinstance(obj.get("evidence"), str):
        rec["evidence"] = obj["evidence"]
    for t in ("event_at", "received_at"):
        n = _int_string(rec[t])
        if n is not rec[t] and n != rec[t]:
            log.append({"rule": "N2", "key": t, "original": rec[t]}); rec[t] = n
    p = rec["payload"]
    if isinstance(p, dict):
        if "valid_from" in p:
            n = _int_string(p["valid_from"])
            if n != p["valid_from"]:
                log.append({"rule": "N2", "key": "payload.valid_from", "original": p["valid_from"]}); p["valid_from"] = n

        def nv(f, v, where):
            if not isinstance(f, str) or f not in registry or not isinstance(v, str):
                return v
            m = S.match_value(v, registry[f])
            if m is not None and m != v:
                log.append({"rule": "N1", "key": where, "original": v, "normalised": m})
                return m
            return v
        if isinstance(p.get("assign"), dict):
            p["assign"] = {f: nv(f, v, f"assign.{f}") for f, v in p["assign"].items()}
        f = p.get("field")
        for key in ("value", "from", "to"):
            if key in p:
                p[key] = nv(f, p[key], key)
        if isinstance(p.get("options"), list):
            p["options"] = [nv(f, x, "options") for x in p["options"]]
    if (rec["kind"] == "correction" and isinstance(rec["event_at"], int) and not isinstance(rec["event_at"], bool)
            and isinstance(p, dict) and isinstance(p.get("valid_from"), int) and rec["event_at"] == p["valid_from"]
            and isinstance(p.get("target"), str) and "valid_to" in p and p["valid_to"] is None):
        log.append({"rule": "N3", "key": "event_at", "original": rec["event_at"]})
        rec["event_at"] = None
    return rec, log


def feedback_prompt(original_prompt, previous_raw, code, message):
    rule = PARSE_RULE if code == "parse" else E.REJECT_CODES[code]
    return (original_prompt + "\n\nYour previous reply:\n" + (previous_raw if previous_raw is not None else "") +
            "\n\nThat reply was not accepted. Rule not met: " + rule +
            (f" (validator message: {message})" if message else "") + "." +
            "\nReply again with one typed record for the same new record, in the schema above. Transcribe what the "
            "new record states; do not change what it says in order to fit earlier records.")


def attempt(eng, raw, registry):
    """Parse, normalise, ingest. Returns (accepted, record or None, norm log, code, message)."""
    if raw is None:
        return False, None, [], "parse", "no reply"
    obj, err = S.parse_object(raw)
    if err is not None:
        return False, None, [], "parse", err
    rec, log = normalise(obj, registry)
    if rec is None:
        return False, None, log, "parse", "not an object"
    try:
        eng.ingest_report(dict(rec, source="extractor:qwen3-8b"))
    except E.RecordRejected as e:
        return False, rec, log, e.code, str(e)[:300]
    return True, rec, log, None, None


def run_branch(spec, context, surface_texts, prompts, registries, initial_raw, retry_fn=None, checkpoints=(2, 4, 6),
               now_of=None, on_checkpoint=None):
    """Replay one history on one surface. initial_raw[k], prompts[k], registries[k], surface_texts[k] for k=1..6.
    retry_fn(k, feedback_prompt) -> raw reply or None (None: no retry branch). on_checkpoint(k, engine) is called
    after record k for k in checkpoints. Returns per-record rows."""
    eng = E.Engine(spec, context)
    rows = []
    for k in sorted(prompts):
        acc, rec, nlog, code, msg = attempt(eng, initial_raw.get(k), registries[k])
        row = {"k": k, "initial": {"accepted": acc, "record": rec, "norm": nlog, "code": code, "message": msg},
               "retried": False, "final": None}
        final = row["initial"]
        if not acc and retry_fn is not None:
            fp = feedback_prompt(prompts[k], initial_raw.get(k), code, msg)
            raw2 = retry_fn(k, fp)
            acc2, rec2, nlog2, code2, msg2 = attempt(eng, raw2, registries[k])
            row["retried"] = True
            row["retry"] = {"accepted": acc2, "record": rec2, "norm": nlog2, "code": code2, "message": msg2,
                            "raw": raw2, "prompt_sha256": hashlib.sha256(fp.encode()).hexdigest()}
            final = row["retry"]
        if not final["accepted"]:
            eng.record_unprocessed(f"r{k:02d}", now_of(k) if now_of else None, surface_texts[k], final["record"],
                                   final["code"], final["message"])
        row["final"] = final
        rows.append(row)
        if on_checkpoint and k in checkpoints:
            on_checkpoint(k, eng)
    return rows, eng
