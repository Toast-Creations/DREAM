"""No-model protections for V1.15.0 frozen-text integration (brief sections 3-5). Fixture worlds use a test-only pool;
they are not the committed panel."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempo import depquery as DQ, freshgen as FG, freshness as F, ftxgen as XG, recovery as R, text_channel as TC, \
    textdep as TD, timing as TM  # noqa: E402

POOL, SEED = "ftxtest", 8181
FG.CONS[POOL] = "bcdfghk"
fx = lambda *r: tuple(r) + (("fx", "fx"),)
COMPETE_D = fx("u-d1", ("B", "ver"), ("YOU", "ver"), [("EA", "B", "YOU"), ("EB", "YOU", "B")], [(0, 0.5)])
STOCK_A = fx("u-a1", {"T": ("empty", "prov"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
             [("on_hand", "G", "yes", "no"), ("on_hand", "D", "yes", "no")], [(0, 0.5)])
UNRES_D = fx("u-d2", ("YOU", "unres:B"), ("B", "prov"), [("EB", "B", "YOU")], [(0, 1.5)])
KEYS = ("queried", "states_sha256", "plan", "candidates", "success", "utility_base", "outcome_kind", "n_states",
        "receipts_sha256", "actual_preaction_state_sha256", "status")


def make(domain, row):
    for att in range(60):
        try:
            w, pub, hid = XG.build(row, domain, SEED + att, POOL)
            return (w, pub, hid) + XG.text_inputs(w, hid)
        except AssertionError:
            continue
    raise AssertionError("cannot build")


def channel_for(pub, recs, texts, regs, raws=None):
    raws = TD.perfect_raws(recs) if raws is None else raws
    return TD.build_channel(pub["world_id"], pub["spec"], raws, regs, texts, [r["received_at"] for r in recs])


def full(pub, hid, role, env, channel, tag):
    ep, gc, env_ep = XG.goal_copy(pub, hid, role)
    if channel is not None:
        ep = TD.text_copy(ep)
    q0 = F.p2_request(ep, gc, channel)["fields"]
    sel = TD.selection_for(ep, gc, q0, env, channel)
    out = {}
    for s in TD.SELECTORS:
        t = TD.run(ep, gc, sel["fields"][s], env, env_ep, hid["tape"], channel, tag + s)
        rf = TD.reference(ep, gc, t, env, channel)
        assert sorted(map(str, rf["states"])) == sorted(map(str, t["states"])) and rf["choice"] == t["plan"] and \
            rf["classes"] == t["candidates"], "reference mismatch"
        out[s] = t
    return q0, sel, out


class FTX(unittest.TestCase):
    def test_01_structured_runner_equals_timing_run(self):
        for dom, row in (("delivery", COMPETE_D), ("assembly", STOCK_A)):
            w, pub, hid, *_ = make(dom, row)
            for role in "AB":
                ep, gc, env_ep = XG.goal_copy(pub, hid, role)
                for env in TM.ENVS:
                    for fs in ([], gc["relevant"][:2]):
                        a = TD.run(ep, gc, fs, env, env_ep, hid["tape"], None, "|x")
                        b = TM.run(ep, gc, {"fields": fs}, env, pub["transitions"], env_ep, hid["tape"], "DEFER", tag="|x")
                        for k in b:
                            if k not in ("cpu_s", "rule"):
                                self.assertEqual(a[k], b[k], k)

    def test_02_perfect_extraction_reproduces_structured(self):
        for dom, row in (("delivery", COMPETE_D), ("assembly", STOCK_A), ("delivery", UNRES_D)):
            w, pub, hid, recs, texts, prompts, regs = make(dom, row)
            ch = channel_for(pub, recs, texts, regs)
            self.assertTrue(all(r["accepted"] for r in ch["rows"]))
            for role in "AB":
                for env in TM.ENVS:
                    qs, ss, os_ = full(pub, hid, role, env, None, "|t")
                    qt, st, ot = full(pub, hid, role, env, ch, "|t")
                    self.assertEqual(qs, qt)
                    self.assertEqual(sorted(map(str, ss["s2_states"])), sorted(map(str, st["s2_states"])))
                    self.assertEqual(ss["fields"], st["fields"])
                    for s in TD.SELECTORS:
                        for k in KEYS:
                            self.assertEqual(os_[s][k], ot[s][k], (role, env, s, k))

    def test_03_gold_reports_poisoned_or_withheld_do_not_change_text(self):
        w, pub, hid, recs, texts, prompts, regs = make("delivery", COMPETE_D)
        ch = channel_for(pub, recs, texts, regs)
        base = full(pub, hid, "A", "changing", ch, "|t")
        bad = copy.deepcopy(pub)
        for r in bad["reports"]:
            r["assertions"] = []
        bad["reports"] = bad["reports"][:1]
        alt = full(bad, hid, "A", "changing", ch, "|t")
        self.assertEqual(base[0], alt[0])
        self.assertEqual(base[1]["fields"], alt[1]["fields"])
        for s in TD.SELECTORS:
            self.assertEqual([base[2][s][k] for k in KEYS], [alt[2][s][k] for k in KEYS])
        self.assertIsNone(TD.text_copy(pub)["reports"])

    def test_04_corrupted_channel_changes_q0_s2_and_outcome(self):
        w, pub, hid, recs, texts, prompts, regs = make("delivery", COMPETE_D)
        fa = f"{pub['goals']['A']['item']}.location"
        raws = TD.perfect_raws(recs)
        hit = None
        for k, r in enumerate(recs):
            if r["kind"] != "initial" and r["payload"].get("field") == fa:
                rr = copy.deepcopy(r)
                rr["status"] = "provisional"
                raws[k] = json.dumps(rr)
                hit = k
        self.assertIsNotNone(hit)
        ch = channel_for(pub, recs, texts, regs, raws)
        qs, ss, os_ = full(pub, hid, "A", "changing", None, "|s")
        qt, st, ot = full(pub, hid, "A", "changing", ch, "|t")
        self.assertEqual(qs, [])
        self.assertEqual(qt, [fa])  # the corrupted status makes P2 query it: gold was not used
        self.assertNotEqual(ss["fields"]["BASE"], st["fields"]["BASE"])
        self.assertNotEqual(os_["BASE"]["queried"], ot["BASE"]["queried"])

    def test_05_list_lengths_and_pending_reception_time(self):
        w, pub, hid, recs, texts, prompts, regs = make("delivery", UNRES_D)
        raws = TD.perfect_raws(recs)
        with self.assertRaises(AssertionError):
            TD.build_channel("x", pub["spec"], raws[:-1], regs, texts, [r["received_at"] for r in recs])
        raws[0] = "not json"
        recv = [r["received_at"] for r in recs]
        ch = TD.build_channel("x", pub["spec"], raws, regs, texts, recv)
        self.assertEqual(ch["rows"][0]["code"], "parse")
        pend = [s for s in ch["sequence"] if s["kind"] == "pending"]
        self.assertEqual(pend[0]["pending"]["received_at"], recv[0])
        self.assertEqual(len(ch["rows"]), len(recs))
        # identical to the frozen builder on the same inputs (adapter unchanged)
        old = TC.build_channel({"episode_id": "x", "spec": pub["spec"], "records_v02": recs}, raws, regs, texts)
        self.assertEqual(json.dumps(old["sequence"], sort_keys=True, default=str),
                         json.dumps(ch["sequence"], sort_keys=True, default=str))

    def test_06_context_isolation_between_clones(self):
        w, pub, hid, recs, texts, prompts, regs = make("assembly", STOCK_A)
        ch = channel_for(pub, recs, texts, regs)
        _, sa, oa = full(pub, hid, "A", "changing", ch, "|t")
        _, sb, ob = full(pub, hid, "B", "changing", ch, "|t")
        for s in TD.SELECTORS:
            self.assertEqual({r["field"] for r in ob[s]["receipts"]}, set(sb["fields"][s]))
            self.assertEqual({r["field"] for r in oa[s]["receipts"]}, set(sa["fields"][s]))
            self.assertTrue(all(r["context"].startswith(f"{pub['world_id']}|B|") for r in ob[s]["receipts"]))
        self.assertEqual(len(ch["sequence"]), len(recs))  # the shared stream is not extended by any clone

    def test_07_selection_reference_both_channels(self):
        for dom, row in (("delivery", COMPETE_D), ("assembly", STOCK_A), ("delivery", UNRES_D)):
            w, pub, hid, recs, texts, prompts, regs = make(dom, row)
            raws = TD.perfect_raws(recs)
            raws[-1] = None
            chs = (None, channel_for(pub, recs, texts, regs), channel_for(pub, recs, texts, regs, raws))
            for ch in chs:
                for role in "AB":
                    ep, gc, _ = XG.goal_copy(pub, hid, role)
                    if ch is not None:
                        ep = TD.text_copy(ep)
                    q0 = F.p2_request(ep, gc, ch)["fields"]
                    for env in TM.ENVS:
                        sel = TD.selection_for(ep, gc, q0, env, ch)
                        ref = TD.selection_reference(ep, gc, q0, env, ch)
                        self.assertEqual(sorted(map(str, sel["s2_states"])), sorted(map(str, ref["s2_states"])))
                        self.assertEqual((sel["R"], sel["D"], sel["fields"]["DEPENDENCY"]),
                                         (ref["R"], ref["D"], ref["DEPENDENCY"]))

    def test_08_prompts_goal_blind_and_hidden_free(self):
        w, pub, hid, recs, texts, prompts, regs = make("assembly", STOCK_A)
        for u in prompts:
            self.assertNotIn("goal", u.lower())
            self.assertNotIn("min_rating", u)
        self.assertEqual(len(prompts), len(recs))
        self.assertEqual(set(recs[0]), {"rid", "kind", "status", "event_at", "received_at", "payload"})


if __name__ == "__main__":
    unittest.main()
