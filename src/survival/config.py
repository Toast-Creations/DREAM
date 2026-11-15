"""Schema 1.4.0 "survival" configuration: inference-only idea-survival chains (no training, no adapters).

modes:
  chains  - ideation (arm) -> development (unsteered) -> finalization (unsteered), test 4/5.
  devqual - fork an existing starting ledger through two budget-matched two-call branches, test 3.
  continuity (V1.5.0, schema "1.5.0") - ONE continuous generation per chain (ideas, thinking, development,
      final) so processing happens in the same context while the dose returns to baseline. Arms:
      baseline; perceive_* (the task text is read under steering, then decode glides to zero);
      generate_* (task read at baseline; ideas written under steering, then glide to zero).
"""
from pathlib import Path
from dream_core.contracts import finite_number, integer
from dream_core.schedules import validate_spec

ARMS = ("strong_prompt", "high_temperature", "targeted", "random")
CONT_ARMS = ("baseline", "perceive_targeted", "perceive_random", "generate_targeted", "generate_random")
WORKFLOWS = ("develop", "review")
STAGE_KEYS = ("ideation", "development", "final")


def validate_survival(cfg, path):
    path = Path(path)
    s = cfg["survival"]
    if s.get("mode") not in ("chains", "devqual", "continuity"):
        raise ValueError("survival.mode must be chains, devqual or continuity")
    if (s["mode"] == "continuity") != (cfg.get("version") == "1.5.0"):
        raise ValueError("continuity mode is schema 1.5.0 only, and 1.5.0 is continuity only")
    if cfg["model"].get("enable_thinking", False) is not False:
        raise ValueError("Idea-survival runs use reasoning off (or a model without a reasoning switch)")
    lim = cfg["limits"]
    integer(lim["max_new_tokens"], "max_new_tokens", 64, 8192)
    stage_caps = lim["stage_input_tokens"]
    keys = ("continuous",) if s["mode"] == "continuity" else STAGE_KEYS
    if set(stage_caps) != set(keys):
        raise ValueError("limits.stage_input_tokens needs exactly " + ", ".join(keys))
    for key in keys:
        integer(stage_caps[key], f"{key} input cap", 64, 32768)
    integer(lim.get("external_retries", 1), "external_retries", 0, 1)
    guard = lim.get("loop_guard")
    if guard is not None:
        if not isinstance(guard, dict) or set(guard) - {"window_tokens", "ngram", "repeat_share", "check_every", "_note"}:
            raise ValueError("limits.loop_guard takes window_tokens, ngram, repeat_share and check_every")
        integer(guard["window_tokens"], "loop window", 64, lim["max_new_tokens"])
        integer(guard["ngram"], "loop n-gram", 2, guard["window_tokens"] // 4)
        finite_number(guard["repeat_share"], "loop repeat share", 0.5, 1)
        integer(guard["check_every"], "loop check interval", 1, guard["window_tokens"])
    gen = cfg["generation"]
    for key in ("temperature",) if s["mode"] == "continuity" else ("temperature", "high_temperature"):
        finite_number(gen[key], key, 1e-8, 3)
    finite_number(gen["top_p"], "top_p", 1e-8, 1)
    integer(gen["top_k"], "top_k", 1, 1000)
    integer(s["order_seed"], "order_seed", 0, 2**31 - 1)
    if s["mode"] == "chains":
        arms = s["arms"]
        if not arms or len(arms) != len(set(arms)) or any(a not in ARMS for a in arms):
            raise ValueError("Arms must be distinct members of " + ", ".join(ARMS))
        if s.get("workflow") not in WORKFLOWS:
            raise ValueError("survival.workflow must be develop or review")
        st = cfg["steering"]
        cap = finite_number(st["max_abs_strength"], "max_abs_strength", 1e-8, 0.6)
        if {"targeted", "random"} & set(arms):
            finite_number(st["peak_strength"], "peak_strength", 0, cap)
            spec = validate_spec(st["schedule"])
            if spec["shape"] == "constant":
                raise ValueError("The temporary arm needs a curve that returns to zero")
        if "targeted" in arms and not st.get("vector_path"):
            raise ValueError("Targeted arm needs a pinned vector artifact")
        if "random" in arms:
            if not st.get("random_set_dir"):
                raise ValueError("Random arm needs the frozen random-direction set")
            integer(st["random_count"], "random_count", 1, 64)
    elif s["mode"] == "continuity":
        arms = s["arms"]
        if not arms or len(arms) != len(set(arms)) or any(a not in CONT_ARMS for a in arms):
            raise ValueError("Arms must be distinct members of " + ", ".join(CONT_ARMS))
        st = cfg["steering"]
        cap = finite_number(st["max_abs_strength"], "max_abs_strength", 1e-8, 0.6)
        if any(a.startswith("perceive") for a in arms):
            per = st["perceive"]
            finite_number(per["prefill_strength"], "perceive prefill_strength", 0, cap)
            spec = validate_spec(per["schedule"])
            if spec["shape"] != "release" or spec["end_fraction"] != 0:
                raise ValueError("Perceive decode schedule must be a release glide to exactly zero")
        if any(a.startswith("generate") for a in arms):
            gen_st = st["generate"]
            finite_number(gen_st["peak_strength"], "generate peak_strength", 0, cap)
            if validate_spec(gen_st["schedule"])["shape"] in ("constant", "release"):
                raise ValueError("Generate schedule must rise and return to zero")
        if any(a.endswith("targeted") for a in arms) and not st.get("vector_path"):
            raise ValueError("Targeted arms need a pinned vector artifact")
        if any(a.endswith("random") for a in arms):
            if not st.get("random_set_dir"):
                raise ValueError("Random arms need the frozen random-direction set")
            integer(st["random_count"], "random_count", 1, 64)
        if not isinstance(s.get("category_probe", False), bool):
            raise ValueError("survival.category_probe must be true or false")
    else:
        if s.get("branches") != ["develop", "review"] and s.get("branches") != ["review", "develop"]:
            raise ValueError("devqual compares exactly the develop and review branches")
    # Paths are relative to the config file, as elsewhere.
    for key in ("data_path", "output_dir"):
        cfg[key] = str((path.parent / cfg[key]).resolve())
    for key in ("path", "manifest"):
        if cfg["model"].get(key):
            cfg["model"][key] = str((path.parent / cfg["model"][key]).resolve())
    for key in ("vector_path", "random_vector_path", "random_set_dir"):
        if cfg["steering"].get(key):
            cfg["steering"][key] = str((path.parent / cfg["steering"][key]).resolve())
    return cfg
