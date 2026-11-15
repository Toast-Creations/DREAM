"""V1.8.2: a less templated prose rendering of a typed record, asserting exactly the same facts, times, status,
correction scope and uncertainty as render.record_line. The record ID and reception time stay explicit (application
metadata). Several phrasings per kind are chosen by a seed derived from the history seed and record ID, so the surface
varies without changing truth conditions. Every rendering is unambiguous by construction; tests check that each one
names its record ID, reception time, event time (or correction validity start and target), every entity and value,
and its status wording.
"""
import hashlib
import random

from .worlds import CARRIED, EMPTY, YES


def _rng(seed, rid):
    return random.Random(int(hashlib.sha256(f"{seed}|{rid}".encode()).hexdigest()[:12], 16))


def fact(w, f, v, rng):
    e = f.split(".")[0]
    if f.endswith(".location"):
        if v == CARRIED:
            return rng.choice([f"crate {e} is being carried by you", f"you are carrying crate {e}"])
        return rng.choice([f"crate {e} is at {v}", f"crate {e} sits at {v}", f"crate {e} is resting at {v}"])
    if f.endswith(".on_hand"):
        if v == YES:
            return rng.choice([f"part {e} is on hand", f"you have part {e} on hand"])
        return rng.choice([f"part {e} is not on hand", f"you do not have part {e} on hand"])
    if v == EMPTY:
        return rng.choice([f"slot {e} is empty", f"nothing is installed in slot {e}"])
    return rng.choice([f"slot {e} holds part {v}", f"part {v} is installed in slot {e}"])


def _join(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def change(w, f, frm, to, rng):
    e = f.split(".")[0]
    if f.endswith(".location"):
        return rng.choice([f"another worker carried crate {e} from {frm} over to {to}",
                           f"crate {e} was moved by another worker from {frm} to {to}"])
    if f.endswith(".on_hand"):
        if to == YES:
            return rng.choice([f"part {e} was delivered to you, so it is now on hand",
                               f"part {e} arrived for you and is now on hand"])
        return rng.choice([f"another team took part {e} away, so it is no longer on hand",
                           f"part {e} was taken by another team and is no longer on hand"])
    if frm == EMPTY:
        return f"another technician fitted part {to} into slot {e}, using their own stock"
    if to == EMPTY:
        return f"another technician pulled part {frm} out of slot {e} and took it away, leaving the slot empty"
    return f"another technician swapped part {frm} in slot {e} for part {to}, taking {frm} away"


def _opt(f, o):
    if f.endswith(".location"):
        return f"at {o}"
    if f.endswith(".on_hand"):
        return "on hand" if o == YES else "not on hand"
    return "empty" if o == EMPTY else f"holding part {o}"


def uncertain(w, f, frm, opts, rng):
    e = f.split(".")[0]
    a, b = (_opt(f, o) for o in opts)
    if f.endswith(".location"):
        return rng.choice([f"another worker moved crate {e} away from {frm}, but nobody wrote down where it went; it "
                           f"ended up either {a} or {b}",
                           f"crate {e} was taken away from {frm} by another worker and its destination was not "
                           f"recorded, so it is now either {a} or {b}"])
    if f.endswith(".on_hand"):
        return (f"a stock check of part {e} was cut short and whether part {e} was moved was never recorded; "
                f"afterwards it is either {a} or {b}")
    return (f"another technician worked on slot {e} and the result was not written down; afterwards the slot is "
            f"either {a} or {b}")


def subject(f):
    e = f.split(".")[0]
    if f.endswith(".location"):
        return f"where crate {e} was"
    return f"whether part {e} was on hand" if f.endswith(".on_hand") else f"what slot {e} held"


def prose_line(w, r, seed):
    rng = _rng(seed, r["rid"])
    p, k, rid, t = r["payload"], r["kind"], r["rid"], r["received_at"]
    head = rng.choice([f"Message {rid}, received at time {t}: ", f"{rid} (came in at time {t}): ",
                       f"At time {t} we received {rid}. "])
    prov = r["status"] == "provisional"
    if head.endswith(". "):
        return _cap(head, _body(w, r, rng, prov))
    return head + _body(w, r, rng, prov)


def _cap(head, body):
    return head + body[0].upper() + body[1:]


def _body(w, r, rng, prov):
    p, k = r["payload"], r["kind"]
    if k in ("initial", "observation"):
        facts = [fact(w, f, v, rng) for f, v in (p["assign"].items() if k == "initial" else [(p["field"], p["value"])])]
        body = _join(facts)
        e = r["event_at"]
        if prov:
            return rng.choice([f"an early, unconfirmed (provisional) report says that at time {e} {body}. "
                                      f"It has not been verified yet.",
                                      f"a provisional report, not yet verified, states that as of time {e} {body}."])
        return rng.choice([f"a confirmed check shows that at time {e} {body}.",
                                  f"someone verified that, as of time {e}, {body}.",
                                  f"checked and confirmed (verified): at time {e}, {body}."])
    if k == "change":
        return rng.choice([f"confirmed (verified) event: at time {r['event_at']}, "
                                  f"{change(w, p['field'], p['from'], p['to'], rng)}.",
                                  f"it is verified that at time {r['event_at']} "
                                  f"{change(w, p['field'], p['from'], p['to'], rng)}."])
    if k == "uncertain_change":
        return f"verified event at time {r['event_at']}: {uncertain(w, p['field'], p['from'], p['options'], rng)}."
    if k == "correction":
        tg = p["target"]
        return rng.choice([
            f"this is a verified correction of {tg}. {tg} got {subject(p['field'])} wrong: actually, from time "
            f"{p['valid_from']} on, {fact(w, p['field'], p['value'], rng)} (until a recorded event changes it). "
            f"Nothing physically changed when this correction arrived.",
            f"verified correction to {tg}: {tg} was mistaken about {subject(p['field'])}. In fact "
            f"{fact(w, p['field'], p['value'], rng)} from time {p['valid_from']} onward, unless a recorded event "
            f"changes it. The correction itself is not an event."])
    raise ValueError(k)
