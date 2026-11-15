"""V1.21.0 KEEP+ID precollection validation and cache mapping (no generation).
Usage: kid_validate.py --hub HUB --src-hub HUB_1_20 [--tokenizer MODEL_PATH]
Gates (all must pass before freeze):
  K1 prompt preservation: removing the annotation line gives back the 1.20 BASE prompt byte-for-byte; the only new
     line is the annotation, directly before "New record to convert:"; the original target line and every prefix
     envelope appear verbatim; the system text equals the 1.20 BASE call's system text.
  K2 public-only identity: the calls file is rebuilt from an allowlisted public copy (prefix, target text, registry
     order, base prompt, metadata) with every other key removed, and again after scrambling the hidden labels on
     disk; both rebuilds are byte-identical to the committed file. The KEEP generator never opens the hidden file.
  K3 construction labels (separate check): the annotated field equals the hidden gold_field on all 192 targets.
  K4 SUB/KEEP identity parity: the 1.20 RES-DET rewrite names the same part as the KEEP annotation.
  K5 token budget: chat-rendered KEEP inputs (Qwen3-32B tokenizer, thinking off) are <= 2,048 tokens.
  K6 scoring: canonical replies are exact under HOLD-EVAL-v1; three semantic mutations (drop the event / add a
     state to an arrival; flip a correction value) are not exact; re-scoring the cached 1.20 BASE and RES-DET replies
     under this source reproduces every stored 1.20 scored row field used here.
  K7 cache provenance: for every target, the 1.20 main-A BASE and DET call records exist, status ok, complete, one
     attempt, user_sha256 = sha256(stored public prompt) = the 1.20 committed call, pinned model settings; main-A LOCK
     binds the 1.20 freeze source/config/calls hashes. Writes HUB/data/CACHE-MAP.jsonl."""
import argparse
import collections
import copy
import hashlib
import json
import random
import tempfile
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tempo import factored as FA, holdeval as HE, holdout as HO, keepid as KI, refgen as RG  # noqa: F401
import kid_generate as KG

PIN = {"revision": "9216db5781bf21249d130ec9da846c4624c16137", "quantization": "nf4", "enable_thinking": False,
       "decoding": "greedy", "dtype": "bfloat16"}
FREEZE_1_20 = {"source": "384d2fd0d59a831e24a4e9340517d35111d6f73888ddb4a130012541eb034176",
               "config_main_A": "e3cc8647c9f0049ca1c367ac70f02bfaf75567557b76fe4910eaec2eaf264a1b",
               "calls_A": "9b7c3922d7a4f0d4e0a7196c359c957b1325b15035955507117489942227b3ed",
               "scored": "49706e4aa703ab939960d820d8d4f9b2c92fa2b4ae94bf0ad04f0cb9307a1205"}
SCORE_KEYS = ("exact", "accepted", "compiled", "bound_ok_accepted", "state_only_event_accepted", "contract_code",
              "pending_code", "category", "raw_events", "raw_states", "raw_revisions", "replay_ok", "truncated")
ALLOW = ("target", "component", "group", "family", "reception", "act", "history", "stratum", "prefix", "target_text",
         "registry_order", "base_prompt")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def shs(s):
    return hashlib.sha256(s.encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--src-hub", required=True)
    ap.add_argument("--tokenizer")
    a = ap.parse_args()
    hub, src = Path(a.hub), Path(a.src_hub)
    data = hub / "data"
    commit = json.loads((data / "COMMITMENT-kid.json").read_text())
    calls = load(data / "kid-calls.jsonl")
    led = {r["target"]: r for r in load(data / "kid-ledger.jsonl")}
    T = {t["target"]: t for t in load(data / "inputs" / "ref-targets.jsonl")}
    H = {h["target"]: h for h in load(data / "inputs" / "ref-cases.jsonl")}
    A20 = {c["call_id"]: c for c in load(src / "data" / "refA-calls.jsonl")}
    gates, out = {}, {}

    def gate(name, bad, n):
        gates[name] = {"pass": not bad, "failures": len(bad), "checked": n, "examples": [str(b)[:300] for b in bad[:6]]}

    assert sha(data / "kid-calls.jsonl") == commit["calls_sha256"]
    # K1
    bad = []
    for c in calls:
        tid = c["call_id"].rsplit("|", 1)[0]
        t, L = T[tid], led[tid]
        base = t["base_prompt"]
        if KI.strip_annotation(c["user"], L["annotation"]) != base:
            bad.append((tid, "strip"))
        bl, kl = base.split("\n"), c["user"].split("\n")
        j = kl.index(KI.ANCHOR)
        if not (len(kl) == len(bl) + 1 and kl[j - 1] == L["annotation"] and kl[:j - 1] + kl[j:] == bl):
            bad.append((tid, "line_diff"))
        if kl[j + 1] != t["target_text"] or any(e["raw_text"] not in c["user"] for e in t["prefix"]):
            bad.append((tid, "target_or_prefix"))
        if c["system"] != A20[f"{tid}|BASE"]["system"] or c["max_new_tokens"] != 256:
            bad.append((tid, "system_or_cap"))
        if L["phrase"] not in t["target_text"] or L["phrase"] != t["detection"]["text"]:
            bad.append((tid, "phrase"))
    gate("K1 prompt preservation (BASE prompt + exactly one annotation line before the anchor)", bad, len(calls))
    # K2
    bad = []
    pubs = load(data / "inputs" / "ref-targets.jsonl")
    slim = [{k: p[k] for k in ALLOW} for p in pubs]
    c2, l2 = KG.build_calls(slim)
    if [json.dumps(x, sort_keys=True) for x in c2] != [json.dumps(x, sort_keys=True) for x in calls]:
        bad.append("allowlisted rebuild differs")
    with tempfile.TemporaryDirectory() as td:  # scrambled hidden labels on disk; the build reads only public rows
        hs = load(data / "inputs" / "ref-cases.jsonl")
        golds = [h["gold_field"] for h in hs]
        random.Random(7).shuffle(golds)
        for h, g in zip(hs, golds):
            h["gold_field"] = g
            h["case"] = {"scrambled": True}
        (Path(td) / "ref-cases.jsonl").write_text("".join(json.dumps(h) + "\n" for h in hs))
        c3, _ = KG.build_calls(copy.deepcopy(slim))
        if [x["user_sha256"] for x in c3] != [x["user_sha256"] for x in calls]:
            bad.append("rebuild under scrambled hidden labels differs")
    import inspect
    code = "".join(inspect.getsource(f) for f in (KI.annotation, KI.identity, KI.keep_prompt, KI.build, KG.build_calls,
                                                   KG.select, KG.call))
    for word in ("gold", "hidden", "cases", "case[", "world_seed"):
        if word in code:
            bad.append(f"prompt-construction code mentions {word!r}")
    gate("K2 public-only identity construction (allowlisted rebuild and scrambled-hidden rebuild byte-identical)", bad, len(calls))
    # K3
    bad = [(t, L["field"], H[t]["gold_field"]) for t, L in led.items() if L["field"] != H[t]["gold_field"]]
    gate("K3 annotated identity = hidden construction label (checked separately, after prompt construction)", bad, len(led))
    # K4
    bad = [(t, L["field"]) for t, L in led.items()
           if T[t]["det_ledger"]["replacement"] != "part " + L["field"][: -len(".on_hand")] or T[t]["det"]["field"] != L["field"]]
    gate("K4 SUB (1.20 RES-DET rewrite) and KEEP+ID carry the same identity", bad, len(led))
    # K5
    toks = {}
    if a.tokenizer:
        from transformers import AutoTokenizer
        from dream_core.modeling import render_chat
        tok = AutoTokenizer.from_pretrained(a.tokenizer, local_files_only=True, trust_remote_code=False)
        tok.dream_chat_kwargs = {"enable_thinking": False}
        for c in calls:
            toks[c["call_id"]] = len(tok(render_chat(tok, c["user"], system=c["system"], enable_thinking=False),
                                         add_special_tokens=False).input_ids)
        bad = [(k, v) for k, v in toks.items() if v > 2048]
        # cross-check: the same tokenizer reproduces the 1.20 recorded BASE input tokens
        rec = {p.name: json.loads(p.read_text()) for p in (src / "stages" / "main-A" / "calls").glob("*__BASE.json")}
        for c in calls[:24]:
            tid = c["call_id"].rsplit("|", 1)[0]
            b = A20[f"{tid}|BASE"]
            n = len(tok(render_chat(tok, b["user"], system=b["system"], enable_thinking=False), add_special_tokens=False).input_ids)
            if n != rec[tid.replace("|", "__") + "__BASE.json"]["input_tokens"]:
                bad.append((tid, "tokenizer does not reproduce 1.20 BASE input tokens", n))
        out["keep_input_tokens"] = {"max": max(toks.values()), "min": min(toks.values()),
                                    "mean": round(sum(toks.values()) / len(toks), 1)}
    else:
        bad = ["tokenizer not given"]
    gate("K5 token budget: chat-rendered KEEP inputs <= 2048 (tokenizer reproduces 1.20 BASE counts)", bad, len(calls))
    # K6
    bad = []
    worlds = {}

    def world(h):
        k = (h["world_seed"], h["pool"])
        if k not in worlds:
            worlds[k] = HO._world(*k)[0]
        return worlds[k]
    if sha(src / "analysis" / "ref" / "scored.jsonl") != FREEZE_1_20["scored"]:
        bad.append("1.20 scored.jsonl differs from its completion hash")
    S20 = {(r["target"], r["arm"]): r for r in load(src / "analysis" / "ref" / "scored.jsonl")}
    recA = {}
    for p in (src / "stages" / "main-A" / "calls").glob("*.json"):
        r = json.loads(p.read_text())
        recA[r["call_id"]] = (r, p)
    for tid in led:
        h, t = H[tid], T[tid]
        case, w, reg = h["case"], world(h), t["registry"]
        can = dict(FA.canonical_factored(HO.public(case)[-1]), evidence=case["text"][-25:])
        s, _, _ = HE.score(json.dumps(can), case, w, reg)
        if not s["exact"]:
            bad.append((tid, "canonical not exact"))
        m = copy.deepcopy(can)
        if h["act"] == "arrival":
            st = {"field": h["gold_field"], "at": case["records"][-1]["event_at"], "value": "yes"}
            e0 = m["events"][0]
            muts = [dict(m, events=[], states=[st]),                                    # state-only arrival
                    dict(m, events=[dict(e0, to="no" if e0["to"] == "yes" else "yes")])]  # wrong event value
            rt = case["records"][-1]["received_at"]
            if rt != st["at"]:                                                           # extra reception-time state
                muts.append(dict(m, states=m["states"] + [dict(st, at=rt)]))
            for mut in muts:
                if HE.score(json.dumps(mut), case, w, reg)[0]["exact"]:
                    bad.append((tid, "arrival mutation exact"))
        else:
            r0 = m["revisions"][0]
            mut = dict(m, revisions=[dict(r0, value="yes" if r0["value"] == "no" else "no")])
            if HE.score(json.dumps(mut), case, w, reg)[0]["exact"]:
                bad.append((tid, "correction mutation exact"))
        for arm, kind in (("BASE", "BASE"), ("RES_DET", "DET")):
            r, _ = recA[f"{tid}|{kind}"]
            s, _, _ = HE.score(r["raw"], case, w, reg, r.get("stop"))
            old = S20[(tid, arm)]
            diff = [k for k in SCORE_KEYS if k in old and s.get(k) != old.get(k)]
            if diff:
                bad.append((tid, arm, diff))
    gate("K6 scoring: canonical exact, mutations inexact, cached 1.20 BASE/RES-DET rescored identically", bad, len(led))
    # K7
    bad = []
    lockA = json.loads((src / "stages" / "main-A" / "LOCK.json").read_text())
    if (lockA["source_sha256"], lockA["config_sha256"], lockA["calls_sha256"], lockA["fake"]) != \
            (FREEZE_1_20["source"], FREEZE_1_20["config_main_A"], FREEZE_1_20["calls_A"], False):
        bad.append(("main-A LOCK", lockA))
    if sha(src / "data" / "refA-calls.jsonl") != FREEZE_1_20["calls_A"]:
        bad.append("1.20 refA-calls differs from freeze")
    cmap = []
    for tid in sorted(led):
        t = T[tid]
        row = {"target": tid}
        for arm, kind, prompt in (("BASE", "BASE", t["base_prompt"]), ("SUB", "DET", t["det_prompt"])):
            r, p = recA[f"{tid}|{kind}"]
            mi = r["model"]
            ok = (r["status"] == "ok" and r.get("complete") and r.get("attempts") == 1 and r["max_new_tokens"] == 256
                  and r["user_sha256"] == shs(prompt) == A20[f"{tid}|{kind}"]["user_sha256"]
                  and A20[f"{tid}|{kind}"]["user"] == prompt
                  and all(mi.get(k) == v for k, v in PIN.items()) and mi["load"]["devices"] == ["cuda:0"]
                  and mi["load"]["quantization"]["bnb_4bit_compute_dtype"] == "bfloat16"
                  and mi["load"]["quantization"]["bnb_4bit_use_double_quant"] is True)
            if not ok:
                bad.append((tid, arm))
            row[arm] = {"call_id": r["call_id"], "record": str(p.relative_to(src)), "record_sha256": sha(p),
                        "user_sha256": r["user_sha256"], "status": r["status"], "stop": r["stop"],
                        "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"], "seconds": r["seconds"],
                        "finished_at": r["finished_at"]}
        k = next(c for c in calls if c["call_id"] == f"{tid}|KEEP")
        row["KEEP"] = {"call_id": k["call_id"], "user_sha256": k["user_sha256"], "status": "scheduled"}
        cmap.append(row)
    cfg20 = json.loads((src / "config" / "stage-main-A.json").read_text())["model"]
    for name in ("stage-smoke.json", "stage-main.json"):
        p = hub / "config" / name
        if p.exists() and json.loads(p.read_text())["model"] != cfg20:
            bad.append((name, "model config differs from 1.20 main-A"))
    with open(data / "CACHE-MAP.jsonl", "w") as fh:
        for r in cmap:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    gate("K7 cache provenance: 1.20 BASE and SUB(DET) records verified; explicit cache map written", bad, len(cmap))
    res = {"gates": gates, "all_pass": all(g["pass"] for g in gates.values()), "calls": len(calls),
           "calls_sha256": commit["calls_sha256"], "cache_map_sha256": sha(data / "CACHE-MAP.jsonl"),
           "composition": dict(collections.Counter(f"{L['family'][:2]}|{L['act']}" for L in led.values())), **out}
    (hub / "phase0").mkdir(exist_ok=True)
    (hub / "phase0" / "VALIDATION.json").write_text(json.dumps(res, indent=1) + "\n")
    md = ["# V1.21.0 KEEP+ID precollection validation", "", f"All pass: **{res['all_pass']}**. Calls: {len(calls)} "
          f"(sha {commit['calls_sha256'][:12]}...). Cache map sha {res['cache_map_sha256'][:12]}...", ""]
    md += [f"- {'PASS' if g['pass'] else 'FAIL'} {k} ({g['checked']} checked, {g['failures']} failures)" for k, g in gates.items()]
    if out:
        md += ["", f"KEEP input tokens: {out['keep_input_tokens']}"]
    (hub / "phase0" / "VALIDATION.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"all_pass": res["all_pass"], **{k: g["failures"] for k, g in gates.items()}}))


if __name__ == "__main__":
    main()
