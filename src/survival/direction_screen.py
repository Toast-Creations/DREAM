"""V1.5.1 direction screen: does any steering direction, read under perceive-mode steering, loosen categories and
make descriptions more abstract than random directions do? Criteria: Runs/idea-survival-20261031/output/continuity/
DIRECTION-SCREEN-CRITERIA.md (fixed before running). Inference only; outputs are raw text, scored host-side.

Candidates per layer: D0 (instruction contrast, last prompt token = the 1.2.x method), D1 (same poles, averaged over
the model's own generated answer), D2 (abstract/poetic minus concrete/literal descriptions, generated-text pooled),
plus nine Gaussian random directions (seeds 271828-271836, the frozen-set procedure).
"""
import json
from pathlib import Path
import time

LAYERS = (-12, -8, -4)
STRENGTHS = (0.10, 0.20)
RANDOM_SEEDS = tuple(range(271828, 271837))
CAT_TOKENS, DESC_TOKENS, BUILD_TOKENS = 48, 96, 80

# Held-out screen objects: not in data/decategorization_prompts.json, not a subject of any pilot, smoke, judge-
# qualification or sealed confirmation task.
SCREEN_OBJECTS = (
    ("salt shaker", "a small container with a perforated cap for sprinkling salt"),
    ("paper lantern", "a folded paper shade around a small light, hung from a cord"),
    ("garden hose", "a long flexible tube that carries water from a tap"),
    ("chess knight", "a carved playing piece that moves in an L-shape"),
    ("birdcage", "a frame of thin bars with a door and a perch"),
    ("doorbell", "a button by a door that rings a chime inside"),
    ("rope bridge", "a walkway of planks hung from ropes across a gap"),
    ("fountain pen", "a pen that draws ink from a reservoir through a metal nib"),
    ("bookshelf", "a set of horizontal boards that hold books upright"),
    ("traffic light", "a post with red, amber and green lamps that control traffic"),
    ("harbour buoy", "a floating marker anchored in water to guide boats"),
    ("wind chime", "hanging tubes that ring when the wind moves them"),
    ("spinning top", "a toy that balances on a point while it spins"),
    ("mailbox", "a lidded box where letters are left for collection"),
    ("tuning fork", "a two-pronged metal fork that rings at one pitch"),
    ("hammock", "a net or cloth bed hung between two supports"),
    ("scarecrow", "a stuffed figure in old clothes set up in a field"),
    ("trellis", "a lattice frame that climbing plants grow along"),
    ("magnifying glass", "a handheld lens that makes small things look larger"),
    ("snow globe", "a sealed glass ball of water and flakes around a small scene"),
    ("abacus", "a frame of rods with sliding beads used for counting"),
    ("bread oven", "a brick chamber heated by fire for baking loaves"),
    ("bus shelter", "a roofed stand where people wait for buses"),
    ("metronome", "a device that ticks at a steady, adjustable tempo"),
)

# V1.5.2: second held-out set for replication of any passing cell (listed before any 1.5.2 run).
SCREEN_OBJECTS_B = (
    ("watering can", "a container with a long spout for watering plants"),
    ("coat hanger", "a shaped hook of wire or wood for hanging clothes"),
    ("rolling pin", "a smooth cylinder rolled over dough to flatten it"),
    ("door knocker", "a hinged metal ring on a door, struck to announce a visitor"),
    ("sundial", "a plate with a raised pointer whose shadow shows the time"),
    ("wheelbarrow", "a one-wheeled cart pushed by two handles"),
    ("music stand", "an adjustable stand that holds sheet music"),
    ("chalkboard", "a dark board written on with chalk and wiped clean"),
    ("fishing rod", "a long flexible pole with a line and reel"),
    ("ice skate", "a boot with a metal blade for gliding on ice"),
    ("broom", "a bundle of bristles on a long handle for sweeping"),
    ("thimble", "a small cap worn on a fingertip when sewing"),
    ("kaleidoscope", "a tube of mirrors that turns coloured pieces into patterns"),
    ("pinwheel", "a paper wheel on a stick that spins in the wind"),
    ("stethoscope", "a device that carries body sounds to the listener's ears"),
    ("typewriter", "a machine that prints letters when keys are struck"),
    ("suitcase", "a rigid case with a handle for carrying clothes on a journey"),
    ("lamppost", "a tall post with a light that lights a street"),
    ("rocking chair", "a chair on curved runners that sways back and forth"),
    ("telescope", "a tube of lenses that makes distant things look near"),
    ("paperweight", "a heavy object that keeps papers from blowing away"),
    ("picnic blanket", "a cloth spread on the ground to sit and eat on"),
    ("diving board", "a springy plank that people jump from into a pool"),
    ("cookie cutter", "a shaped metal edge pressed into dough to cut shapes"),
)
OBJECT_SETS = {"A": SCREEN_OBJECTS, "B": SCREEN_OBJECTS_B}

# V1.5.3: method P (prompt wording). Verbatim from output/continuity/WRITE-AND-PROMPT-SCREEN-CRITERIA.md.
# Candidates contain no style words; N0-N8 are the matched neutral null.
PREAMBLES = {
    "P0": "Before you answer, let go of the usual labels for this object. Notice its shapes, motions, materials and "
          "effects as if you had never seen one and did not know what it is for.",
    "P1": "Hold this object loosely in mind: set aside what kind of thing it is supposed to be, and attend to what it "
          "resembles, what it does to its surroundings, and what else it could belong with.",
    "P2": "Approach this object without sorting it into its familiar groups. Let its features connect freely to things "
          "from very different domains before you answer.",
    "N0": "Before you answer, read the object's name and description carefully, and make sure your reply follows the "
          "requested format exactly.",
    "N1": "Take a moment to consider the object described below, then answer the question that follows it as clearly "
          "and accurately as you can.",
    "N2": "Please answer the following question about an everyday object. Read the whole entry first, and keep your "
          "reply to the format that is asked for.",
    "N3": "Here is a short entry about an object, followed by a question. Answer the question directly, using the "
          "information in the entry and your general knowledge.",
    "N4": "Consider the object in the entry below, then give the answer that the question requests, keeping to the "
          "format and length it asks for.",
    "N5": "The next message contains an object and a question about it. Read both parts, then reply in the way the "
          "question specifies, without extra commentary.",
    "N6": "Answer the question below about the given object. Be accurate and helpful, and make sure your reply matches "
          "the requested length and format.",
    "N7": "Look at the object named below together with its short description, and respond to the request that "
          "follows as a careful, knowledgeable assistant would.",
    "N8": "Below is an object and a brief description of it. Please read them, think about the object for a moment, "
          "and then complete the task that is asked.",
}
STYLE_WORDS = ("abstract", "poetic", "figurative", "metaphor", "image", "lyrical")
MODES = ("perceive", "generate", "prompt")

D2_POLES = ("abstract", "concrete")
D2_TEMPLATES = (
    ("Describe the {o} in abstract, poetic, figurative language, as an image or idea rather than a thing.",
     "Describe the {o} in plain, literal, concrete terms: what it is made of and how it is used."),
)


def object_line(name, desc):
    return f"{name}: {desc}"


def probe_user(kind, name, desc, preamble=None):
    line = object_line(name, desc)
    ask = ("List five categories that this object belongs to. Reply with one comma-separated line and nothing else."
           if kind == "categories" else "Describe this object in two sentences.")
    head = f"{preamble}\n\n" if preamble else ""
    user = f"{head}Object: {line}\n\n{ask}"
    start = len(head) + len("Object: ")
    assert user[start:start + len(line)] == line
    return user, (start, start + len(line))


def d1_pairs(build):
    return [(p["decategorized"], p["categorical"]) for p in build]


def d2_pairs(build):
    objects = sorted({p["object"] for p in build})
    return [(a.format(o=o), b.format(o=o)) for o in objects for a, b in D2_TEMPLATES]


def random_vectors(hidden):
    import torch
    out = []
    for seed in RANDOM_SEEDS:
        g = torch.Generator(device="cpu").manual_seed(seed)
        v = torch.randn(hidden, generator=g, dtype=torch.float32)
        out.append((f"R{seed - RANDOM_SEEDS[0]}", seed, v / v.norm()))
    return out


def generated_pool(model, tokenizer, prompt, layers, max_new_tokens=BUILD_TOKENS):
    """Greedy-generate the model's answer to ``prompt``; return (text, {layer: mean hidden over generated tokens})."""
    import torch
    from dream_core import modeling
    from dream_core.steering import blocks, hidden_tensor, resolve_layer
    out = modeling.generate(model, tokenizer, prompt, max_input_tokens=512, max_new_tokens=max_new_tokens,
                            temperature=0.0)
    rendered = modeling.render_chat(tokenizer, prompt)
    p_ids = tokenizer(rendered, return_tensors="pt", add_special_tokens=False)["input_ids"]
    g_ids = tokenizer(out["raw_text"], return_tensors="pt", add_special_tokens=False)["input_ids"]
    if g_ids.shape[1] == 0:
        raise ValueError("Empty generation cannot be pooled")
    ids = torch.cat([p_ids, g_ids], dim=1).to(model.get_input_embeddings().weight.device)
    n = p_ids.shape[1]
    pooled, handles = {}, []
    for layer in layers:
        def hook(module, inputs, output, layer=layer):
            pooled[layer] = hidden_tensor(output)[0, n:, :].detach().float().mean(0).cpu()
        handles.append(blocks(model)[resolve_layer(model, layer)].register_forward_hook(hook))
    try:
        with torch.no_grad():
            model(input_ids=ids, use_cache=False)
    finally:
        for h in handles:
            h.remove()
    return out["raw_text"], pooled


def contrast_generated(model, tokenizer, pairs, layers, log):
    """Unit mean(toward pooled) - mean(away pooled) per layer, over generated-answer tokens."""
    import torch
    rows = {layer: ([], []) for layer in layers}
    for toward, away in pairs:
        for side, prompt in ((0, toward), (1, away)):
            text, pooled = generated_pool(model, tokenizer, prompt, layers)
            log.append({"prompt": prompt, "side": ("toward", "away")[side], "text": text})
            for layer in layers:
                rows[layer][side].append(pooled[layer])
    out = {}
    for layer, (a, b) in rows.items():
        d = torch.stack(a).mean(0) - torch.stack(b).mean(0)
        if not torch.isfinite(d).all() or d.norm() < 1e-8:
            raise ValueError("Degenerate contrast")
        out[layer] = d / d.norm()
    return out


def run_probe(model, tokenizer, cfg, kind, name, desc, vector=None, layer=None, strength=None, mode="perceive",
              preamble=None):
    """mode perceive: steer the object span at prefill only. mode generate (V1.5.3): constant lambda at the prefill's
    last position and every decode step. ``preamble`` (V1.5.3, method P) is prepended text with no steering."""
    from contextlib import nullcontext
    from dream_core import modeling
    from dream_core.steering import MaskedSteerer
    from survival.runner import span_positions
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode}")
    if mode == "prompt" and vector is not None:
        raise ValueError("Method P is unsteered")
    user, span = probe_user(kind, name, desc, preamble)
    ctx = nullcontext()
    if vector is not None and mode == "generate":
        ctx = MaskedSteerer(model, layer, vector, strength, generation=True)
        with ctx as steerer:
            out = modeling.generate(model, tokenizer, user, max_input_tokens=512,
                                    max_new_tokens=CAT_TOKENS if kind == "categories" else DESC_TOKENS,
                                    temperature=0.0)
        if not steerer.trace or any(x != float(strength) for x in steerer.trace):
            raise RuntimeError("Write-time steering must apply constant lambda at every generation forward")
        return {"text": out["text"], "finish": out["finish_reason"], "output_tokens": out["output_tokens"],
                "steered_forwards": len(steerer.trace)}
    if vector is not None:
        positions, n, _ = span_positions(tokenizer, None, user, span, 512)
        ctx = MaskedSteerer(model, layer, vector, 0.0, generation=True, prefill_positions=positions,
                            prefill_strength=strength, prompt_tokens=n)
    with ctx as steerer:
        out = modeling.generate(model, tokenizer, user, max_input_tokens=512,
                                max_new_tokens=CAT_TOKENS if kind == "categories" else DESC_TOKENS, temperature=0.0)
    rec = {"text": out["text"], "finish": out["finish_reason"], "output_tokens": out["output_tokens"]}
    if vector is not None:
        rec["prefill_positions"] = len(steerer.prefill_trace["positions"])
        if steerer.trace[1:] and any(x != 0.0 for x in steerer.trace[1:]):
            raise RuntimeError("Decode steps must be unsteered in the screen")
    return rec


def run(model, tokenizer, cfg, out_dir, build, pilot_vector_path=None, max_seconds=21600, strengths=STRENGTHS,
        candidates=("D0", "D1", "D2"), objects="A", vectors_from=None, layers=LAYERS, mode="perceive"):
    """Build (or load) candidates, then screen. One JSON line per probe in screen.jsonl; resumable by key.

    V1.5.2: strengths, candidates, layers and the object set are parameters; ``vectors_from`` loads the exact
    vectors saved by an earlier screen (keys (code, layer)) instead of rebuilding them.
    """
    import shutil
    import torch
    from dream_core.ledger import atomic_json
    from dream_core.steering import build_vector, resolve_layer
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode}")
    if mode == "prompt":
        return run_prompt(model, tokenizer, cfg, out, candidates, objects, max_seconds, started)
    vec_path = out / "vectors.pt"
    if vectors_from is not None and not vec_path.exists():
        shutil.copy2(vectors_from, vec_path)
        atomic_json(out / "vectors-meta.json", {"loaded_from": str(vectors_from)})
    if vec_path.exists():
        vectors = torch.load(vec_path, weights_only=False)
    else:
        log = []
        vectors = {}
        for layer in LAYERS:
            vectors[("D0", layer)] = build_vector(model, tokenizer, build, layer, 512,
                                                  poles=("decategorized", "categorical")).float().cpu()
        for code, pairs in (("D1", d1_pairs(build)), ("D2", d2_pairs(build))):
            for layer, v in contrast_generated(model, tokenizer, pairs, LAYERS, log).items():
                vectors[(code, layer)] = v
        for layer in LAYERS:
            for code, seed, v in random_vectors(model.config.hidden_size):
                vectors[(code, layer)] = v
        torch.save(vectors, vec_path)
        atomic_json(out / "build-generations.json", log)
        meta = {f"{c}@{resolve_layer(model, l)}": {"norm": float(v.norm())} for (c, l), v in vectors.items()}
        if pilot_vector_path and Path(pilot_vector_path).exists():
            pv = torch.tensor(json.loads(Path(pilot_vector_path).read_text())["vector"])
            meta["cosine_D0_block-8_vs_pilot_vector"] = float(torch.dot(pv / pv.norm(), vectors[("D0", -8)]))
        cand = {l: [vectors[(c, l)] for c in ("D0", "D1", "D2")] for l in LAYERS}
        meta["candidate_cosines"] = {str(l): [[float(torch.dot(a, b)) for b in cand[l]] for a in cand[l]] for l in LAYERS}
        atomic_json(out / "vectors-meta.json", meta)
    path = out / "screen.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line); done.add((r["direction"], r["layer"], r["strength"], r["object"], r["probe"]))
    def emit(rec):
        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")
    jobs = [("baseline", None, None)] + [(c, l, s) for l in layers for c in
            tuple(candidates) + tuple(f"R{i}" for i in range(len(RANDOM_SEEDS))) for s in strengths]
    atomic_json(out / "screen-plan.json", {"strengths": list(strengths), "candidates": list(candidates),
                                           "layers": list(layers), "objects": objects, "mode": mode})
    for code, layer, strength in jobs:
        for name, desc in OBJECT_SETS[objects]:
            for kind in ("categories", "description"):
                key = (code, layer, strength, name, kind)
                if key in done:
                    continue
                if time.monotonic() - started > max_seconds:
                    raise TimeoutError("Screen wall-time budget reached; finished probes preserved, resume to continue")
                vec = None if code == "baseline" else vectors[(code, layer)]
                rec = run_probe(model, tokenizer, cfg, kind, name, desc, vec, layer, strength,
                                mode=mode if code != "baseline" else "perceive")
                emit({"direction": code, "layer": layer, "strength": strength, "object": name, "probe": kind,
                      "mode": mode, **rec})
    atomic_json(out / "COMPLETE.json", {"probes": len(jobs) * len(OBJECT_SETS[objects]) * 2})
    return out


def run_prompt(model, tokenizer, cfg, out, candidates, objects, max_seconds, started):
    """V1.5.3 method P: baseline (no preamble), candidate P wordings and all nine N wordings; no steering."""
    from dream_core.ledger import atomic_json
    from dream_core.steering import assert_no_dream_hooks
    assert_no_dream_hooks(model)
    if any(c not in PREAMBLES or not c.startswith("P") for c in candidates):
        raise ValueError("Method P candidates must be P wordings")
    codes = ["baseline", *candidates, *(f"N{i}" for i in range(9))]
    path = out / "screen.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line); done.add((r["direction"], r["object"], r["probe"]))
    atomic_json(out / "screen-plan.json", {"mode": "prompt", "candidates": list(candidates), "objects": objects,
                                           "preambles": {c: PREAMBLES[c] for c in codes if c != "baseline"}})
    for code in codes:
        for name, desc in OBJECT_SETS[objects]:
            for kind in ("categories", "description"):
                if (code, name, kind) in done:
                    continue
                if time.monotonic() - started > max_seconds:
                    raise TimeoutError("Screen wall-time budget reached; finished probes preserved, resume to continue")
                rec = run_probe(model, tokenizer, cfg, kind, name, desc, mode="prompt",
                                preamble=None if code == "baseline" else PREAMBLES[code])
                with open(path, "a") as f:
                    f.write(json.dumps({"direction": code, "layer": None, "strength": None, "object": name,
                                        "probe": kind, "mode": "prompt", **rec}) + "\n")
    atomic_json(out / "COMPLETE.json", {"probes": len(codes) * len(OBJECT_SETS[objects]) * 2})
    return out
