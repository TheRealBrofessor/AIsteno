import unittest

from aisteno.codec import decode, encode


class CodecTests(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        text = (
            "Professor prefers low-token mode.\n"
            "one-box copy paste commands; no fluff.\n"
            "Autonode memory injection budget: backup, delete, merge.\n"
            "Literal AN, BK, PREF:TOKLOW, and ~ remain literal.\n"
        )
        encoded = encode(text)
        self.assertIn("PREF:TOKLOW", encoded)
        self.assertIn("CMD=1BOX", encoded)
        self.assertIn("NOFLUFF", encoded)
        self.assertEqual(decode(encoded), text)

    def test_preserve_paths(self):
        text = "Use /srv/Miahou/backup/AN/image.dd and C:\\Evidence\\Autonode\\memory.bin\n"
        encoded = encode(text)
        self.assertIn("/srv/Miahou/backup/~AN/image.dd", encoded)
        self.assertIn("C:\\Evidence\\Autonode\\memory.bin", encoded)
        self.assertEqual(decode(encoded), text)

    def test_preserve_case_numbers(self):
        text = "Case No. 24-CV-01842: Professor must retain the legal record.\n"
        encoded = encode(text)
        self.assertIn("Case No. 24-CV-01842", encoded)
        self.assertEqual(decode(encoded), text)

    def test_preserve_commands(self):
        commands = (
            "$ cp /evidence/backup.dd /vault/backup.dd\n"
            "Command: git merge forensic-review\n"
            "python -m aisteno.cli roundtrip memory.md\n"
        )
        encoded = encode(commands)
        self.assertIn(commands, encoded)
        self.assertEqual(decode(encoded), commands)

    def test_preserve_line_endings(self):
        text = "Autonode backup memory\r\nProfessor prefers low-token mode\r\n"
        self.assertEqual(decode(encode(text)), text)


if __name__ == "__main__":
    unittest.main()
