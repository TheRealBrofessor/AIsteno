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


if __name__ == "__main__":
    unittest.main()
