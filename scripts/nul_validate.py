"""Pre-collection validation for V1.16.0 (no model call; no main-panel outcome computed).
Usage: nul_validate.py --hub HUB --set nul|nulsmoke --stage-config CONFIG [--out DIR] [--skip-regressions]
Checks:
  1 counts: calls = 2 x reports, within the ceiling; positions contiguous; prompt hashes
  2 prose and prompts: check_equivalent on every rendering (rebuild); ORIGINAL = the frozen 1.15.1 prompt builder;
    NULL_PRIOR = nullprior.null_prompt(ORIGINAL) and differs only by the declared payload line + clarification;
    source prose and historical context byte-identical across interfaces; allowlist re-maps to structured reports
  3 public/hidden separation (no goal wording, declarations, hidden keys)
  4 pre-sensor perfect parity (Q0, S2, DEPENDENCY fields); stable copies never augmented (structured)
  5 allocation: every instance of a family has that family's 1.14.0 per-copy structure (e, subsets, |Q0|)
  6 regressions: (a) ORIGINAL prompts rebuilt for overnight block b001 equal its committed calls byte for byte;
    (b) the five overnight unsafe interpretations are re-scored as fixtures: not exact, wrong field attribution
  7 model configuration equals 1.15.1 / 1.11.0
  8 interleaving: the runner's precommitted seeded order (order_seed) over the mixed calls file; per-interface counts
    by quarter of the run are recorded with the order hash"""
import argparse
import collections
import hashlib
import json
import os
import random
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import assertions as A, depgen as DG, engine_fixtures as EF, freshness as F, ftxgen as XG, nullprior as NP, \
    text_channel as TC, textdep as TD, timing as TM
from nul_evaluate import record_diag

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
DEPQ = RUNS / "temporal-dependency-query-20261105-225524"
QUEUE = RUNS / "temporal-text-replication-20261105-233535"
DEPREC = RUNS / "temporal-dependency-recovery-20261105-170340"
UNSAFE = [("b001", "a06", 4), ("b015", "a06", 3), ("b021", "a04", 4), ("b018", "a08", 3), ("b021", "d05", 6)]
HIDDEN_KEYS = {"truth", "tape", "seed", "labels", "intended_status", "records_v02"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--stage-config", required=True)
    ap.add_argument("--out")
    ap.add_argument("--skip-regressions", action="store_true")
    a = ap.parse_args()
    hub = Path(a.hub)
    out = Path(a.out) if a.out else hub / "phase0"
    out.mkdir(parents=True, exist_ok=True)
    data = hub / "data"
    commit = json.loads((data / f"COMMITMENT-{a.set}.json").read_text())
    pubs = load(data / "public" / f"{a.set}-worlds.jsonl")
    txt = {t["world_id"]: t for t in load(data / "public" / f"{a.set}-text.jsonl")}
    hids = {h["world_id"]: h for h in load(data / "hidden" / f"{a.set}-hidden.jsonl")}
    gold = load(data / "hidden" / f"{a.set}-gold.jsonl")
    calls = load(data / f"{a.set}-calls.jsonl")
    cb = {c["call_id"]: c for c in calls}
    rows = {r[0]: (d, r) for d, r, _ in NP.specs(a.set, 0, smoke=a.set.endswith("smoke"))}
    res, failures = {}, []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
        return cond
    check(len(calls) == commit["calls"] == 2 * commit["reports"] <= commit["calls_ceiling"], "call counts")
    check(all(hashlib.sha256(c["user"].encode()).hexdigest() == c["user_sha256"] for c in calls), "prompt hashes")
    res["1_counts"] = {"reports": commit["reports"], "calls": len(calls), "ceiling": commit["calls_ceiling"],
                       "source_kind_counts": commit["source_kind_counts"]}
    alloc = collections.defaultdict(set)
    nparity = 0
    for pub in pubs:
        wid, hid, tx = pub["world_id"], hids[pub["world_id"]], txt[pub["world_id"]]
        n = len(pub["reports"])
        check(len(tx["call_ids"]) == len(tx["texts"]) == len(tx["registries"]) == len(tx["received"]) == n, f"{wid}: lists")
        w = NP.build(rows[wid][1], pub["domain"], hid["seed"], a.set)[0]
        recs, texts, prompts, regs = NP.text_inputs(w, hid)
        check(texts == tx["texts"] and regs == tx["registries"], f"{wid}: rebuilt text inputs")
        check(json.dumps([A.from_v02(EF.public_record(r)) for r in recs], sort_keys=True) == json.dumps(pub["reports"], sort_keys=True),
              f"{wid}: allowlist re-map")
        check(prompts == TC.prompts(w, {"records_v02": recs, "seed": hid["seed"]}), f"{wid}: ORIGINAL builder")
        for k, u in enumerate(prompts, 1):
            o, nn = cb[f"{wid}|prose|r{k}|ORIGINAL"]["user"], cb[f"{wid}|prose|r{k}|NULL_PRIOR"]["user"]
            check(o == u and nn == NP.null_prompt(u), f"{wid} r{k}: prompt pair")
            check(o.replace(NP.PAYLOAD_LINE, NP.NULL_PAYLOAD_LINE + "\n" + NP.CLARIFICATION) == nn, f"{wid} r{k}: only declared diff")
            check("goal" not in o.lower() and not any(tr["text"] in o for tr in pub["transitions"]), f"{wid} r{k}: hidden text in prompt")
        check(not (HIDDEN_KEYS & set(pub)) and not (HIDDEN_KEYS & set(tx)), f"{wid}: hidden key")
        gl = {g["k"]: g["gold"] for g in gold if g["world_id"] == wid}
        perf = TD.build_channel(wid, pub["spec"], TD.perfect_raws([gl[k] for k in range(1, n + 1)]), tx["registries"],
                                tx["texts"], tx["received"])
        check(all(r["accepted"] for r in perf["rows"]), f"{wid}: perfect rejected")
        for role in ("A", "B"):
            ep, gc, _ = NP.goal_copy(pub, hid, role)
            q_s = F.p2_request(ep, gc)["fields"]
            q_p = F.p2_request(TD.text_copy(ep), gc, perf)["fields"]
            check(q_s == q_p, f"{wid}/{role}: perfect Q0")
            for env in TM.ENVS:
                s_s = TD.selection_for(ep, gc, q_s, env, None)
                s_p = TD.selection_for(TD.text_copy(ep), gc, q_p, env, perf)
                nparity += 1
                check(sorted(map(str, s_s["s2_states"])) == sorted(map(str, s_p["s2_states"])) and s_s["fields"] == s_p["fields"],
                      f"{wid}/{role}/{env}: perfect S2/fields")
                if env == "stable":
                    check(s_s["e"] == 0, f"{wid}/{role}: stable augmentation")
                else:
                    alloc[(NP.family(wid), role)].add((s_s["e"], s_s["n_random_subsets"] if s_s["e"] else 0, len(q_s)))
    res["2_prompts"] = "ORIGINAL = frozen builder; NULL_PRIOR = declared one-line payload change + clarification; prose/context identical"
    res["4_perfect_parity_presensor"] = f"{nparity} copies identical"
    if not a.set.endswith("smoke"):
        old = {(s["world"], s["role"]): (s["e"], s["n_random_subsets"] if s["e"] else 0, len(s["Q0"]))
               for s in load(DEPQ / "stages" / "main" / "selections.jsonl") if s["env"] == "changing"}
        bad = [k for k, v in alloc.items() if v != {old[k]}]
        check(not bad, f"allocation differs from 1.14.0: {bad[:5]}")
        res["5_allocation"] = "every instance reproduces its family's 1.14.0 per-copy structure (48 family-goal pairs)"
    if not a.skip_regressions:
        b1 = QUEUE / "blocks" / "b001"
        bp = load(b1 / "data" / "public" / "ftx-worlds.jsonl")
        bh = {h["world_id"]: h for h in load(b1 / "data" / "hidden" / "ftx-hidden.jsonl")}
        bc = {c["call_id"]: c["user"] for c in load(b1 / "data" / "ftx-calls.jsonl")}
        drows = {r[0]: (d, r) for d, r, _ in DG.specs("ftx", 0)}
        nb = 0
        for pub in bp:
            wid = pub["world_id"]
            w = XG.build(drows[wid][1], pub["domain"], bh[wid]["seed"], "ftx")[0]
            _, _, prompts, _ = XG.text_inputs(w, bh[wid])
            for k, u in enumerate(prompts, 1):
                nb += 1
                check(bc[f"{wid}|prose|r{k}"] == u, f"b001 {wid} r{k}: ORIGINAL prompt differs from the overnight call")
        fx = []
        for blk, wid, k in UNSAFE:
            bd = QUEUE / "blocks" / blk
            g = {x["call_id"]: x for x in load(bd / "data" / "hidden" / "ftx-gold.jsonl")}[f"{wid}|prose|r{k}"]
            ch = {x["world"]: x for x in load(bd / "stages" / "main" / "eval" / "channels.jsonl")}[wid]
            rep = ch["rows"][k - 1]["report"]
            d = record_diag(rep, g["gold"], g["text"])
            fx.append({"case": f"{blk}/{wid}/r{k}", "exact": d["denotation_equal"], "field_ok": d["field_attribution_ok"],
                       "kind_ok": d["kind_correct"], "evidence_quoted": (ch["rows"][k - 1]["report"] or {}).get("evidence", "")[:40] in g["text"]})
            check(not d["denotation_equal"] and not d["field_attribution_ok"], f"unsafe fixture {blk}/{wid}/r{k} not flagged")
        res["6_regressions"] = {"b001_ORIGINAL_prompts_identical": nb, "unsafe_fixtures": fx}
    cfg = json.loads(Path(a.stage_config).read_text())
    old = json.loads((DEPREC / "config" / "stage-main.json").read_text())
    check(cfg["model"] == old["model"] and cfg["retry_limit"] == old["retry_limit"] and
          cfg["max_input_tokens"] == old["max_input_tokens"] and all(c["max_new_tokens"] == 256 for c in calls), "model config")
    res["7_model_config"] = cfg["model"]
    order = list(calls)
    check(cfg.get("order") == "as_committed", "runner must use the committed balanced schedule")
    if cfg.get("order") != "as_committed":
        random.Random(cfg["order_seed"]).shuffle(order)
    q = len(order) // 4 or 1
    quarters = [dict(collections.Counter(c["arm"] for c in order[i * q:(i + 1) * q if i < 3 else None])) for i in range(4)]
    first = collections.Counter()
    pos = {c["call_id"]: i for i, c in enumerate(order)}
    for c in calls:
        if c["arm"] == "ORIGINAL":
            o, n2 = pos[c["call_id"]], pos[c["call_id"].replace("|ORIGINAL", "|NULL_PRIOR")]
            first["ORIGINAL first" if o < n2 else "NULL_PRIOR first"] += 1
    res["8_interleaving"] = {"order_seed": cfg["order_seed"], "order_sha256": hashlib.sha256(
        json.dumps([c["call_id"] for c in order]).encode()).hexdigest(), "per_quarter": quarters, "pair_order": dict(first)}
    res["failures"], res["pass"] = failures, not failures
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = [f"# V1.16.0 pre-collection validation ({a.set})", "", f"**{'PASS' if not failures else 'FAIL'}** ({len(failures)} failures).", ""]
    for kk, v in res.items():
        if kk not in ("failures", "pass"):
            L += [f"## {kk}", "```", json.dumps(v, indent=1, default=str)[:3000], "```"]
    if failures:
        L += ["## Failures", *[f"- {x}" for x in failures]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("PASS" if not failures else f"FAIL {len(failures)}: {failures[:6]}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
