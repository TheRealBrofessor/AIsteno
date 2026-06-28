import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from aisteno.cli import main


class CliSafetyTests(unittest.TestCase):
    def test_encode_is_dry_run_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.md"
            output = Path(directory) / "output.aisteno"
            source.write_text("Autonode backup memory\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["encode", str(source), "--out", str(output)])
            self.assertEqual(code, 0)
            self.assertFalse(output.exists())

    def test_apply_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.md"
            output = Path(directory) / "output.aisteno"
            source.write_text("memory\n", encoding="utf-8")
            output.write_text("keep me", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["encode", str(source), "--out", str(output), "--apply"])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

    def test_pack_out_is_dry_run_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.md"
            output = Path(directory) / "packed.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["pack", str(source), "--out", str(output)])
            self.assertEqual(code, 0)
            self.assertFalse(output.exists())

    def test_force_requires_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.md"
            output = Path(directory) / "packed.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["pack", str(source), "--out", str(output), "--force"])
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())

    def test_apply_force_can_replace_output_but_not_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.md"
            output = Path(directory) / "packed.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            output.write_text("old", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["pack", str(source), "--out", str(output), "--apply", "--force"])
            self.assertEqual(code, 0)
            self.assertNotEqual(output.read_text(encoding="utf-8"), "old")
            original = source.read_text(encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["pack", str(source), "--out", str(source), "--apply", "--force"])
            self.assertEqual(code, 2)
            self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
