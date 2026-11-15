"""No-model fixtures for V1.21.0 KEEPID-v1 (annotation wording, placement, preservation, public-only identity)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from tempo import keepid as KI  # noqa: E402

REG = ["Tolo.part", "Alpa.on_hand", "Beta.on_hand"]
R01 = "Message r01, received at time 2: confirmed (verified) event: at time 2, another technician fitted part Alpa into slot Tolo, using their own stock."
TGT = "Message r02, received at time 9: it is verified that at time 9 the part that slot Tolo held at time 2 was delivered to you, so it is now on hand."
BASE = ("WORLD\n\nRecords received before this one (context only):\n" + R01 + "\n\nNew record to convert:\n" + TGT +
        "\n\nQUERY (record extraction)\nReply with JSON.")


def pub(target=TGT, prefix=((("r01", R01),))):
    return {"target": "x|arrival|A", "component": "primary", "act": "arrival", "group": "x", "family": "F3",
            "reception": "immediate", "history": "A", "stratum": "F3|immediate",
            "prefix": [{"record_id": r, "raw_text": t} for r, t in prefix], "target_text": target,
            "registry_order": REG, "base_prompt": BASE.replace(TGT, target)}


class KeepId(unittest.TestCase):
    def test_annotation_wording_frozen(self):
        self.assertEqual(KI.annotation("the part that slot Tolo held at time 2", "Alpa.on_hand"),
                         'Resolved reference: "the part that slot Tolo held at time 2" = part Alpa (field Alpa.on_hand).')
        with self.assertRaises(AssertionError):
            KI.annotation("x", "Tolo.part")

    def test_placement_and_preservation(self):
        prompt, led = KI.build(pub())
        lines = prompt.split("\n")
        j = lines.index(KI.ANCHOR)
        self.assertEqual(lines[j - 1], led["annotation"])
        self.assertEqual(lines[j + 1], TGT)  # original sentence unchanged
        self.assertEqual(KI.strip_annotation(prompt, led["annotation"]), BASE)
        self.assertEqual(lines[:j - 1] + lines[j:], BASE.split("\n"))
        self.assertEqual(led["field"], "Alpa.on_hand")
        self.assertNotIn("part Alpa was delivered", prompt)

    def test_identity_from_public_text_only(self):
        # same public input -> same identity; changing only the public record changes it
        p = pub()
        p_alt = pub(prefix=(("r01", R01.replace("part Alpa", "part Beta")),))
        self.assertEqual(KI.build(p)[1]["field"], "Alpa.on_hand")
        self.assertEqual(KI.build(p_alt)[1]["field"], "Beta.on_hand")
        extra = dict(p, gold_field="Beta.on_hand", case={"field": "Beta"})
        self.assertEqual(KI.build(extra), KI.build(p))  # non-public keys are ignored

    def test_no_identity_no_prompt(self):
        self.assertIsNone(KI.build(pub(prefix=())))  # missing support -> RES-DET refuses -> no KEEP prompt

    def test_build_calls_select_and_order(self):
        import kid_generate as KG
        rows = [pub(), dict(pub(), target="x|removal|A", act="removal"), dict(pub(), target="y|correction|B", act="correction",
                                                                                group="y", history="B")]
        calls, led = KG.build_calls(rows)
        self.assertEqual(sorted(c["call_id"] for c in calls), ["x|arrival|A|KEEP", "y|correction|B|KEEP"])
        self.assertEqual(KG.build_calls(rows)[0], calls)  # deterministic
        self.assertTrue(all(c["max_new_tokens"] == 256 and c["arm"] == "KEEP" for c in calls))


if __name__ == "__main__":
    unittest.main()
