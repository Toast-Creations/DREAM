"""CPU stub tests for the V1.20.0 resource guard (no model)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tempo import refguard as RG  # noqa: E402


def hub_with(records, failed):
    h = Path(tempfile.mkdtemp())
    (h / "stages" / "smoke-A" / "calls").mkdir(parents=True)
    for i in range(records):
        (h / "stages" / "smoke-A" / "calls" / f"c{i}.json").write_text("{}")
    (h / "stages" / "smoke-A" / "attempts.jsonl").write_text("\n".join("{}" for _ in range(failed)))
    return h


def calls(h, n):
    p = h / "calls.jsonl"
    p.write_text("\n".join(json.dumps({"call_id": str(i)}) for i in range(n)) + "\n")
    return p


class Guard(unittest.TestCase):
    def test_counts_records_and_failed_attempts(self):
        h = hub_with(140, 3)
        self.assertEqual(RG.used_attempts(h), 143)
        r = RG.check(h, calls(h, 1200), 2e9, now=1e9)
        self.assertTrue(r["ok"]); self.assertEqual(r["remaining_attempts"], 1601)

    def test_stops_before_excess_attempt(self):
        h = hub_with(144, 1)
        r = RG.check(h, calls(h, 1600), 2e9, now=1e9)
        self.assertFalse(r["ok"]); self.assertEqual(r["reason"], "attempt budget")

    def test_deadline_stop(self):
        h = hub_with(10, 0)
        r = RG.check(h, calls(h, 5), 1000.0, now=1001.0)
        self.assertFalse(r["ok"]); self.assertEqual(r["reason"], "deadline")


if __name__ == "__main__":
    unittest.main()
