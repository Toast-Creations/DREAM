"""V1.15.0 panel: the 1.14.0 coverage allocation (tempo.depgen.ROWS / SMOKE_ROWS, unchanged) with new pools and seeds,
plus the frozen prose channel inputs. depgen.py and freshgen.py are byte-unchanged; the new pool names are added to
freshgen's consonant table at import time (data only).

Allowlist export to the renderer and prompts (nothing else from the generator's orchestration record):
  public past records: history.public(r) = (rid, kind, status, event_at, received_at, payload) for each report
  renderer seed:       the world's generator seed (selects among the frozen prose templates; carries no state)
  world object:        the public world (fixed facts, rules, registry) rebuilt by the same builder
Never passed: truth, tape, labels, goals/goal roles, sensor values, intended statuses."""
from . import depgen as DG, freshgen as FG, history as Hm, prose_study as PS, text_channel as TC

POOLS = {"ftx": "cghlmpz", "ftxsmoke": "dfjkrtv"}
FG.CONS.update(POOLS)
ROWS, SMOKE_ROWS = DG.ROWS, DG.SMOKE_ROWS
build, specs, goal_copy = DG.build, DG.specs, DG.goal_copy


def text_inputs(w, hid):
    recs = [Hm.public(r) for r in hid["records_v02"]]
    view = {"records_v02": recs, "seed": hid["seed"]}
    texts = TC.prose_texts(w, view)
    prompts = TC.prompts(w, view)
    regs = [{f: Hm.allowed_values(w, f) for f in Hm.registry_fields(w, recs[:k])} for k in range(1, len(recs) + 1)]
    for r, t in zip(recs, texts):
        PS.check_equivalent(r, t)  # raises AssertionError (existing input-validity redraw rule)
    if not (len(recs) == len(texts) == len(prompts) == len(regs)):
        raise AssertionError("text input lists differ in length")
    return recs, texts, prompts, regs
