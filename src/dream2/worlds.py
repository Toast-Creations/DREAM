"""Procedural integer micro-worlds and an independent executable answer oracle."""
import json
from pathlib import Path
import random
from dream_core.contracts import REQUIRED_CATEGORIES


def apply_ops(start, operators, rules):
    if type(start) is not int:
        raise ValueError("World inputs must be integers")
    value = start
    for operator in operators:
        rule = rules[operator]
        if rule["kind"] == "add":
            value += rule["value"]
        elif rule["kind"] == "multiply":
            value *= rule["value"]
        else:
            raise ValueError("Unsupported world operator")
    return value


def oracle(item, world):
    kind = item["oracle"]["kind"]
    args = item["oracle"]
    if kind == "apply":
        return apply_ops(args["start"], args["operators"], world["rules"])
    if kind == "rule":
        return world["rules"][args["operator"]] == args["claim"]
    if kind == "scope":
        return False
    if kind == "arithmetic":
        return args["a"] + args["b"]
    if kind == "lookup":
        return world["lookup"][args["key"]]
    raise ValueError("Unknown oracle kind")


def answer_type(value):
    return "boolean" if type(value) is bool else "integer" if type(value) is int else "string"


def canonical_question(item, training=False):
    args = item["oracle"]
    kind = args["kind"]
    if kind == "apply":
        if item.get("category") == "paraphrase":
            return f"Transform the integer {args['start']} using just {args['operators'][0]}."
        return f"Start with {args['start']}. Apply {' then '.join(args['operators'])} from left to right."
    if kind == "rule":
        return f"In this world, does {args['operator']} mean {args['claim']['kind']} {args['claim']['value']}?"
    if kind == "scope":
        return f"Outside this synthetic world, does the invented name {args['operator']} impose a universal rule on ordinary arithmetic?"
    if kind == "arithmetic":
        return f"Outside all synthetic worlds, what is {args['a']} plus {args['b']}?"
    if kind == "lookup":
        return f"What integer is assigned to {args['key']}?" if training else f"Recall the assigned integer for {args['key']}."
    raise ValueError("Unknown question renderer")


def generate_worlds(count=24, seed=1101, split="development"):
    if split not in ("development", "validation", "test") or not 1 <= count <= 10000:
        raise ValueError("Invalid world count or split")
    rng = random.Random(seed)
    worlds = []
    for index in range(count):
        names = ["op" + "".join(rng.choices("abcdefghjkmnpqrstuvwxyz", k=7)) for _ in range(3)]
        while len(set(names)) != 3:
            names = ["op" + "".join(rng.choices("abcdefghjkmnpqrstuvwxyz", k=7)) for _ in range(3)]
        rules = {names[0]: {"kind": "multiply", "value": rng.choice([2, 3, -2, -3])},
                 names[1]: {"kind": "add", "value": rng.choice([-7, -5, 4, 6])},
                 names[2]: {"kind": "multiply", "value": -1}}
        world = {"id": f"{split}-{seed}-{index:04d}", "split": split,
                 "rules": rules, "lookup": {"tagA": rng.randrange(100, 900), "tagB": rng.randrange(100, 900)},
                 "train": [], "eval": []}
        def question(start, ops):
            return f"Start with {start}. Apply {' then '.join(ops)} from left to right."
        rules_text = "; ".join(f"{name}: {rule['kind']} {rule['value']}" for name, rule in rules.items())
        world["description"] = "Synthetic integer world. Operators act left to right."
        for name in names:
            for start in (-3, 2, 5):
                world["train"].append({"question": question(start, [name]),
                    "context": rules_text, "oracle": {"kind": "apply", "start": start, "operators": [name]}})
        world["train"].append({"question": question(1, names[:2]), "context": rules_text,
                                "oracle": {"kind": "apply", "start": 1, "operators": names[:2]}})
        for key in world["lookup"]:
            world["train"].append({"question": f"What integer is assigned to {key}?",
                "context": f"{key} is assigned {world['lookup'][key]}.", "oracle": {"kind": "lookup", "key": key}})
        for name in names:
            world["eval"].append({"category": "direct", "question": question(7, [name]),
                                  "oracle": {"kind": "apply", "start": 7, "operators": [name]}})
            world["eval"].append({"category": "paraphrase", "question": f"Transform the integer -8 using just {name}.",
                                  "oracle": {"kind": "apply", "start": -8, "operators": [name]}})
        sequences = (names, names[::-1], [names[1], names[0], names[1]], [names[0], names[2], names[1]])
        for start, ops in zip((4, -4, 6, -6), sequences):
            # Distinct probes with varied inputs; neither copy-input nor sign
            # flip alone can earn composition credit on these new fixtures.
            while apply_ops(start, ops, rules) in (start, -start):
                start += 1
            world["eval"].append({"category": "composition", "question": question(start, ops),
                                  "oracle": {"kind": "apply", "start": start, "operators": ops}})
        for name, rule in rules.items():
            for claim in (dict(rule), {"kind": rule["kind"], "value": rule["value"] + 1}):
                world["eval"].append({"category": "contradiction",
                    "question": f"In this world, does {name} mean {claim['kind']} {claim['value']}?",
                    "oracle": {"kind": "rule", "operator": name, "claim": claim}})
            world["eval"].append({"category": "scope",
                "question": f"Outside this synthetic world, does the invented name {name} impose a universal rule on ordinary arithmetic?",
                "oracle": {"kind": "scope", "operator": name}})
        for a, b in ((11, 8), (3, -9), (-5, -7), (25, 19)):
            world["eval"].append({"category": "anchor", "question": f"Outside all synthetic worlds, what is {a} plus {b}?",
                                  "oracle": {"kind": "arithmetic", "a": a, "b": b}})
        for key in world["lookup"]:
            world["eval"].append({"category": "lookup", "question": f"Recall the assigned integer for {key}.",
                                  "oracle": {"kind": "lookup", "key": key}})
        for item in world["train"] + world["eval"]:
            item["answer"] = oracle(item, world)
            item["answer_type"] = answer_type(item["answer"])
        worlds.append(world)
    return worlds


def validate_worlds(worlds):
    if not worlds or len({w["id"] for w in worlds}) != len(worlds):
        raise ValueError("World IDs must be unique")
    for world in worlds:
        if world["split"] not in ("development", "validation", "test"):
            raise ValueError("Invalid split")
        if not world["rules"] or any(r["kind"] not in ("add", "multiply") or type(r["value"]) is not int for r in world["rules"].values()):
            raise ValueError("Rules must have declared integer operations")
        if not world["train"] or not set(REQUIRED_CATEGORIES).issubset({i["category"] for i in world["eval"]}):
            raise ValueError("World lacks required exposure or evaluation categories")
        for item in world["train"] + world["eval"]:
            target = oracle(item, world)
            if type(item["answer"]) is not type(target) or item["answer"] != target or item["answer_type"] != answer_type(target):
                raise ValueError("Reference answer disagrees with oracle")
            if item["question"] != canonical_question(item, item in world["train"]):
                raise ValueError("Question wording disagrees with its symbolic oracle arguments")
        composition = [i["question"] for i in world["eval"] if i["category"] == "composition"]
        if len(composition) != len(set(composition)):
            raise ValueError("Duplicate composition probes")
        for item in world["train"]:
            args = item["oracle"]
            if args["kind"] not in ("apply", "lookup"):
                raise ValueError("Unsupported exposure kind")
            context = (f"{args['key']} is assigned {world['lookup'][args['key']]}." if args["kind"] == "lookup" else
                       "; ".join(f"{name}: {r['kind']} {r['value']}" for name,r in world["rules"].items()))
            if item["context"] != context:
                raise ValueError("Training context disagrees with verified world facts")
        expected = {"direct":"apply", "paraphrase":"apply", "composition":"apply", "contradiction":"rule",
                    "scope":"scope", "anchor":"arithmetic", "lookup":"lookup"}
        if any(i["category"] not in expected or expected[i["category"]] != i["oracle"]["kind"] for i in world["eval"]):
            raise ValueError("Evaluation category disagrees with its oracle kind")
        probes = [i["answer"] for i in world["eval"] if i["category"] == "contradiction"]
        if probes.count(True) != probes.count(False) or not probes:
            raise ValueError("Contradiction probes must be balanced")
        train_signatures = {(i["oracle"].get("start"), tuple(i["oracle"].get("operators", [])))
                            for i in world["train"] if i["oracle"]["kind"] == "apply"}
        if any((i["oracle"]["start"], tuple(i["oracle"]["operators"])) in train_signatures
               for i in world["eval"] if i["category"] == "composition"):
            raise ValueError("Composition query leaked into training")
    return worlds


def load_worlds(path, phase):
    worlds = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_worlds(worlds)
    selected = [w for w in worlds if w["split"] == phase]
    if not selected:
        raise ValueError("No worlds for the declared phase")
    return selected
