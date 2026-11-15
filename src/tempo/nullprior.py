"""V1.16.0 paired extraction-interface test: ORIGINAL (frozen 1.15.1 prompt, unchanged) vs NULL-PRIOR (the same
prompt with one declared clarification about unstated prior values). Everything else is unchanged and shared:
the new record, raw historical prefix, domain header, registry, system message, model, decoding, schema keys,
adapter-v1, engine, selector and temporal rules.

The NULL-PRIOR prompt = the ORIGINAL prompt with exactly one text replacement (asserted to occur once):
  the payload line of history.EXTRACT_REPLY, where
    change {"field": "<field>", "from": "<value>", "to": "<value>"}
    uncertain_change {"field": "<field>", "from": "<value>", "options": [...]}
  advertise "from": "<value>" or null, followed by one added line (the clarification).
No arrival/removal examples, no trigger words, no source validator, no change to evidence quoting, context or
corrections. A missing ordinary "from" key stays a mapping failure in both arms (adapter unchanged).

Panel: 96 worlds = four fresh instances of each of the 24 fixed case families (tempo.depgen.ROWS, unchanged); the
instance index is appended to the family id ("d01i1" ... "a12i4") and the seed is derived from it."""
import hashlib

from . import depgen as DG, freshgen as FG, ftxgen as XG, history as Hm

INTERFACES = ("ORIGINAL", "NULL_PRIOR")
CLARIFICATION = ("For change and uncertain_change, include the from key. If the new record does not explicitly state "
                 "the prior value, use JSON null. Otherwise transcribe the stated prior value.")
PAYLOAD_LINE = Hm.EXTRACT_REPLY[2]
NULL_PAYLOAD_LINE = PAYLOAD_LINE.replace(
    'change {"field": "<field>", "from": "<value>", "to": "<value>"}',
    'change {"field": "<field>", "from": "<value>" or null, "to": "<value>"}').replace(
    'uncertain_change {"field": "<field>", "from": "<value>", "options"',
    'uncertain_change {"field": "<field>", "from": "<value>" or null, "options"')
assert NULL_PAYLOAD_LINE.count(" or null") == 2

POOLS = {"nul": "bdfgkpt", "nulsmoke": "chjlmrs"}
FG.CONS.update(POOLS)
N_INST = 4
ROWS = [(d, (f"{r[0]}i{n}",) + tuple(r[1:])) for n in range(1, N_INST + 1) for d, r in DG.ROWS]
SMOKE_ROWS = list(DG.SMOKE_ROWS)
build, goal_copy, text_inputs = DG.build, DG.goal_copy, XG.text_inputs


def family(world_id):
    return world_id.split("i")[0] if not world_id.startswith("s-") else world_id


def specs(pool, base_seed, smoke=False):
    out = []
    for domain, r in (SMOKE_ROWS if smoke else ROWS):
        out.append((domain, r, int(hashlib.sha256(f"{base_seed}|{pool}|{r[0]}".encode()).hexdigest()[:12], 16)))
    return out


def null_prompt(original):
    if original.count(PAYLOAD_LINE) != 1:
        raise AssertionError("payload line must occur exactly once")
    return original.replace(PAYLOAD_LINE, NULL_PAYLOAD_LINE + "\n" + CLARIFICATION)
