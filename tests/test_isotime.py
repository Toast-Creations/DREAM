"""dream_core.isotime: identical parsing of DREAM's timestamp formats on Python 3.10 and 3.11+."""
from datetime import datetime, timedelta, timezone
import unittest

from dream_core.isotime import fromisoformat

NY_WINTER = timezone(timedelta(hours=-5))


class IsoTime(unittest.TestCase):
    def test_colonless_offset_from_strftime(self):
        self.assertEqual(fromisoformat("2026-11-15T17:03:34-0500"),
                         datetime(2026, 11, 15, 17, 3, 34, tzinfo=NY_WINTER))

    def test_colon_offset_and_isoformat_roundtrip(self):
        dt = datetime(2026, 11, 11, 7, 0, 0, tzinfo=NY_WINTER)
        self.assertEqual(fromisoformat(dt.isoformat()), dt)
        self.assertEqual(fromisoformat("2026-11-11T07:00:00-05:00"), dt)

    def test_utc_z_suffix(self):
        self.assertEqual(fromisoformat("2026-11-15T22:03:34Z"),
                         datetime(2026, 11, 15, 22, 3, 34, tzinfo=timezone.utc))

    def test_positive_offset_and_microseconds(self):
        self.assertEqual(fromisoformat("2026-11-15T17:03:34.250000+0130"),
                         datetime(2026, 11, 15, 17, 3, 34, 250000, tzinfo=timezone(timedelta(hours=1, minutes=30))))

    def test_naive_and_date_only_unchanged(self):
        self.assertEqual(fromisoformat("2026-11-15T17:03:34"), datetime(2026, 11, 15, 17, 3, 34))
        self.assertEqual(fromisoformat("2026-11-15"), datetime(2026, 11, 15))

    def test_invalid_input_still_raises(self):
        for bad in ("not a time", "2026-11-15T25:00:00-0500", ""):
            with self.assertRaises(ValueError):
                fromisoformat(bad)
        with self.assertRaises(TypeError):
            fromisoformat(1794536247)


if __name__ == "__main__":
    unittest.main()
