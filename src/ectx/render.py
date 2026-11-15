"""The exact text shown to the model. Every condition receives byte-identical prompts.

Rules text below is the specification solver 2 (keycheck.py) implements.
"""
import json

RULES = {
    "delivery": [
        "You are a courier. Places are joined by roads; each road can be travelled in both directions.",
        "\"go from A to B\": you must be at A, A and B must be joined by a listed road, and that road must not be closed right now. Cost: the road's cost.",
        "\"take ITEM\": you must be at the place where ITEM rests, your hands must be empty, and ITEM must be portable. Cost: 1. You can carry only one item at a time.",
        "\"put down ITEM\": you must be carrying ITEM. It then rests at the place where you are. Cost: 1.",
        "An item counts as being at a place only while it rests there, not while you carry it.",
    ],
    "assembly": [
        "You are a technician fitting parts into the slots of a machine. Each slot and each part has a connector type.",
        "\"order PART\": only parts with a listed price can be ordered; the part must not already be on hand or installed. Cost: its price. It arrives on hand.",
        "\"fit ADAPTER to SLOT\": the adapter must be on hand, the slot must be empty and have no adapter, and the adapter's output connector must equal the slot's connector. Cost: 1. A fitted adapter stays in place; afterwards the slot accepts only parts whose connector equals the adapter's input connector.",
        "\"install PART in SLOT\": the part must be on hand and the slot must be empty. The part's connector must equal the slot's connector, or, if an adapter is fitted, the adapter's input connector. Cost: 2.",
        "\"remove the part from SLOT\": the slot must hold a part. The part goes back on hand and the slot becomes empty (any adapter stays). Cost: 1.",
    ],
    "workshop": [
        "You are a maker. You either have a resource or you do not; getting one you already have changes nothing.",
        "\"get RESOURCE from SOURCE\": the source must supply that resource and must not be out of stock; if the source requires a permit you must hold it. Cost: the source's cost.",
        "\"obtain permit PERMIT\": always possible. Cost: the permit's cost. Permits are kept.",
        "\"make ITEM\": you must have every input listed in its recipe and, if the recipe requires a permit, hold that permit. The inputs are used up and you then have ITEM. Cost: 1.",
    ],
}

TASK_LINE = ("Choose the option whose plan achieves the goal with the lowest possible total cost. "
             "Every step must be allowed at the moment it is taken. The empty plan is allowed if the goal already holds.")
ANSWER_LINE = 'Reply with only a JSON object: {"choice": "<option ID>"}'


def static_lines(family, st):
    if family == "delivery":
        out = ["Places: " + ", ".join(st["places"]) + "."]
        out += [f"Road between {a} and {b}: cost {c}." for a, b, c in st["roads"]]
        out += [f"{i}: {'portable' if p['portable'] else 'fixed in place (cannot be taken)'}."
                for i, p in st["items"].items()]
        return out
    if family == "assembly":
        out = [f"Slot {s}: connector {c}." for s, c in st["slots"].items()]
        out += [f"Part {p}: connector {v['type']}, rating {v['rating']}." for p, v in st["parts"].items()]
        out += [f"Adapter {a}: input connector {v['from']}, output connector {v['to']}." for a, v in st["adapters"].items()]
        out += [f"Price of {p}: {c}." for p, c in st["prices"].items()]
        return out
    out = []
    for s, v in st["sources"].items():
        extra = f", requires permit {v['permit']}" if v["permit"] else ""
        out.append(f"Source {s}: supplies {v['resource']}, cost {v['cost']}{extra}.")
    out += [f"Permit {k}: cost {c}." for k, c in st["permits"].items()]
    for item, v in st["recipes"].items():
        extra = f"; requires permit {v['permit']}" if v["permit"] else ""
        out.append(f"Recipe for {item}: inputs {' and '.join(v['inputs'])}{extra}.")
    return out


def state_lines(family, s):
    if family == "delivery":
        out = [f"You are at {s['agent']}."]
        for i, w in s["item_at"].items():
            out.append(f"{i} is being carried by you." if w == "held" else f"{i} rests at {w}.")
        closed = [f"{a}–{b}" for a, b in s["closed"]]
        out.append("Closed roads right now: " + (", ".join(closed) if closed else "none") + ".")
        return out
    if family == "assembly":
        out = []
        for slot in sorted(s["slot_part"]):
            part, adapter = s["slot_part"][slot], s["slot_adapter"].get(slot)
            out.append(f"Slot {slot}: " + (f"holds {part}" if part else "empty")
                       + (f", adapter {adapter} fitted" if adapter else ", no adapter") + ".")
        out.append("On hand: " + (", ".join(sorted(s["on_hand"])) if s["on_hand"] else "nothing") + ".")
        return out
    return ["You have: " + (", ".join(sorted(s["have"])) if s["have"] else "nothing") + ".",
            "Permits held: " + (", ".join(sorted(s["permits"])) if s["permits"] else "none") + ".",
            "Out of stock right now: " + (", ".join(sorted(s["out_of_stock"])) if s["out_of_stock"] else "none") + "."]


def goal_line(family, g):
    if family == "delivery":
        return f"Goal: {g['item']} rests at {g['place']}."
    if family == "assembly":
        return f"Goal: slot {g['slot']} holds a part rated at least {g['min_rating']}."
    return f"Goal: you have {g['item']}."


def step_text(family, step):
    k = step[0]
    if family == "delivery":
        return {"go": lambda: f"go from {step[1]} to {step[2]}", "take": lambda: f"take {step[1]}",
                "put": lambda: f"put down {step[1]}"}[k]()
    if family == "assembly":
        return {"order": lambda: f"order {step[1]}", "fit": lambda: f"fit {step[1]} to {step[2]}",
                "install": lambda: f"install {step[1]} in {step[2]}",
                "remove": lambda: f"remove the part from {step[1]}"}[k]()
    return {"get": lambda: f"get {step[1]} from {step[2]}", "obtain": lambda: f"obtain permit {step[1]}",
            "make": lambda: f"make {step[1]}"}[k]()


def plan_text(family, plan):
    return "no action (empty plan)" if not plan else "; ".join(f"{n}. {step_text(family, s)}" for n, s in enumerate(plan, 1))


def query_block(family, q, *, answer=None):
    lines = ["Current state:"] + ["- " + x for x in state_lines(family, q["state"])]
    if q.get("correction"):
        if answer is not None:  # a solved example in the packet: its correction is local to it
            lines.append("Correction (applies to this example only; the packet's fixed facts are unchanged "
                         "for every other question): " + q["correction"]["text"])
        else:
            lines.append("Correction (this replaces the packet's fixed fact): " + q["correction"]["text"])
    lines.append(goal_line(family, q["goal"]))
    lines.append("Options:")
    lines += [f"[{c['id']}] {plan_text(family, c['plan'])}" for c in q["candidates"]]
    if answer is not None:
        lines.append("Answer: " + json.dumps({"choice": answer}))
    return "\n".join(lines)


def packet(ep, *, exclude_support=None, include_support=True):
    """include_support=False (V1.6.1, adapter training only): rules and fixed facts, no solved examples."""
    fam = ep["family"]
    parts = [f"EPISODE PACKET ({ep['world_name']})", "", "Rules:"]
    parts += ["- " + r for r in RULES[fam]]
    parts += ["", "Fixed facts:"] + ["- " + x for x in static_lines(fam, ep["static"])]
    if not include_support:
        return "\n".join(parts)
    parts += ["", "Solved examples (verified):"]
    n = 0
    for s in ep["support"]:
        if s["qid"] == exclude_support:
            continue
        n += 1
        parts += ["", f"Example {n}:", query_block(fam, s, answer=s["answer"])]
    return "\n".join(parts)


def user_prompt(ep, q, *, exclude_support=None, include_support=True):
    return "\n".join([packet(ep, exclude_support=exclude_support, include_support=include_support), "", "CURRENT QUERY", TASK_LINE,
                      query_block(ep["family"], q), "", ANSWER_LINE])
