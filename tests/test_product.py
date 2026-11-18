import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aisteno.config import Config, load_config
from aisteno.dashboard import serve
from aisteno.mcp_server import serve as serve_mcp
from aisteno.setup import discover_candidates, setup
from aisteno.sync import restore, sync, watch


class ProductTests(unittest.TestCase):
    def test_setup_requires_approval_and_detects_hermes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / ".hermes" / "memory.md"
            source.parent.mkdir()
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            candidates = discover_candidates(home)
            self.assertEqual(candidates[0].agent, "hermes")
            config_file = home / "config.json"
            with patch("builtins.input", return_value="n"):
                with self.assertRaises(PermissionError):
                    setup(home=home, config_path=config_file)
            config = setup(home=home, assume_yes=True, config_path=config_file)
            self.assertEqual(load_config(config_file), config)

    def test_sync_preserves_source_and_restores_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "memory.md"
            output = root / "packed.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output), backup_dir=str(root / "backups"))
            first = sync(config)
            self.assertTrue(first.changed)
            original = source.read_text(encoding="utf-8")
            source.write_text("User prefers direct answers.\n", encoding="utf-8")
            second = sync(config)
            self.assertIsNotNone(second.backup)
            restore(second.backup, output)
            self.assertIn("concise", output.read_text(encoding="utf-8"))
            self.assertEqual(source.read_text(encoding="utf-8"), original.replace("concise", "direct"))

    def test_watch_once_refreshes_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.md", root / "output.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output))
            result = next(watch(config, once=True))
            self.assertTrue(result.changed)
            self.assertTrue(output.exists())

    def test_mcp_stdio_exposes_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, config_file = root / "source.md", root / "output.txt", root / "config.json"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output))
            sync(config)
            config_file.write_text(json.dumps(config.__dict__), encoding="utf-8")
            with patch.dict(os.environ, {"AISTENO_CONFIG": str(config_file)}):
                incoming = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n")
                outgoing = io.StringIO()
                serve_mcp(incoming, outgoing)
            self.assertIn("memory_context", outgoing.getvalue())

    def test_dashboard_is_loopback_and_serves_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, config_file = root / "source.md", root / "config.json"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config_file.write_text(json.dumps(Config(str(source), str(root / "out")).__dict__), encoding="utf-8")
            with patch.dict(os.environ, {"AISTENO_CONFIG": str(config_file)}):
                server = serve(port=0)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            server.server_close()


if __name__ == "__main__":
    unittest.main()
