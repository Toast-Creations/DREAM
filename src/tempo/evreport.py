"""EVT-v1 event-reporting development comparison: fixed allocation, prompts and public-only panel construction.

No model or inference. Adapted from ESUB-v1 (tempo.esubject); the V1.23/V1.24 correction reversal, KEEP
annotation and clarification sentence are reused unchanged.

Arms (both on every scheduled target):
  KEEP_CLAR  unchanged V1.24 KEEP annotation + clarification sentence (current)
  KEEP_EVT   KEEP_CLAR + exactly one event-reporting sentence, inserted as its own line directly after the
             query line that begins "List the assertions by category"

Arrival wording is set by bit b1 in the unchanged generator: b1 = 0 gives the result wording ("... was delivered
to you, so it is now on hand"), b1 = 1 the transition wording ("... went from not on hand to on hand: it was
delivered to you"). The within-stratum cycle balances both wordings in every family x reception stratum.

Allocation: 12 blocks of 12 stems (F1 i, F1 d, F2 i, F2 d, then F3 i x4 and F3 d x4) = 144 arrival stems in
F1:F2:F3 = 1:1:4. Corrections use the first 4 blocks (48 stems: F1 8, F2 8, F3 32). Bits b0/b1 cycle over the four cells within each
family x reception stratum (b2 = 0, open intervals only), so every stratum has exact four-cell balance in both the
arrival and the correction panel.
"""
import collections
import copy
import hashlib
import json
import random
import re

from . import clarify as CL, holdout as HO, kidconf as KC, kidconfgen as KG

STUDY = "EVT-v1"
ARMS = ("KEEP_CLAR", "KEEP_EVT")
DIRECTIONS = CL.DIRECTIONS
HISTORIES = HO.HISTORIES
EVENT_SENTENCE = ('If the new record says that a change happened (for example, that something was delivered, '
                  'installed or removed), list that change under "events", even when the record also states the '
                  'value that resulted.')
ANCHOR_PREFIX = "List the assertions by category"
BLOCK = (("F1_two_hop", "immediate"), ("F1_two_hop", "delayed"), ("F2_slot_join", "immediate"),
         ("F2_slot_join", "delayed")) + (("F3_historical_occupant", "immediate"),) * 4 + \
        (("F3_historical_occupant", "delayed"),) * 4
DEFAULT_CONFIG = {
    "study": STUDY, "arrival_blocks": 12, "correction_blocks": 4, "block_size": 12, "smoke_stems": 2,
    "family_ratio": [1, 1, 4], "receptions": ["immediate", "delayed"],
    "bits_rule": "within-stratum-cycle-v1", "b2": 0, "schedule_rule": "stem-act-unit-v1",
    "base_seed": 2026111241, "smoke_base_seed": 2026111242, "schedule_seed": 2026111243,
    "pool": "ev26", "smoke_pool": "ev26s", "consonants": KG.DEFAULT_CONSONANTS,
    "id_prefix": "v26-g", "smoke_prefix": "v26-s", "max_attempts": 300, "max_new_tokens": 256,
    "conditions": list(ARMS), "event_sentence": EVENT_SENTENCE,
}
_VARIABLE_KEYS = {"base_seed", "smoke_base_seed", "schedule_seed", "pool", "smoke_pool", "consonants",
                  "id_prefix", "smoke_prefix", "max_attempts"}
_META_KEYS = ("stem", "set", "block", "family", "reception", "bits", "primary_arrival", "primary_correction")


def validate_config(config):
    """Closed explicit config: no unknown keys or alternate allocations."""
    if not isinstance(config, dict) or set(config) != set(DEFAULT_CONFIG):
        keys = set(config) if isinstance(config, dict) else set()
        raise ValueError(f"PANEL keys differ: missing={sorted(set(DEFAULT_CONFIG) - keys)}, "
                         f"unknown={sorted(keys - set(DEFAULT_CONFIG))}")
    for key, value in DEFAULT_CONFIG.items():
        if key not in _VARIABLE_KEYS and json.dumps(config[key], sort_keys=True) != json.dumps(value, sort_keys=True):
            raise ValueError(f"unsupported fixed PANEL value: {key}")
    for key in ("base_seed", "smoke_base_seed", "schedule_seed", "max_attempts"):
        if type(config[key]) is not int or config[key] <= 0:
            raise ValueError(f"positive integer required: {key}")
    for key in ("pool", "smoke_pool", "id_prefix", "smoke_prefix"):
        if not isinstance(config[key], str) or not re.fullmatch(r"[A-Za-z0-9-]+", config[key]):
            raise ValueError(f"unsafe namespace: {key}")
    if not isinstance(config["consonants"], str) or not re.fullmatch(r"[a-z]+", config["consonants"]) or \
            len(set(config["consonants"])) != len(config["consonants"]):
        raise ValueError("invalid consonants")
    if config["pool"] == config["smoke_pool"] or config["id_prefix"] == config["smoke_prefix"] or \
            config["base_seed"] == config["smoke_base_seed"]:
        raise ValueError("main and smoke namespaces/seeds must differ")
    return config


def plan(config=None, smoke=False):
    """Canonical allocation, independent of generated content or model output."""
    cfg = validate_config(copy.deepcopy(DEFAULT_CONFIG) if config is None else config)
    if smoke:
        return [{"stem": cfg["smoke_prefix"] + f"{i + 1:04d}", "set": "smoke", "block": i,
                 "family": family, "reception": reception, "bits": bits,
                 "primary_arrival": True, "primary_correction": True}
                for i, (family, reception, bits) in enumerate((("F2_slot_join", "immediate", [0, 0, 0]),
                                                              ("F3_historical_occupant", "delayed", [0, 1, 0])))]
    seen, out = collections.Counter(), []
    for block in range(cfg["arrival_blocks"]):
        for family, reception in BLOCK:
            cell = seen[(family, reception)] % 4
            seen[(family, reception)] += 1
            out.append({"stem": cfg["id_prefix"] + f"{len(out) + 1:04d}", "set": "main", "block": block,
                        "family": family, "reception": reception, "bits": [cell & 1, (cell >> 1) & 1, 0],
                        "primary_arrival": True, "primary_correction": block < cfg["correction_blocks"]})
    return out


def validate_allocation(rows, config=None, smoke=False):
    if not isinstance(rows, list) or json.dumps(rows, sort_keys=True) != json.dumps(plan(config, smoke), sort_keys=True):
        raise ValueError("allocation differs from canonical PANEL plan")
    return rows


def allowed_arms(row, act):
    if act not in ("arrival", "correction"):
        raise ValueError("unsupported act")
    return ARMS if row[f"primary_{act}"] else ()


def expected_targets(allocation):
    out = []
    for row in allocation:
        for act in ("arrival", "correction"):
            if not row[f"primary_{act}"]:
                continue
            for direction in (("na",) if act == "arrival" else DIRECTIONS):
                for history in HISTORIES:
                    meta = {key: row[key] for key in _META_KEYS}
                    meta.update(group=row["stem"], act=act, direction=direction, history=history,
                                component="smoke" if row["set"] == "smoke" else "primary",
                                stratum=KC.stratum(row["family"], row["reception"]))
                    meta["target"] = f"{row['stem']}|{act}|{direction}|{history}"
                    out.append(meta)
    return out


def allowed_call_ids(allocation):
    return {meta["target"] + "|" + arm for meta in expected_targets(allocation)
            for arm in allowed_arms(meta, meta["act"])}


def event_prompt(keep_clar_prompt):
    """KEEP_CLAR prompt + EVENT_SENTENCE as its own line directly after the unique ANCHOR_PREFIX query line."""
    lines = keep_clar_prompt.split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith(ANCHOR_PREFIX)]
    if len(hits) != 1 or EVENT_SENTENCE in keep_clar_prompt:
        raise AssertionError("anchor query line not unique in the KEEP_CLAR prompt")
    return "\n".join(lines[:hits[0] + 1] + [EVENT_SENTENCE] + lines[hits[0] + 1:])


def strip_event(keep_evt_prompt):
    """Inverse used by validation: removing exactly the sentence line must give back the KEEP_CLAR prompt."""
    line = "\n" + EVENT_SENTENCE + "\n"
    if keep_evt_prompt.count(EVENT_SENTENCE) != 1 or keep_evt_prompt.count(line) != 1:
        raise AssertionError("event sentence not found exactly once as its own line")
    return keep_evt_prompt.replace(line, "\n")


def wording(bits):
    """Arrival wording label from the public allocation bit b1 (see module docstring)."""
    return "TRANSITION" if bits[1] else "RESULT"


def prompts_from_public(pub):
    """No construction labels, canonical records or hidden values are consulted."""
    prompts, ledger = CL.prompts_from_public(pub)
    keep_clar = prompts["KEEP_CLAR"]
    return {"KEEP_CLAR": keep_clar, "KEEP_EVT": event_prompt(keep_clar)}, ledger


def schedule(units, seed):
    """Shuffle whole stem-act units and condition order; share a seeded cell order across all conditions."""
    rng = random.Random(seed)
    units = list(units)
    rng.shuffle(units)
    result = []
    for unit in units:
        if len({(c["stem"], c["act"]) for c in unit}) != 1:
            raise ValueError("schedule unit must be one stem-act")
        arms = [arm for arm in ARMS if any(c["arm"] == arm for c in unit)]
        cells = sorted({(c["direction"], c["history"]) for c in unit})
        rng.shuffle(arms)
        rng.shuffle(cells)
        arm_order, cell_order = {x: i for i, x in enumerate(arms)}, {x: i for i, x in enumerate(cells)}
        if len(unit) != len(arms) * len(cells):
            raise ValueError("incomplete schedule unit")
        result.extend(sorted(unit, key=lambda c: (arm_order[c["arm"]], cell_order[(c["direction"], c["history"])])))
    return result


def build_part(allocation, base_seed, pool, config):
    KG.register_pool(pool, config["consonants"])
    publics, hidden, units, rejected = [], [], [], []
    for row in allocation:
        stem = row["stem"]
        targets = expected_targets([row])
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
                    prompts, ledger = prompts_from_public(pub)
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
            for arm in allowed_arms(pub, pub["act"]):
                call = KG.call(pub["target"] + "|" + arm, arm, pub["history"], prompts[arm], config["max_new_tokens"])
                call.update({key: pub[key] for key in (*_META_KEYS, "target", "group", "act", "direction", "history",
                                                       "component", "stratum")})
                call["system_sha256"] = hashlib.sha256(call["system"].encode()).hexdigest()
                by_act.setdefault(pub["act"], []).append(call)
        units.extend(by_act.values())
    return {"plan": allocation, "public": publics, "hidden": hidden, "units": units, "rejected": rejected}


def generate(config=None, historical_prompts=(), historical_seeds=(), allocation=None):
    cfg = validate_config(copy.deepcopy(DEFAULT_CONFIG) if config is None else config)
    declared = {part: plan(cfg, smoke=(part == "smoke")) for part in ("main", "smoke")} \
        if allocation is None else allocation
    if set(declared) != {"main", "smoke"}:
        raise ValueError("both main and smoke allocations required")
    out = {}
    for part in ("main", "smoke"):
        validate_allocation(declared[part], cfg, smoke=(part == "smoke"))
        result = build_part(declared[part], cfg["smoke_base_seed" if part == "smoke" else "base_seed"],
                            cfg["smoke_pool" if part == "smoke" else "pool"], cfg)
        result["calls"] = schedule(result.pop("units"), cfg["schedule_seed"] + int(part == "smoke"))
        if {c["call_id"] for c in result["calls"]} != allowed_call_ids(declared[part]):
            raise AssertionError("generated calls differ from allocation membership")
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
