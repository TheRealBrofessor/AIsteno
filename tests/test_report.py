import unittest

from aisteno.report import calculate_stats, format_stats


class ReportTests(unittest.TestCase):
    def test_stats(self):
        text = ("Professor prefers low-token mode. no fluff. Autonode backup memory.\n" * 20)
        stats = calculate_stats(text)
        self.assertEqual(stats.original_characters, len(text))
        self.assertGreater(stats.characters_saved, 0)
        self.assertGreater(stats.percent_reduction, 0)
        self.assertTrue(stats.roundtrip_matches)
        report = format_stats(stats)
        self.assertIn("original character count:", report)
        self.assertIn("roundtrip decode matches original: yes", report)


if __name__ == "__main__":
    unittest.main()
