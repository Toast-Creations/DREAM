"""Budget calculations that never import or load a model."""


def trial_count(cfg, count):
    if count <= 0:
        raise ValueError("The declared phase has no benchmark items")
    if cfg["experiment"] == "survival":
        from survival.runner import load_rows, unit_count
        return unit_count(cfg, load_rows(cfg["data_path"], cfg["phase"]))
    if cfg["experiment"] == "decategorization":
        from dream.decategorization import conditions
        # One record per cell; sober passes are a second call inside that record.
        return len(conditions(cfg))*count*len(cfg["seeds"])
    lambdas = cfg["steering"]["lambda_values"]
    extra = len(cfg["steering"].get("extra_arms", []))
    cells = len(lambdas) + 1 + extra
    if cfg["experiment"] == "concept_association":
        cells = (len(lambdas) + int(cfg["association"]["include_temperature_control"])
                 + int(cfg["association"].get("include_random_direction_control", False))) * len(cfg["association"]["reasoning_modes"])
    if cfg["experiment"] in ("dream2", "dream2_concepts"):
        etas = cfg["plasticity"]["eta_values"]
        # V1.3.3: one coupled cell per extra arm and positive eta.
        cells = len(lambdas)*len(etas) + extra*sum(x > 0 for x in etas)
        if cfg["plasticity"].get("preexposure_control", True):
            cells += sum(x > 0 for x in lambdas)*sum(x > 0 for x in etas)
        cells += cfg["plasticity"].get("high_eta") is not None
    return cells*count*len(cfg["seeds"])
