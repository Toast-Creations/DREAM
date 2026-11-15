"""V1.22.0 KEEP+ID confirmation precollection validation (no generation).
Usage: kconf_validate.py --hub HUB [--tokenizer MODEL_PATH] [--historical PATH ...]
Gates (all must pass before freeze), main and smoke:
  V1 prompt preservation: KEEP minus its annotation line = BASE byte-for-byte, the annotation is the only new line and
     sits directly before "New record to convert:"; SUB = refres.rewrite_prompt(BASE, target, RES-DET rewrite); both
     arms share system text and cap 256.
  V2 public-only construction: SUB/KEEP prompts rebuilt from an allowlisted public copy (prefix, target text,
     registry order, BASE prompt) are byte-identical; again after scrambling the hidden labels; the prompt-building
     code does not mention hidden/gold/case fields.
  V3 identity = construction label (checked separately, after construction) and SUB/KEEP identity parity.
  V4 token budget: chat-rendered SUB and KEEP inputs <= 2,048 (Qwen3-32B tokenizer, thinking off).
  V5 scoring: canonical replies exact; per arrival: state-only, wrong event value and (when it differs) extra
     reception-time state are inexact; per correction: flipped revision value, empty lists and NO-state + YES-revision
     mixed reply are inexact.
  V6 allocation and membership: group counts per stratum and act equal the declared allocation; arrival groups are
     the first n_arrival/8 blocks and a subset of correction groups; both histories for every kept group-act; the call
     schedule is exactly {group|act|hist|arm}; unique ids; smoke disjoint from main (groups, pools, world seeds).
  V7 disjointness from history: no BASE prompt or world seed from the given historical files; no gNNN ids."""
import argparse
import collections
import copy
import hashlib
import inspect
import json
import random
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA, holdeval as HE, holdout as HO, keepid as KI, kidconf as KC, kidconfgen as KG, \
    kidconfscore as KS, refres as RR

ALLOW = ("target", "component", "group", "family", "reception", "act", "history", "stratum", "prefix", "target_text",
         "registry_order", "base_prompt")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--tokenizer")
    ap.add_argument("--historical", nargs="*", default=[])
    ap.add_argument("--src-hub", help="1.20 hub: tokenizer must reproduce 24 recorded 1.20 BASE input-token counts")
    a = ap.parse_args()
    hub = Path(a.hub)
    data = hub / "data"
    commit = json.loads((data / "COMMITMENT.json").read_text())
    cfg = commit["config"]
    for name, h in commit["files_sha256"].items():
        assert sha(data / name) == h, f"{name} differs from its commitment"
    gates, out = {}, {}

    def gate(name, bad, n):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": n, "examples": [str(b)[:300] for b in bad[:6]]}

    parts = {}
    for part in ("main", "smoke"):
        parts[part] = (load(data / f"public/{part}-targets.jsonl"), {h["target"]: h for h in load(data / f"hidden/{part}-cases.jsonl")},
                       load(data / f"{part}-calls.jsonl"))
    allcalls = [c for p in parts.values() for c in p[2]]
    bymap = {c["call_id"]: c for c in allcalls}
    # V1
    bad = []
    for part, (pubs, hid, calls) in parts.items():
        for p in pubs:
            sub, keep = bymap[p["target"] + "|SUB"], bymap[p["target"] + "|KEEP"]
            L = p["identity"]
            line = L["keep_ledger"]["annotation"]
            if KI.strip_annotation(keep["user"], line) != p["base_prompt"]:
                bad.append((p["target"], "strip"))
            bl, kl = p["base_prompt"].split("\n"), keep["user"].split("\n")
            j = kl.index(KI.ANCHOR)
            if not (len(kl) == len(bl) + 1 and kl[j - 1] == line and kl[:j - 1] + kl[j:] == bl and kl[j + 1] == p["target_text"]):
                bad.append((p["target"], "line_diff"))
            nt = RR.rewrite(p["target_text"], L["detection"], L["field"])[0]
            if sub["user"] != RR.rewrite_prompt(p["base_prompt"], p["target_text"], nt):
                bad.append((p["target"], "sub"))
            if sub["system"] != keep["system"] or sub["max_new_tokens"] != 256 or keep["max_new_tokens"] != 256:
                bad.append((p["target"], "system_or_cap"))
            if any(e["raw_text"] not in keep["user"] for e in p["prefix"]):
                bad.append((p["target"], "prefix"))
    gate("V1 prompt preservation (KEEP = BASE + one annotation line; SUB = 1.20 rewrite)", bad, len(allcalls) // 2)
    # V2
    bad = []
    for part, (pubs, hid, calls) in parts.items():
        for scramble in (False, True):
            if scramble:   # hidden labels scrambled in memory; construction reads public rows only
                golds = [h["gold_field"] for h in hid.values()]
                random.Random(7).shuffle(golds)
                for h, g in zip(hid.values(), golds):
                    h["gold_field"] = g
            for p in pubs:
                slim = copy.deepcopy({k: p[k] for k in ALLOW})
                sub, keep, led = KG.arms_from_public(slim)
                if hashlib.sha256(sub.encode()).hexdigest() != bymap[p["target"] + "|SUB"]["user_sha256"] or \
                        hashlib.sha256(keep.encode()).hexdigest() != bymap[p["target"] + "|KEEP"]["user_sha256"]:
                    bad.append((p["target"], "rebuild differs", scramble))
    code = "".join(inspect.getsource(f) for f in (KG.arms_from_public, KI.annotation, KI.keep_prompt, RR.rewrite,
                                                   RR.rewrite_prompt))
    for word in ("gold", "hidden", "case[", "world_seed"):
        if word in code:
            bad.append(f"prompt-construction code mentions {word!r}")
    gate("V2 public-only construction (allowlisted and scrambled-hidden rebuilds byte-identical)", bad, len(allcalls) // 2)
    # V3 (reload hidden: V2 scrambled the in-memory copy)
    bad = []
    for part in parts:
        hid = {h["target"]: h for h in load(data / f"hidden/{part}-cases.jsonl")}
        pubs = parts[part][0]
        parts[part] = (pubs, hid, parts[part][2])
        for p in pubs:
            L = p["identity"]
            if L["field"] != hid[p["target"]]["gold_field"]:
                bad.append((p["target"], "identity != label"))
            if L["sub_ledger"]["replacement"] != "part " + L["field"][: -len(".on_hand")] or \
                    L["keep_ledger"]["field"] != L["field"]:
                bad.append((p["target"], "SUB/KEEP parity"))
    gate("V3 identity = construction label; SUB/KEEP identity parity", bad, sum(len(p[0]) for p in parts.values()))
    # V4
    toks = {}
    if a.tokenizer:
        from transformers import AutoTokenizer
        from dream_core.modeling import render_chat
        tok = AutoTokenizer.from_pretrained(a.tokenizer, local_files_only=True, trust_remote_code=False)
        tok.dream_chat_kwargs = {"enable_thinking": False}     # as in the runner and the 1.21 validator
        for c in allcalls:
            toks[c["call_id"]] = len(tok(render_chat(tok, c["user"], system=c["system"], enable_thinking=False),
                                         add_special_tokens=False).input_ids)
        bad = [(k, v) for k, v in toks.items() if v > 2048]
        if a.src_hub:
            src = Path(a.src_hub)
            A20 = {c["call_id"]: c for c in load(src / "data" / "refA-calls.jsonl")}
            recs = sorted((src / "stages" / "main-A" / "calls").glob("*__BASE.json"))[:24]
            for rp in recs:
                r = json.loads(rp.read_text())
                c = A20[r["call_id"]]
                n_ = len(tok(render_chat(tok, c["user"], system=c["system"], enable_thinking=False), add_special_tokens=False).input_ids)
                if n_ != r["input_tokens"]:
                    bad.append((r["call_id"], "tokenizer does not reproduce 1.20 input tokens", n_, r["input_tokens"]))
            out["tokenizer_crosscheck_1_20"] = len(recs)
        else:
            bad.append("no 1.20 hub for the tokenizer cross-check")
        for arm in KC.ARMS:
            v = [n for k, n in toks.items() if k.endswith("|" + arm)]
            out[f"{arm}_input_tokens"] = {"max": max(v), "min": min(v), "mean": round(sum(v) / len(v), 1)}
    else:
        bad = ["tokenizer not given"]
    gate("V4 token budget <= 2048 (chat-rendered, thinking off)", bad, len(allcalls))
    # V5
    bad, n = [], 0
    for part, (pubs, hid, calls) in parts.items():
        for p in pubs:
            h = hid[p["target"]]
            case, w, reg = h["case"], KS.world(h, cfg["consonants"]), p["registry"]
            can = dict(FA.canonical_factored(HO.public(case)[-1]), evidence=case["text"][-25:])
            n += 1
            if not HE.score(json.dumps(can), case, w, reg)[0]["exact"]:
                bad.append((p["target"], "canonical not exact"))
            if p["act"] == "arrival":
                st = {"field": h["gold_field"], "at": case["records"][-1]["event_at"], "value": "yes"}
                e0 = can["events"][0]
                muts = {"state_only": dict(can, events=[], states=[st]),
                        "wrong_event_value": dict(can, events=[dict(e0, to="no" if e0["to"] == "yes" else "yes")])}
                rt = case["records"][-1]["received_at"]
                if rt != st["at"]:
                    muts["extra_reception_state"] = dict(can, states=can["states"] + [dict(st, at=rt)])
            else:
                r0 = can["revisions"][0]
                muts = {"flipped_revision": dict(can, revisions=[dict(r0, value="yes" if r0["value"] == "no" else "no")]),
                        "empty": dict(can, events=[], states=[], revisions=[]),
                        "no_state_yes_revision": dict(can, states=[{"field": h["gold_field"], "at": r0.get("valid_from"), "value": "no"}],
                                                      revisions=[dict(r0, value="yes")])}
            for name, mut in muts.items():
                if HE.score(json.dumps(mut), case, w, reg)[0]["exact"]:
                    bad.append((p["target"], name, "mutation exact"))
    gate("V5 scoring: canonical exact; act-specific mutations inexact (both acts)", bad, n)
    # V6
    bad = []
    pubs, hid, calls = parts["main"]
    groups = KC.plan(cfg["n_correction_groups"], cfg["id_prefix"])
    want = KC.allocation_table(groups, cfg["n_arrival_groups"])
    got = collections.Counter(f"{p['act']}|{p['stratum']}" for p in pubs if p["history"] == "A")
    if dict(got) != want or commit["allocation"] != want:
        bad.append(("allocation", dict(got), want))
    decl = {(p["group"], p["act"]): p["stratum"] for p in pubs}
    for (g, act) in decl:
        if {p["history"] for p in pubs if p["group"] == g and p["act"] == act} != set(KC.HISTORIES):
            bad.append((g, act, "histories"))
    arr = {g for g, act in decl if act == "arrival"}
    cor = {g for g, act in decl if act == "correction"}
    first = {gid for gid, f, r, b, blk in groups if blk < cfg["n_arrival_groups"] // 8}
    if arr != first or not arr <= cor or len(cor) != cfg["n_correction_groups"]:
        bad.append(("nesting", len(arr), len(cor)))
    sched = {c["call_id"] for c in calls}
    if sched != {f"{g}|{a_}|{h}|{arm}" for (g, a_) in decl for h in KC.HISTORIES for arm in KC.ARMS} or len(sched) != len(calls):
        bad.append("schedule != declared membership")
    sp, sh, sc = parts["smoke"]
    if {p["group"] for p in sp} & {p["group"] for p in pubs} or {h["world_seed"] for h in sh.values()} & {h["world_seed"] for h in hid.values()}:
        bad.append("smoke overlaps main")
    if len(sc) != 32:
        bad.append(("smoke calls", len(sc)))
    gate("V6 allocation, nesting, paired histories, schedule = membership, smoke disjoint", bad, len(calls))
    # V7
    bad = []
    hp, hs = set(), set()
    for f in a.historical:
        for r in load(f):
            hp.add(r.get("base_prompt"))
            hs.add(r.get("world_seed"))
    allp = [p["base_prompt"] for part in parts.values() for p in part[0]]
    if set(allp) & hp:
        bad.append("historical prompt reappears")
    if {h["world_seed"] for part in parts.values() for h in part[1].values()} & hs:
        bad.append("historical world seed reappears")
    if any(c["call_id"].startswith("g0") for c in allcalls):
        bad.append("gNNN id")
    if not a.historical:
        bad.append("no historical files given")
    gate("V7 disjoint from 1.20/1.21 panels (prompts, world seeds, ids)", bad, len(allp))
    res = {"gates": gates, "all_pass": all(g["pass"] for g in gates.values()), "main_calls": len(calls),
           "smoke_calls": len(sc), "commitment_sha256": sha(data / "COMMITMENT.json"), **out}
    (hub / "phase0").mkdir(exist_ok=True)
    (hub / "phase0" / "VALIDATION.json").write_text(json.dumps(res, indent=1) + "\n")
    md = ["# V1.22.0 KEEP+ID confirmation precollection validation", "", f"All pass: **{res['all_pass']}**.", ""]
    md += [f"- {'PASS' if g['pass'] else 'FAIL'} {k} ({g['checked']} checked, {g['failures']} failures)" for k, g in gates.items()]
    (hub / "phase0" / "VALIDATION.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"all_pass": res["all_pass"], **{k: g["failures"] for k, g in gates.items()}}))


if __name__ == "__main__":
    main()
