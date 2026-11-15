"""JSON configuration with fail-closed bounds and paths relative to its file."""
import json
from pathlib import Path
from .contracts import finite_number, integer


def load_config(path):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    # Schema 1.1.0 keeps every earlier experiment unchanged; schema 1.2.0 is
    # only the decategorization study, which adds signed doses and schedules.
    if not ((cfg.get("version") == "1.1.0" and cfg.get("experiment") in ("dream", "dream2", "dream2_concepts", "concept_association"))
            or (cfg.get("version") == "1.2.0" and cfg.get("experiment") == "decategorization")
            or (cfg.get("version") in ("1.4.0", "1.5.0") and cfg.get("experiment") == "survival")):
        raise ValueError("Supported schema version and experiment required")
    if cfg.get("phase") not in ("development", "validation", "test"):
        raise ValueError("Declare an evaluation phase")
    limits = cfg["limits"]
    for key, high in (("max_trials", 100000), ("max_seconds", 86400), ("max_input_tokens", 8192),
                      ("max_new_tokens", 8192), ("max_worlds", 10000)):
        integer(limits[key], key, maximum=high)
    if limits["max_input_tokens"] < 8:
        raise ValueError("Input token cap is too small")
    if not cfg["seeds"] or len(set(cfg["seeds"])) != len(cfg["seeds"]):
        raise ValueError("Seeds must be nonempty and distinct")
    for seed in cfg["seeds"]:
        integer(seed, "seed", 0, 2**31-1)
    integer(cfg["steering"]["layer_index"], "layer_index", -10000, 10000)
    if cfg["experiment"] == "survival":
        # V1.4.0: inference-only idea survival has its own bounds and path handling.
        from survival.config import validate_survival
        return validate_survival(cfg, path)
    if cfg["experiment"] == "decategorization":
        validate_decategorization(cfg)
    else:
        values = cfg["steering"]["lambda_values"]
        if not values or 0.0 not in values or len(values) != len(set(values)):
            raise ValueError("Include one identical zero-steering control")
        for value in values:
            finite_number(value, "lambda", 0, 1)
    if cfg["experiment"] == "decategorization":
        pass  # Fully checked by validate_decategorization above.
    elif cfg["experiment"] in ("dream2", "dream2_concepts"):
        if (not cfg["plasticity"]["eta_values"] or 0 not in cfg["plasticity"]["eta_values"] or
                len(set(cfg["plasticity"]["eta_values"])) != len(cfg["plasticity"]["eta_values"])):
            raise ValueError("Include no-update control")
        for value in cfg["plasticity"]["eta_values"]:
            finite_number(value, "eta", 0, 10)
        finite_number(cfg["adapter"]["base_learning_rate"], "learning rate", 1e-8, .1)
        finite_number(cfg["adapter"]["max_grad_norm"], "gradient cap", 1e-8, 100)
        integer(cfg["adapter"]["steps_per_example"], "steps per example", 1, 100)
        integer(cfg["adapter"]["rank"], "rank", 1, 256)
        integer(cfg["adapter"]["alpha"], "alpha", 1, 1024)
        if not cfg["adapter"]["target_modules"] or any(not isinstance(x,str) or not x for x in cfg["adapter"]["target_modules"]):
            raise ValueError("Nonempty target module names are required")
        if cfg["adapter"].get("optimizer") not in ("adamw", "sgd"):
            raise ValueError("Explicit AdamW or SGD policy required")
        if cfg["experiment"] == "dream2_concepts":
            validate_concept_evaluation(cfg)
    elif cfg["experiment"] == "concept_association":
        modes = cfg["association"]["reasoning_modes"]
        if len(modes) != 2 or any(type(x) is not bool for x in modes) or set(modes) != {False, True}:
            raise ValueError("Concept comparison requires both explicit Boolean reasoning modes")
        if cfg["phase"] != "development":
            raise ValueError("V1.1.4 concept study is development-only")
        for key in ("include_temperature_control", "halt_on_invalid"):
            if type(cfg["association"][key]) is not bool:
                raise ValueError("Association policies must be explicit Booleans")
        for key in ("temperature", "high_temperature"):
            finite_number(cfg["generation"][key], key, 1e-8, 3)
        finite_number(cfg["generation"]["top_p"], "top_p", 1e-8, 1)
        integer(cfg["generation"]["top_k"], "top_k", 1, 1000)
        if cfg["steering"].get("schedule"):
            raise ValueError("Concept comparison uses constant steering, independent of the answer cap")
        if type(cfg["association"].get("include_random_direction_control", False)) is not bool:
            raise ValueError("Random-direction control must be an explicit Boolean")
        if cfg["association"].get("include_random_direction_control", False):
            finite_number(cfg["association"]["random_direction_strength"], "random direction strength", 1e-8, 1)
            if not cfg["steering"].get("random_vector_path"):
                raise ValueError("A separate pinned random-direction artifact is required")
    else:
        for key in ("temperature", "high_temperature", "integration_temperature"):
            finite_number(cfg["generation"][key], key, 0, 3)
        finite_number(cfg["generation"]["top_p"], "top_p", 1e-8, 1)
        for step in ("anchor", "integration"):
            if cfg["generation"].get(step) is not None:
                validate_sampling(cfg["generation"][step], f"generation.{step}")
    validate_extra_arms(cfg)
    validate_loop_guard(cfg)
    for key in ("data_path", "output_dir"):
        cfg[key] = str((path.parent / cfg[key]).resolve())
    for key in ("path", "manifest"):
        if cfg["model"].get(key):
            cfg["model"][key] = str((path.parent / cfg["model"][key]).resolve())
    if cfg["steering"].get("vector_path"):
        cfg["steering"]["vector_path"] = str((path.parent / cfg["steering"]["vector_path"]).resolve())
    for key in ("random_vector_path", "divergent_vector_path"):
        if cfg["steering"].get(key):
            cfg["steering"][key] = str((path.parent / cfg["steering"][key]).resolve())
    for arm in cfg["steering"].get("extra_arms", []):
        arm["vector_path"] = str((path.parent / arm["vector_path"]).resolve())
    return cfg


def validate_sampling(spec, label):
    """A seeded sampling preset: temperature, top_p and optional top_k (V1.3.2/1.3.3)."""
    if not isinstance(spec, dict) or set(spec) - {"temperature", "top_p", "top_k", "_note"}:
        raise ValueError(f"{label} takes only temperature, top_p and top_k")
    finite_number(spec["temperature"], f"{label} temperature", 1e-8, 3)
    finite_number(spec["top_p"], f"{label} top_p", 1e-8, 1)
    if spec.get("top_k") is not None:
        integer(spec["top_k"], f"{label} top_k", 1, 1000)


def validate_loop_guard(cfg):
    """V1.3.3 limits.loop_guard: stop a generation whose recent tokens repeat (calibration in document 19)."""
    guard = cfg["limits"].get("loop_guard")
    if guard is None:
        return
    if cfg["experiment"] not in ("dream", "dream2_concepts"):
        raise ValueError("limits.loop_guard is a DREAM / DREAM 2 concepts setting")
    if not isinstance(guard, dict) or set(guard) - {"window_tokens", "ngram", "repeat_share", "check_every", "_note"}:
        raise ValueError("limits.loop_guard takes window_tokens, ngram, repeat_share and check_every")
    integer(guard["window_tokens"], "loop window", 64, cfg["limits"]["max_new_tokens"])
    integer(guard["ngram"], "loop n-gram", 2, guard["window_tokens"] // 4)
    finite_number(guard["repeat_share"], "loop repeat share", 0.5, 1)
    integer(guard["check_every"], "loop check interval", 1, guard["window_tokens"])


def validate_extra_arms(cfg):
    """V1.3.3 extra steering arms: a named vector of a required kind at one positive dose."""
    arms = cfg["steering"].get("extra_arms", [])
    if not arms:
        return
    if cfg["experiment"] not in ("dream", "dream2_concepts"):
        raise ValueError("steering.extra_arms is a DREAM / DREAM 2 concepts setting")
    if type(arms) is not list:
        raise ValueError("steering.extra_arms must be a list")
    names = []
    for arm in arms:
        if not isinstance(arm, dict) or set(arm) - {"name", "vector_path", "kind", "lambda", "_note"}:
            raise ValueError("Each extra arm takes name, vector_path, kind and lambda")
        if type(arm.get("name")) is not str or not arm["name"].isidentifier() or arm["name"] in ("divergent", "semantic"):
            raise ValueError("Extra arm names must be new identifiers")
        if any(type(arm.get(k)) is not str or not arm[k] for k in ("vector_path", "kind")):
            raise ValueError("Extra arms need a vector path and a required vector kind")
        finite_number(arm["lambda"], "extra arm lambda", 1e-8, 1)
        names.append(arm["name"])
    if len(set(names)) != len(names):
        raise ValueError("Extra arm names must be distinct")


def validate_concept_evaluation(cfg):
    """V1.3.3 DREAM 2 concept learning: evaluation modes and their sampling presets."""
    evaluation = cfg["evaluation"]
    modes = evaluation["reasoning_modes"]
    if not modes or any(type(x) is not bool for x in modes) or len(set(modes)) != len(modes):
        raise ValueError("Concept evaluation needs distinct Boolean reasoning modes")
    for mode in modes:
        validate_sampling(evaluation["sampling"]["thinking" if mode else "direct"],
                          f"evaluation.sampling.{'thinking' if mode else 'direct'}")
    if cfg["plasticity"].get("high_eta") is not None:
        raise ValueError("The concept pilot declares no high-plasticity cell")
    if cfg["gate"].get("enabled", False):
        raise ValueError("Concept learning has no automatic consolidation gate; ratings are blinded review")


def validate_ladder(cfg, cap, used):
    """V1.3.1 explore ladders: known roles ending in ground; each named ladder
    gives one more level than roles, never rising, within the cap."""
    from dream.decategorization import EXPLORE_ROLES
    ladder = cfg["ladder"]
    roles, levels = ladder["roles"], ladder["levels"]
    if type(roles) is not list or not 2 <= len(roles) <= 8 or any(r not in EXPLORE_ROLES for r in roles):
        raise ValueError("The explore ladder needs 2 to 8 known roles")
    if roles.count("ground") != 1 or roles[-1] != "ground":
        raise ValueError("Exactly one ground role, and it must be last")
    if type(levels) is not dict or not set(used) <= set(levels):
        raise ValueError("Every ladder an arm uses must be listed in ladder.levels")
    for name, values in levels.items():
        if type(values) is not list or len(values) != len(roles) + 1:
            raise ValueError(f"Ladder {name} needs one more level than roles")
        for value in values:
            finite_number(value, f"ladder {name} level", 0, cap)
        if any(b > a for a, b in zip(values, values[1:])) or values[0] <= 0:
            raise ValueError(f"Ladder {name} must start above zero and never rise")
    integer(ladder["glide_tokens"], "glide_tokens", 1, 8192)
    integer(ladder["max_new_tokens"], "ladder max_new_tokens", 8, 8192)
    integer(ladder["max_input_tokens"], "ladder max_input_tokens", 8, 8192)
    finite_number(ladder["temperature"], "ladder temperature", 1e-8, 3)


def validate_decategorization(cfg):
    """V1.2.0 bounds: signed doses capped by max_abs_strength, a zero arm, valid curves."""
    from dream.decategorization import CONDITIONS, VECTOR_KINDS, conditions
    from .schedules import validate_spec, validate_temperature_schedule
    if cfg["phase"] != "development":
        raise ValueError("V1.2.0 decategorization study is development-only")
    if cfg["model"].get("enable_thinking", False) is not False:
        raise ValueError("Decategorization arms run with reasoning off")
    # V1.3.1 raised the ceiling from 0.5 to 0.6 for the ladder start test that
    # David requested; each config still sets its own lower cap.
    cap = finite_number(cfg["steering"]["max_abs_strength"], "max_abs_strength", 1e-8, 0.6)
    trip = cfg["trip"]
    finite_number(trip["peak_strength"], "peak_strength", 1e-8, cap)
    validate_spec({k: trip[k] for k in ("shape", "onset_tokens", "plateau_tokens", "comedown_tokens")})
    if trip["shape"] == "constant":
        raise ValueError("The trip curve must rise and fall; constant dose is its own arm")
    validate_temperature_schedule(cfg["temperature_anneal"])
    d = cfg["decategorization"]
    names = d["conditions"]
    if len(names) != len(set(names)) or any(n not in CONDITIONS for n in names):
        raise ValueError("Conditions must be distinct known arm names")
    sweep = d.get("dose_sweep", [])
    if len(sweep) != len(set(sweep)):
        raise ValueError("Dose sweep values must be distinct")
    for value in sweep:
        finite_number(value, "dose", -cap, cap)
    if type(d["halt_on_invalid"]) is not bool:
        raise ValueError("halt_on_invalid must be an explicit Boolean")
    cells = conditions(cfg)
    if not cells or not any(c["lambda"] == 0 and c["temperature_schedule"] is None and not c["sober_pass"]
                            and not c["explore"] for c in cells):
        raise ValueError("Include one identical zero-steering control")
    if any(c["explore"] for c in cells):
        validate_ladder(cfg, cap, {c["explore"][1] for c in cells if c["explore"] and c["explore"][1]})
        if any(c["explore"][0] != "flat" for c in cells if c["explore"]) and not any(
                c["explore"] and c["explore"][0] == "flat" for c in cells):
            raise ValueError("Ladder arms need a flat (unsteered) explore control")
    if any(c["sober_pass"] for c in cells) and "two_step_control" not in names:
        raise ValueError("Sober-pass arms need the zero-dose two-step control")
    for kind in {c["vector_kind"] for c in cells} - {"none"}:
        if not cfg["steering"].get(VECTOR_KINDS[kind][0]):
            raise ValueError(f"A pinned {kind} vector artifact is required")
    for key in ("temperature", "sober_temperature"):
        finite_number(cfg["generation"][key], key, 1e-8, 3)
    finite_number(cfg["generation"]["top_p"], "top_p", 1e-8, 1)
    integer(cfg["generation"]["top_k"], "top_k", 1, 1000)
    for key in ("sober_max_input_tokens", "sober_max_new_tokens"):
        integer(cfg["limits"][key], key, 8, 8192)
