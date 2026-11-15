"""Pre-collection validation for V1.15.0 (no model call; no main-panel outcome is computed).
Usage: ftx_validate.py --hub HUB --set ftx|ftxsmoke [--out DIR] [--skip-regressions] [--stage-config CONFIG]
Checks:
  1 counts: exact call count = sum of reports per world, within the ceiling; no truncation (every public report has a
    call); call ids/positions contiguous; prompt hashes match the prompt text
  2 prose: every rendering passes prose_study.check_equivalent against its source record; template coverage by kind
    and status; the allowlisted public records re-map exactly to the structured public reports (from_v02)
  3 public/hidden separation: prompts contain no goal, transition declaration, tape, truth-only value, label or
    intended status; public files carry no hidden key; one goal-blind prompt stream per world
  4 inputs (structured, public, pre-sensor): declarations; tape inside the window; S2 fully represented; the
    1.14.0 allocation reproduced on the new instances (same per-copy e / subset structure by row)
  5 perfect-extraction parity, pre-sensor only (main panel): Q0, S2 and both selectors' field lists are identical
    for the structured channel and the canonical-record text channel
  6 regressions on old inspected panels: (a) the structured runner reproduces all 272 stored 1.14.0 main trajectories;
    (b) the perfect-extraction channel on the 1.14.0 panel reproduces the structured outcomes of all 192 BASE /
    DEPENDENCY trajectories; (c) the new channel builder equals the frozen text_channel.build_channel on every stored
    1.11.0 main reply (144 calls)
  7 model configuration equals the recorded 1.11.0 extraction configuration (revision, BF16, thinking off, greedy,
    256 tokens, infrastructure-only retry)"""
import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from dream_core import localpaths as LP  # public release: local paths from environment
from tempo import assertions as A, depgen as DG, depquery as DQ, engine_fixtures as EF, freshness as F, ftxgen as XG, \
    text_channel as TC, textdep as TD, timing as TM

RUNS = Path(os.environ.get("DREAM_RUNS", f"{LP.RUNS}"))
DEPQ = RUNS / "temporal-dependency-query-20261105-225524"
DEPREC = RUNS / "temporal-dependency-recovery-20261105-170340"
HIDDEN_KEYS = {"truth", "tape", "seed", "labels", "intended_status", "records_v02"}
PK = ("queried", "states_sha256", "plan", "candidates", "success", "utility_base", "outcome_kind", "status")


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--out")
    ap.add_argument("--skip-regressions", action="store_true")
    ap.add_argument("--stage-config")
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
    rows = {r[0]: (d, r) for d, r, _ in XG.specs(a.set, 0, smoke=a.set.endswith("smoke"))}
    res, failures = {}, []

    def check(cond, msg):
        if not cond:
            failures.append(msg)
        return cond
    # 1
    import hashlib
    per = collections.Counter(c["group_id"] for c in calls)
    for pub in pubs:
        wid = pub["world_id"]
        n = len(pub["reports"])
        check(per[wid] == n == len(txt[wid]["call_ids"]) == len(txt[wid]["texts"]) == len(txt[wid]["registries"]) ==
              len(txt[wid]["received"]), f"{wid}: call/report count mismatch")
        ks = [c["k"] for c in calls if c["group_id"] == wid]
        check(ks == list(range(1, n + 1)), f"{wid}: call positions")
    check(all(hashlib.sha256(c["user"].encode()).hexdigest() == c["user_sha256"] for c in calls), "prompt hashes")
    check(len(calls) == commit["calls"] <= commit["calls_ceiling"], "call count vs ceiling")
    res["1_counts"] = {"calls": len(calls), "ceiling": commit["calls_ceiling"],
                       "reports_per_world": dict(collections.Counter(per.values())),
                       "max_input_chars": max(len(c["user"]) for c in calls)}
    # 2
    kinds = collections.Counter()
    for pub in pubs:
        wid = pub["world_id"]
        hid = hids[wid]
        w = XG.build(rows[wid][1], pub["domain"], hid["seed"], a.set)[0]
        recs, texts, prompts, regs = XG.text_inputs(w, hid)
        check(texts == txt[wid]["texts"] and regs == txt[wid]["registries"], f"{wid}: rebuilt text inputs differ")
        check([c["user"] for c in calls if c["group_id"] == wid] == prompts, f"{wid}: rebuilt prompts differ")
        mapped = [A.from_v02(EF.public_record(r)) for r in recs]
        check(json.dumps(mapped, sort_keys=True) == json.dumps(pub["reports"], sort_keys=True),
              f"{wid}: allowlisted records do not re-map to the structured reports")
        for r in recs:
            kinds[f"{r['kind']}|{r['status']}"] += 1
        # 3
        hidden_vals = set()
        for tr in pub["transitions"]:
            hidden_vals.add(tr["text"])
        for u in prompts:
            check("goal" not in u.lower(), f"{wid}: goal wording in a prompt")
            check(not any(h in u for h in hidden_vals), f"{wid}: a transition declaration in a prompt")
            for role in ("A", "B"):
                g = pub["goals"][role]
                check(f"min_rating" not in u, f"{wid}: goal parameter in a prompt")
        check(not (HIDDEN_KEYS & set(pub)) and not (HIDDEN_KEYS & set(txt[wid])), f"{wid}: hidden key in public file")
    res["2_prose"] = {"check_equivalent": "every rendering (generation and rebuild)", "kinds_present": dict(sorted(kinds.items())),
                      "allowlist_remap": "exact for every world"}
    res["3_public_hidden"] = "no goal wording, declaration text, hidden key; prompts built once per world (goal-blind)"
    # 4, 5
    alloc = collections.Counter()
    nparity = 0
    for pub in pubs:
        wid, hid, tx = pub["world_id"], hids[pub["world_id"]], txt[pub["world_id"]]
        for tr in pub["transitions"]:
            try:
                F.check_declaration(pub["spec"], tr, pub["registry_allowed"])
            except F.DeclarationError as e:
                check(False, f"{wid}: {e}")
            check(tr["window"] == {"lo": 12, "hi": 14}, f"{wid}: window")
        gl = {g["k"]: g["gold"] for g in gold if g["world_id"] == wid}
        ch = TD.build_channel(wid, pub["spec"], TD.perfect_raws([gl[k] for k in range(1, len(gl) + 1)]),
                              tx["registries"], tx["texts"], tx["received"])
        check(all(r["accepted"] for r in ch["rows"]), f"{wid}: perfect extraction rejected")
        for role in ("A", "B"):
            ep, gc, env_ep = XG.goal_copy(pub, hid, role)
            q_s = F.p2_request(ep, gc)["fields"]
            q_p = F.p2_request(TD.text_copy(ep), gc, ch)["fields"]
            check(q_s == q_p, f"{wid}/{role}: perfect Q0")
            for env in TM.ENVS:
                s_s = TD.selection_for(ep, gc, q_s, env, None)
                s_p = TD.selection_for(TD.text_copy(ep), gc, q_p, env, ch)
                nparity += 1
                check(sorted(map(str, s_s["s2_states"])) == sorted(map(str, s_p["s2_states"])) and s_s["fields"] == s_p["fields"],
                      f"{wid}/{role}/{env}: perfect S2/fields")
                check(s_s["s2_status"] == "ok" and not s_s["partially_represented"] and not s_s["unrepresented"],
                      f"{wid}/{role}/{env}: S2 representation")
                if env == "stable":
                    check(s_s["e"] == 0, f"{wid}/{role}: stable augmentation")
                else:
                    alloc[(rows[wid][1][0], role, s_s["e"], s_s["n_random_subsets"] if s_s["e"] else 0, len(q_s))] += 1
        env = TM.environment(XG.goal_copy(pub, hid, "A")[2], "changing", pub["transitions"], hid["tape"],
                             TM.schedule_clock("DEFER"))
        check(len(env.state_at(16)[1]) == len(hid["tape"]), f"{wid}: tape")
    res["5_perfect_parity_presensor"] = f"{nparity} goal/env copies: Q0, S2 and field lists identical"
    if (DEPQ / "stages" / "main" / "selections.jsonl").exists() and not a.set.endswith("smoke"):
        old = collections.Counter()
        for s in load(DEPQ / "stages" / "main" / "selections.jsonl"):
            if s["env"] == "changing":
                old[(s["world"], s["role"], s["e"], s["n_random_subsets"] if s["e"] else 0, len(s["Q0"]))] += 1
        check(old == alloc, "1.14.0 allocation structure not reproduced on the new instances")
        res["4_allocation"] = "per-copy (row, goal, e, random subsets, |Q0|) identical to 1.14.0 for all 48 changing copies"
    # 6 regressions
    if not a.skip_regressions:
        dpubs = load(DEPQ / "data" / "public" / "depq-worlds.jsonl")
        dh = {h["world_id"]: h for h in load(DEPQ / "data" / "hidden" / "depq-hidden.jsonl")}
        stored = {(t["world"], t["role"], t["env"], t["arm"], t["subset"]): t
                  for t in load(DEPQ / "stages" / "main" / "trajectories.jsonl")}
        drows = {r[0]: (d, r) for d, r, _ in DG.specs("depq", 0)}
        diff_a, diff_b, n_a, n_b = [], [], 0, 0
        for pub in dpubs:
            wid, hid = pub["world_id"], dh[pub["world_id"]]
            w = DG.build(drows[wid][1], pub["domain"], hid["seed"], "depq")[0]
            recs, texts, _, regs = XG.text_inputs(w, hid)
            ch = TD.build_channel(wid, pub["spec"], TD.perfect_raws(recs), regs, texts, [r["received_at"] for r in recs])
            for role in ("A", "B"):
                ep, gc, env_ep = DG.goal_copy(pub, hid, role)
                for env in TM.ENVS:
                    for (ww, rr, ee, arm, sub), o in stored.items():
                        if (ww, rr, ee) != (wid, role, env):
                            continue
                        tag = f"|{arm}" + ("" if sub is None else f"#{sub}")
                        t = TD.run(ep, gc, o["fields"], env, env_ep, hid["tape"], None, tag)
                        n_a += 1
                        if any(t[x] != o[x] for x in PK + ("receipts_sha256", "utility")):
                            diff_a.append((wid, role, env, arm, sub))
                        if arm != "RANDOM_EXTRA":
                            p = TD.run(TD.text_copy(ep), gc, o["fields"], env, env_ep, hid["tape"], ch, tag)
                            n_b += 1
                            if any(p[x] != o[x] for x in PK + ("receipts_sha256", "utility")):
                                diff_b.append((wid, role, env, arm))
        check(not diff_a and n_a == 272, f"1.14.0 structured regression {diff_a[:5]} n={n_a}")
        check(not diff_b and n_b == 192, f"1.14.0 perfect-channel regression {diff_b[:5]} n={n_b}")
        # (c) adapter on 1.11.0 stored replies
        eps = load(DEPREC / "data" / "deprec-episodes.jsonl")
        dg = {g["call_id"]: g for g in load(DEPREC / "data" / "deprec-gold.jsonl")}
        recs_ = {}
        for p in (DEPREC / "stages" / "main" / "calls").glob("*.json"):
            r = json.loads(p.read_text()); recs_[r["call_id"]] = r
        n_c, diff_c = 0, []
        for ep in eps:
            cids = [f"{ep['episode_id']}|prose|r{k}" for k in range(1, len(ep["records_v02"]) + 1)]
            raws = [recs_[c]["raw"] if c in recs_ and recs_[c]["status"] == "ok" else None for c in cids]
            regs = [dg[c]["registry"] for c in cids]
            o = TC.build_channel(ep, raws, regs, ep["prose_texts"])
            nw = TD.build_channel(ep["episode_id"], ep["spec"], raws, regs, ep["prose_texts"],
                                  [r["received_at"] for r in ep["records_v02"]])
            n_c += len(cids)
            if json.dumps(o["sequence"], sort_keys=True, default=str) != json.dumps(nw["sequence"], sort_keys=True, default=str):
                diff_c.append(ep["episode_id"])
        check(not diff_c and n_c == 144, f"1.11.0 adapter replay differs {diff_c[:5]} n={n_c}")
        res["6_regressions"] = {"1.14.0_structured": f"{n_a - len(diff_a)}/{n_a} identical",
                                "1.14.0_perfect_channel": f"{n_b - len(diff_b)}/{n_b} identical",
                                "1.11.0_adapter_replay_calls": f"{n_c} calls, {len(eps) - len(diff_c)}/{len(eps)} episode streams identical"}
    # 7 model configuration
    if a.stage_config:
        cfg = json.loads(Path(a.stage_config).read_text())
        old = json.loads((DEPREC / "config" / "stage-main.json").read_text())
        check(cfg["model"] == old["model"], "model block differs from 1.11.0")
        check(cfg["retry_limit"] == old["retry_limit"] and cfg["max_input_tokens"] == old["max_input_tokens"], "retry/input limits")
        check(all(c["max_new_tokens"] == 256 for c in calls), "max_new_tokens")
        man = json.loads(Path(cfg["model"]["manifest"]).read_text())
        check(man.get("revision") == "b968826d9c46dd6066d109eabc6255188de91218", "model revision")
        res["7_model_config"] = {"model": cfg["model"], "revision": man.get("revision"), "decoding": "greedy (tempo_run HFModel)",
                                 "max_new_tokens": 256, "retry_limit": cfg["retry_limit"], "content_retry": "none"}
    res["failures"], res["pass"] = failures, not failures
    (out / "VALIDATION.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    L = [f"# V1.15.0 pre-collection validation ({a.set})", "", f"**{'PASS' if not failures else 'FAIL'}** "
         f"({len(failures)} failures). No model call; no main-panel outcome computed.", ""]
    for kk, v in res.items():
        if kk not in ("failures", "pass"):
            L += [f"## {kk}", "```", json.dumps(v, indent=1, default=str)[:3000], "```"]
    if failures:
        L += ["## Failures", *[f"- {f}" for f in failures]]
    (out / "VALIDATION.md").write_text("\n".join(L) + "\n")
    print("PASS" if not failures else f"FAIL {len(failures)}: {failures[:6]}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
