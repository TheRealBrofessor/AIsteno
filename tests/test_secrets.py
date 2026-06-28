import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from aisteno.cli import main
from aisteno.codec import decode, encode
from aisteno.pack import pack
from aisteno.secrets import format_secret_scan, scan_secrets


class SecretSafetyTests(unittest.TestCase):
    def assert_redacted(self, label: str, value: str, secret_type: str) -> None:
        source = f"Account note: {label}{value}\n"
        result = pack(source)
        self.assertNotIn(value, result.text)
        self.assertIn(f"SECRET{{type={secret_type};stored=no}}", result.text)
        self.assertEqual(result.secrets_redacted, 1)

    def test_pack_redacts_pw(self):
        self.assert_redacted("pw=", "Velvet7!Moon", "password")

    def test_pack_redacts_password(self):
        self.assert_redacted("password=", "Cedar8!River", "password")

    def test_pack_redacts_sudo(self):
        self.assert_redacted("sudo=", "Quartz9!Comet", "sudo")

    def test_pack_redacts_api_key_and_token_patterns(self):
        source = "API key: sk-test-value-123\naccess_token=tok_test_value_456\n"
        result = pack(source)
        self.assertNotIn("sk-test-value-123", result.text)
        self.assertNotIn("tok_test_value_456", result.text)
        self.assertIn("SECRET{type=api_key;stored=no}", result.text)
        self.assertIn("SECRET{type=token;stored=no}", result.text)
        self.assertEqual(result.secrets_redacted, 2)

    def test_pack_redacts_passwd_secret_and_credential_labels(self):
        cases = (
            ("passwd=Slate4!Harbor", "password"),
            ("secret: generic-secret-value", "secret"),
            ("bridge password Bridge5!Hidden", "password"),
            ("login credential Login6!Hidden", "password"),
        )
        for source, secret_type in cases:
            with self.subTest(source=source.split()[0]):
                result = pack(source + "\n")
                self.assertEqual(result.secrets_redacted, 1)
                self.assertEqual(result.text, f"SECRET{{type={secret_type};stored=no}}\n")

    def test_ordinary_password_rule_is_not_treated_as_a_value(self):
        source = "Password rule plus OS and hostname should be remembered.\n"
        result = pack(source)
        self.assertEqual(result.secrets_redacted, 0)
        self.assertNotIn("SECRET{", result.text)

    def test_pack_redacts_unlabeled_password_like_value(self):
        value = "Hidden7!Compass"
        result = pack(f"Account fallback: {value}\n")
        self.assertNotIn(value, result.text)
        self.assertIn("SECRET{type=password;stored=no}", result.text)

    def test_secret_scan_never_prints_values(self):
        values = ("Amber4!Signal", "tok_private_987")
        source = f"password={values[0]}\nToken: {values[1]}\n"
        report = format_secret_scan(scan_secrets(source))
        for value in values:
            self.assertNotIn(value, report)
        self.assertIn("possible secrets: 2", report)
        self.assertIn("line 1: type=password", report)
        self.assertIn("line 2: type=token", report)
        self.assertIn("[REDACTED]", report)

    def test_secret_scan_cli_does_not_print_secret_values(self):
        value = "CliOnly5!Secret"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "memory.md"
            source.write_text(f"sudo password: {value}\n", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                code = main(["secret-scan", str(source)])
        self.assertEqual(code, 0)
        self.assertNotIn(value, stdout.getvalue())
        self.assertIn("type=sudo", stdout.getvalue())

    def test_multiple_secrets_on_one_line_all_redacted(self):
        first = "First8!Secret"
        second = "second-token-value"
        result = pack(f"password={first}; token={second}\n")
        self.assertNotIn(first, result.text)
        self.assertNotIn(second, result.text)
        self.assertEqual(result.secrets_redacted, 2)

    def test_discovered_secret_is_scrubbed_from_repeated_context(self):
        value = "Repeat8!Hidden"
        source = f"password={value}\nNever echo {value} in memory.\n"
        scan = scan_secrets(source)
        self.assertNotIn(value, scan.redacted_text)
        self.assertNotIn(value, format_secret_scan(scan))
        self.assertNotIn(value, pack(source).text)

    def test_redaction_preserves_following_sentence_as_non_secret_fact(self):
        value = "Hidden7!Compass"
        result = pack(
            f"Email: professor@example.com / {value}. Bridge SMTP:1025 remains configured.\n"
        ).text
        self.assertNotIn(value, result)
        self.assertIn("Bridge SMTP", result)
        self.assertNotIn("pw=Bridge", result)

    def test_archive_mode_still_roundtrips_secrets_exactly(self):
        source = "sudo=Archive6!Exact\napi_key=archive-key-value\n"
        self.assertEqual(decode(encode(source)), source)

    def test_dense_records_split_into_domain_tags(self):
        source = (
            "Case No. CV-2026-14 must remain exact.\n"
            "Device: Google Pixel 8 Pro.\n"
            "Miahou project release is active.\n"
        )
        result = pack(source).text
        self.assertIn("LEGAL{", result)
        self.assertIn("DEV{", result)
        self.assertIn("PROJ{", result)


if __name__ == "__main__":
    unittest.main()
