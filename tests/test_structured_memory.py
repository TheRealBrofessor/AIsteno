import json
import unittest

from aisteno.facts import canonicalize
from aisteno.integrations import as_agent_memory, pack_json
from aisteno.pack import pack
from aisteno.secrets import SecretClassificationError, scan_secrets


class StructuredMemoryTests(unittest.TestCase):
    def test_conflicts_are_explicit_and_provenance_is_retained(self):
        facts = canonicalize(
            (
                ("PREF", "tone", "friendly", 1),
                ("PREF", "tone", "formal", 2),
                ("PREF", "tone", "friendly", 3),
            ),
            source="fixture.md",
            observed_at="2026-01-01T00:00:00+00:00",
        )
        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0].conflicts, ("formal",))
        self.assertEqual(len(facts[0].provenance), 2)

    def test_supersession_and_timestamp_are_structured(self):
        facts = canonicalize(
            (("STATUS", "state", "active supersedes pending", 4),),
            observed_at="2026-01-01T00:00:00+00:00",
        )
        self.assertEqual(facts[0].supersedes, ("pending",))

    def test_no_substring_merging(self):
        facts = canonicalize((("PREF", "answer", "short", 1), ("PREF", "answer", "shorter", 2)))
        self.assertEqual(len(facts), 2)

    def test_json_and_agent_adapters_are_machine_readable(self):
        payload = json.loads(pack_json("User prefers concise answers.\n"))
        self.assertEqual(payload[0]["domain"], "PREF")
        self.assertIn("facts", as_agent_memory("User prefers concise answers.\n"))

    def test_credential_formats_are_redacted(self):
        values = (
            "AKIAIOSFODNN7EXAMPLE",
            "ghp_" + "A" * 24,
            "sk_live_" + "a" * 16,
            "xoxb-" + "a" * 16,
        )
        scan = scan_secrets("\n".join(f"value={value}" for value in values))
        for value in values:
            self.assertNotIn(value, scan.redacted_text)
        self.assertEqual(len(scan.findings), len(values))

    def test_unclassified_long_value_blocks_pack(self):
        with self.assertRaises(SecretClassificationError):
            pack("opaque=" + "Z" * 60 + "\n")


if __name__ == "__main__":
    unittest.main()
