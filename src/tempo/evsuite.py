"""EVT suite (V1.27.0): three back-to-back studies on fresh panels. No model or inference.

Generalizes tempo.evreport (EVT-v1, unchanged) to closed study specs:
  A  EVTC-v1  confirmation of the policy KEEP_EVT + IGUARD vs KEEP_CLAR + IGUARD (288 arrival, 48 correction stems)
  B  EVTR-v1  screen of a narrowed event sentence: KEEP_CLAR, KEEP_EVT, KEEP_EVTR (144 arrival, 48 correction stems)
  C  EVTB-v1  descriptive wrong-binding panel: history-B arrivals only, F2:F3 = 1:3, 384 stems, three arms
  D  EVTT-v1  (V1.29.0) screen of the combined sentence KEEP_EVTT against KEEP_EVT, with KEEP_CLAR as anchor;
              delayed-F3-heavy panel (240 arrival stems in 15-stem blocks, 15 correction stems)

KEEP_CLAR is the unchanged V1.24 builder. KEEP_EVT is exactly tempo.evreport.event_prompt. KEEP_EVTR inserts
EVTR_SENTENCE at the same position (its own line directly after the query line that begins
"List the assertions by category"). Removing the inserted line gives back KEEP_CLAR byte for byte.
KEEP_EVTR's wording is the replacement Codex required before freeze (review F6); it combines scope narrowing with a
state-time instruction, so study B cannot attribute an effect to either clause separately.

KEEP_EVTT (V1.29.0, study D) is KEEP_EVT's line with KEEP_EVTR's state-time clause appended in the same line
(verbatim apart from the capital letter), at the same position. KEEP_EVTT minus its appended sentence is KEEP_EVT
byte for byte, so KEEP_EVTT-KEEP_EVT isolates the time clause given KEEP_EVT's scope. Studies A-C are unchanged.

Arrival wording is set by allocation bit b1 (tempo.evreport.wording). Bits b0/b1 cycle over the four cells within
every family x reception stratum (b2 = 0), so both wordings are exactly balanced in every stratum of every panel.
"""
import collections
import copy
import hashlib
import json
import random
import re

from . import clarify as CL, evreport as ES, holdout as HO, kidconf as KC, kidconfgen as KG

SUITE = "EVT-SUITE-v1"
DIRECTIONS = CL.DIRECTIONS
ANCHOR_PREFIX = ES.ANCHOR_PREFIX
EVENT_SENTENCE = ES.EVENT_SENTENCE
EVTR_SENTENCE = ('If the new record reports a change and follows it with a separate clause stating the resulting '
                 'value, list the change under "events"; for that change, any resulting value you also list under '
                 '"states" should use the time explicitly stated for the change.')
EVTT_CLAUSE = 'For that change, any resulting value you also list under "states" should use the time explicitly ' \
              'stated for the change.'
EVTT_SENTENCE = EVENT_SENTENCE + " " + EVTT_CLAUSE
SENTENCES = {"KEEP_EVT": EVENT_SENTENCE, "KEEP_EVTR": EVTR_SENTENCE, "KEEP_EVTT": EVTT_SENTENCE}
BLOCK12 = ES.BLOCK
BLOCK8 = (("F2_slot_join", "immediate"), ("F2_slot_join", "delayed")) + \
         (("F3_historical_occupant", "immediate"),) * 3 + (("F3_historical_occupant", "delayed"),) * 3
# Study D: delayed-F3-heavy (all KEEP_EVT reception-dated replies in the suite were F3 delayed RESULT). Every
# family x reception cell count per block is 1, 2 or 9, so 16 blocks give multiples of 4 and exact wording balance.
BLOCK15D = (("F1_two_hop", "immediate"), ("F1_two_hop", "delayed"), ("F2_slot_join", "immediate"),
            ("F2_slot_join", "delayed")) + (("F3_historical_occupant", "immediate"),) * 2 + \
           (("F3_historical_occupant", "delayed"),) * 9
SMOKE2 = (("F2_slot_join", "immediate", [0, 0, 0]), ("F3_historical_occupant", "delayed", [0, 1, 0]))
SMOKE4 = (("F2_slot_join", "immediate", [0, 0, 0]), ("F2_slot_join", "delayed", [0, 1, 0]),
          ("F3_historical_occupant", "immediate", [0, 1, 0]), ("F3_historical_occupant", "delayed", [0, 0, 0]))

SPECS = {
    "A": {"study": "EVTC-v1", "arms": ("KEEP_CLAR", "KEEP_EVT"), "block": "BLOCK12", "arrival_blocks": 24,
          "correction_blocks": 4, "arrival_histories": ["A", "B"], "smoke": "SMOKE2",
          "base_seed": 2026111251, "smoke_base_seed": 2026111252, "schedule_seed": 2026111253,
          "pool": "su27a", "smoke_pool": "su27as", "id_prefix": "v27a-g", "smoke_prefix": "v27a-s",
          "main_calls": 1536, "smoke_calls": 24},
    "B": {"study": "EVTR-v1", "arms": ("KEEP_CLAR", "KEEP_EVT", "KEEP_EVTR"), "block": "BLOCK12",
          "arrival_blocks": 12, "correction_blocks": 4, "arrival_histories": ["A", "B"], "smoke": "SMOKE2",
          "base_seed": 2026111261, "smoke_base_seed": 2026111262, "schedule_seed": 2026111263,
          "pool": "su27b", "smoke_pool": "su27bs", "id_prefix": "v27b-g", "smoke_prefix": "v27b-s",
          "main_calls": 1440, "smoke_calls": 36},
    "C": {"study": "EVTB-v1", "arms": ("KEEP_CLAR", "KEEP_EVT", "KEEP_EVTR"), "block": "BLOCK8",
          "arrival_blocks": 48, "correction_blocks": 0, "arrival_histories": ["B"], "smoke": "SMOKE4",
          "base_seed": 2026111271, "smoke_base_seed": 2026111272, "schedule_seed": 2026111273,
          "pool": "su27c", "smoke_pool": "su27cs", "id_prefix": "v27c-g", "smoke_prefix": "v27c-s",
          "main_calls": 1152, "smoke_calls": 12},
    "D": {"study": "EVTT-v1", "arms": ("KEEP_CLAR", "KEEP_EVT", "KEEP_EVTT"), "block": "BLOCK15D",
          "arrival_blocks": 16, "correction_blocks": 1, "arrival_histories": ["A", "B"], "smoke": "SMOKE2",
          "base_seed": 2026111491, "smoke_base_seed": 2026111492, "schedule_seed": 2026111493,
          "pool": "su29d", "smoke_pool": "su29ds", "id_prefix": "v29d-g", "smoke_prefix": "v29d-s",
          "main_calls": 1620, "smoke_calls": 36},
}
_BLOCKS = {"BLOCK12": BLOCK12, "BLOCK8": BLOCK8, "BLOCK15D": BLOCK15D}
_SMOKES = {"SMOKE2": SMOKE2, "SMOKE4": SMOKE4}
_META_KEYS = ("stem", "set", "block", "family", "reception", "bits", "primary_arrival", "primary_correction")


def default_config(key):
    spec = SPECS[key]
    extra = {"evtt_sentence": EVTT_SENTENCE} if key == "D" else {}   # A-C configs stay byte-identical to V1.27.0
    return {**extra, "suite": SUITE, "key": key, **{k: (list(v) if isinstance(v, tuple) else v) for k, v in spec.items()},
            "block_size": len(_BLOCKS[spec["block"]]), "receptions": ["immediate", "delayed"],
            "bits_rule": "within-stratum-cycle-v1", "b2": 0, "schedule_rule": "stem-act-unit-v1",
            "consonants": KG.DEFAULT_CONSONANTS, "max_attempts": 300, "max_new_tokens": 256,
            "evtr_sentence": EVTR_SENTENCE, "event_sentence": EVENT_SENTENCE}


def validate_config(config):
    """Closed explicit config: exactly the declared spec for its key; no alternate allocations."""
    if not isinstance(config, dict) or config.get("key") not in SPECS:
        raise ValueError("PANEL must name a declared suite key")
    want = default_config(config["key"])
    if set(config) != set(want):
        raise ValueError(f"PANEL keys differ: missing={sorted(set(want) - set(config))}, "
                         f"unknown={sorted(set(config) - set(want))}")
    for key, value in want.items():
        if json.dumps(config[key], sort_keys=True) != json.dumps(value, sort_keys=True):
            raise ValueError(f"unsupported PANEL value: {key}")
    for key in ("pool", "smoke_pool", "id_prefix", "smoke_prefix"):
        if not re.fullmatch(r"[A-Za-z0-9-]+", config[key]):
            raise ValueError(f"unsafe namespace: {key}")
    return config


def arms(config):
    return tuple(config["arms"])


def plan(config, smoke=False):
    """Canonical allocation, independent of generated content or model output."""
    cfg = validate_config(config)
    corr = cfg["correction_blocks"] > 0
    if smoke:
        return [{"stem": cfg["smoke_prefix"] + f"{i + 1:04d}", "set": "smoke", "block": i, "family": family,
                 "reception": reception, "bits": list(bits), "primary_arrival": True, "primary_correction": corr}
                for i, (family, reception, bits) in enumerate(_SMOKES[cfg["smoke"]])]
    seen, out = collections.Counter(), []
    for block in range(cfg["arrival_blocks"]):
        for family, reception in _BLOCKS[cfg["block"]]:
            cell = seen[(family, reception)] % 4
            seen[(family, reception)] += 1
            out.append({"stem": cfg["id_prefix"] + f"{len(out) + 1:04d}", "set": "main", "block": block,
                        "family": family, "reception": reception, "bits": [cell & 1, (cell >> 1) & 1, 0],
                        "primary_arrival": True, "primary_correction": block < cfg["correction_blocks"]})
    return out


def validate_allocation(rows, config, smoke=False):
    if not isinstance(rows, list) or json.dumps(rows, sort_keys=True) != json.dumps(plan(config, smoke), sort_keys=True):
        raise ValueError("allocation differs from canonical PANEL plan")
    return rows


def expected_targets(allocation, config):
    out = []
    for row in allocation:
        for act in ("arrival", "correction"):
            if not row[f"primary_{act}"]:
                continue
            histories = config["arrival_histories"] if act == "arrival" else list(HO.HISTORIES)
            for direction in (("na",) if act == "arrival" else DIRECTIONS):
                for history in histories:
                    meta = {key: row[key] for key in _META_KEYS}
                    meta.update(group=row["stem"], act=act, direction=direction, history=history,
                                component="smoke" if row["set"] == "smoke" else "primary",
                                stratum=KC.stratum(row["family"], row["reception"]))
                    meta["target"] = f"{row['stem']}|{act}|{direction}|{history}"
                    out.append(meta)
    return out


def allowed_call_ids(allocation, config):
    return {meta["target"] + "|" + arm for meta in expected_targets(allocation, config) for arm in arms(config)}


def insert_line(keep_clar_prompt, sentence):
    """KEEP_CLAR prompt + sentence as its own line directly after the unique ANCHOR_PREFIX query line."""
    lines = keep_clar_prompt.split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith(ANCHOR_PREFIX)]
    if len(hits) != 1 or any(s in keep_clar_prompt for s in SENTENCES.values()):
        raise AssertionError("anchor query line not unique in the KEEP_CLAR prompt")
    return "\n".join(lines[:hits[0] + 1] + [sentence] + lines[hits[0] + 1:])


def strip_line(prompt, sentence):
    line = "\n" + sentence + "\n"
    if prompt.count(sentence) != 1 or prompt.count(line) != 1:
        raise AssertionError("sentence not found exactly once as its own line")
    return prompt.replace(line, "\n")


def prompts_from_public(pub, config):
    """No construction labels, canonical records or hidden values are consulted."""
    prompts, ledger = CL.prompts_from_public(pub)
    keep_clar = prompts["KEEP_CLAR"]
    out = {"KEEP_CLAR": keep_clar}
    for arm in arms(config):
        if arm != "KEEP_CLAR":
            out[arm] = insert_line(keep_clar, SENTENCES[arm])
    if "KEEP_EVT" in out and out["KEEP_EVT"] != ES.event_prompt(keep_clar):
        raise AssertionError("KEEP_EVT differs from the EVT-v1 builder")
    return out, ledger


def schedule(units, seed, arm_list):
    """Shuffle whole stem-act units and arm order; share a seeded cell order across all arms (as EVT-v1)."""
    rng = random.Random(seed)
    units = list(units)
    rng.shuffle(units)
    result = []
    for unit in units:
        if len({(c["stem"], c["act"]) for c in unit}) != 1:
            raise ValueError("schedule unit must be one stem-act")
        order = [arm for arm in arm_list if any(c["arm"] == arm for c in unit)]
        cells = sorted({(c["direction"], c["history"]) for c in unit})
        rng.shuffle(order)
        rng.shuffle(cells)
        arm_order, cell_order = {x: i for i, x in enumerate(order)}, {x: i for i, x in enumerate(cells)}
        if len(unit) != len(order) * len(cells):
            raise ValueError("incomplete schedule unit")
        result.extend(sorted(unit, key=lambda c: (arm_order[c["arm"]], cell_order[(c["direction"], c["history"])])))
    return result


def build_part(allocation, base_seed, pool, config):
    KG.register_pool(pool, config["consonants"])
    publics, hidden, units, rejected = [], [], [], []
    for row in allocation:
        stem = row["stem"]
        targets = expected_targets([row], config)
        for attempt in range(config["max_attempts"]):
            seed = KC.seed_for(base_seed, pool, stem, attempt)
            try:
                group = HO.build_group(stem, seed, row["family"], row["reception"], row["bits"], pool)
                built = []
                for meta in targets:
                    original = group["cases"][(meta["act"], meta["history"])]
                    case = CL.correction_case(original, meta["direction"]) if meta["act"] == "correction" \
                        else copy.deepcopy(original)
                    pub = KG.public_row(meta["target"], group["world"], case, group["render_seed"], meta)
                    prompts, ledger = prompts_from_public(pub, config)
                    if ledger["field"] != case["field"]:
                        raise AssertionError("public identity differs from construction label")
                    pub["identity"] = ledger
                    hid = {**meta, "world_seed": seed, "pool": pool, "render_seed": group["render_seed"],
                           "gold_field": case["field"], "case": case}
                    built.append((pub, hid, prompts))
                break
            except AssertionError as exc:
                rejected.append({"stem": stem, "attempt": attempt, "seed": seed, "reason": str(exc)[:240]})
        else:
            raise AssertionError(f"unable to construct {stem}")
        by_act = {}
        for pub, hid, prompts in built:
            publics.append(pub)
            hidden.append(hid)
            for arm in arms(config):
                call = KG.call(pub["target"] + "|" + arm, arm, pub["history"], prompts[arm], config["max_new_tokens"])
                call.update({key: pub[key] for key in (*_META_KEYS, "target", "group", "act", "direction", "history",
                                                       "component", "stratum")})
                call["system_sha256"] = hashlib.sha256(call["system"].encode()).hexdigest()
                by_act.setdefault(pub["act"], []).append(call)
        units.extend(by_act.values())
    return {"plan": allocation, "public": publics, "hidden": hidden, "units": units, "rejected": rejected}


def generate(config, historical_prompts=(), historical_seeds=(), allocation=None):
    cfg = validate_config(config)
    declared = {part: plan(cfg, smoke=(part == "smoke")) for part in ("main", "smoke")} \
        if allocation is None else allocation
    if set(declared) != {"main", "smoke"}:
        raise ValueError("both main and smoke allocations required")
    out = {}
    for part in ("main", "smoke"):
        validate_allocation(declared[part], cfg, smoke=(part == "smoke"))
        result = build_part(declared[part], cfg["smoke_base_seed" if part == "smoke" else "base_seed"],
                            cfg["smoke_pool" if part == "smoke" else "pool"], cfg)
        result["calls"] = schedule(result.pop("units"), cfg["schedule_seed"] + int(part == "smoke"), arms(cfg))
        if {c["call_id"] for c in result["calls"]} != allowed_call_ids(declared[part], cfg):
            raise AssertionError("generated calls differ from allocation membership")
        if len(result["calls"]) != cfg["smoke_calls" if part == "smoke" else "main_calls"]:
            raise AssertionError("generated call count differs from the declared spec")
        out[part] = result
    prompts = [p["base_prompt"] for result in out.values() for p in result["public"]]
    seeds = {h["stem"]: h["world_seed"] for result in out.values() for h in result["hidden"]}
    ids = [c["call_id"] for result in out.values() for c in result["calls"]]
    filenames = [cid.replace("|", "__") for cid in ids]
    if len(set(prompts)) != len(prompts) or set(prompts) & set(historical_prompts):
        raise AssertionError("repeated BASE prompt in new or historical panel")
    if len(set(seeds.values())) != len(seeds) or set(seeds.values()) & set(historical_seeds):
        raise AssertionError("world seed repeated across stems or historical panel")
    if len(set(ids)) != len(ids) or len(set(filenames)) != len(filenames):
        raise AssertionError("duplicate call id or encoded filename")
    return out


def allowed_manifest(panel):
    keys = ("set", "call_id", "target", "stem", "act", "direction", "history", "arm",
            "system_sha256", "user_sha256", "max_new_tokens")
    return [{key: call[key] for key in keys} for part in ("main", "smoke") for call in panel[part]["calls"]]
