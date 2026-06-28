import unittest

from aisteno.pack import PACK_LEGEND, pack
from aisteno.report import calculate_pack_stats, format_pack_stats
from aisteno.wordlist import WORDLIST


class PackTests(unittest.TestCase):
    def test_wordlist_has_at_least_300_mappings(self):
        self.assertGreaterEqual(len(WORDLIST), 300)

    def test_normal_memory_reduction_at_least_50_percent(self):
        with open("examples/normal_user_memory_sample.md", encoding="utf-8") as stream:
            stats = calculate_pack_stats(stream.read())
        self.assertGreaterEqual(stats.percent_reduction, 50.0)

    def test_normal_memory_matches_expected_fixture(self):
        with open("examples/normal_user_memory_sample.md", encoding="utf-8") as stream:
            result = pack(stream.read()).text
        with open("examples/packed_expected_sample.txt", encoding="utf-8") as stream:
            self.assertEqual(result, stream.read())

    def test_miahou_example_reduction_at_least_40_percent(self):
        with open("examples/miahou_memory_sample.md", encoding="utf-8") as stream:
            stats = calculate_pack_stats(stream.read())
        self.assertGreaterEqual(stats.percent_reduction, 40.0)

    def test_preserves_important_paths(self):
        path = "/home/professor/Projects/Miahou/config/settings.json"
        result = pack(f"The important project path is {path}\n").text
        self.assertIn(path, result)

    def test_preserves_device_model_names(self):
        for model in ("Lenovo ThinkPad X1 Carbon", "Google Pixel 8 Pro"):
            with self.subTest(model=model):
                self.assertIn(model, pack(f"The primary device model is {model}.\n").text)

    def test_preserves_email_addresses(self):
        email = "professor+codex@example.com"
        self.assertIn(email, pack(f"The work account email is {email}.\n").text)

    def test_preserves_hostname_and_command_snippet(self):
        hostname = "professor-ASUS-Zenbook-14-UM3406KA"
        command = "DISPLAY=:0 xdg-open"
        result = pack(f"Hostname: {hostname}. Use {command}.\n").text
        self.assertIn(hostname, result)
        self.assertIn(command, result)

    def test_preserves_quoted_user_phrases(self):
        result = pack('User says "approved" and "go all the way".\n').text
        self.assertIn('"approved"', result)
        self.assertIn('"go all the way"', result)

    def test_merges_duplicate_preferences(self):
        text = "- User prefers concise answers.\n- The user prefers concise answers.\n"
        result = pack(text)
        self.assertEqual(result.records_created, 1)
        self.assertEqual(result.text.count("ans=concise"), 1)

    def test_removes_filler(self):
        text = "Remember that currently the user prefers short answers.\n"
        result = pack(text).text.casefold()
        self.assertNotIn("remember that", result)
        self.assertNotIn("currently", result)
        self.assertNotIn("the user prefers", result)

    def test_default_has_no_header_or_legend(self):
        result = pack("User prefers short answers.\n").text
        self.assertFalse(result.startswith("AISTENO/"))
        self.assertNotIn(PACK_LEGEND, result)
        self.assertTrue(result.startswith("PREF{"))

    def test_optional_legend(self):
        self.assertTrue(pack("User prefers short answers.\n", legend=True).text.startswith(PACK_LEGEND))

    def test_pack_stats_fields(self):
        stats = calculate_pack_stats("User prefers short answers and no fluff.\n")
        report = format_pack_stats(stats)
        for label in (
            "original chars:",
            "packed chars:",
            "chars saved:",
            "percent reduction:",
            "records created:",
            "possible lost-detail warnings:",
        ):
            self.assertIn(label, report)


if __name__ == "__main__":
    unittest.main()
