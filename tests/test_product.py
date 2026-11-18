import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen
from unittest.mock import patch

from aisteno.config import Config, load_config
from aisteno.dashboard import serve
from aisteno.mcp_server import serve as serve_mcp
from aisteno.setup import discover_candidates, setup
from aisteno.sync import restore, sync, watch
from aisteno.adapters import agent_startup


class ProductTests(unittest.TestCase):
    def test_setup_requires_approval_and_detects_hermes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / ".hermes" / "memories" / "MEMORY.md"
            source.parent.mkdir(parents=True)
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

    def test_sync_failure_keeps_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.md", root / "output.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output))
            sync(config)
            previous = output.read_bytes()
            source.write_text("User prefers direct answers.\n", encoding="utf-8")
            with patch.object(Path, "replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaises(OSError):
                    sync(config)
            self.assertEqual(output.read_bytes(), previous)

    def test_agent_startup_rejects_stale_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.md", root / "output.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output))
            sync(config)
            self.assertIn("PREF", agent_startup(config))
            source.write_text("User prefers direct answers.\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                agent_startup(config)

    def test_agent_startup_rejects_modified_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.md", root / "output.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output))
            sync(config)
            output.write_bytes(output.read_bytes().replace(b"concise", b"direct", 1))
            with self.assertRaisesRegex(ValueError, "modified"):
                agent_startup(config)

    def test_sync_rebuilds_tampered_managed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.md", root / "output.txt"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config = Config(str(source), str(output))
            first = sync(config)
            original = output.read_bytes()
            output.write_bytes(original.replace(b"concise", b"direct", 1))
            second = sync(config)
            self.assertTrue(second.changed)
            self.assertNotEqual(output.read_bytes(), original.replace(b"concise", b"direct", 1))

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

    def test_mcp_returns_protocol_errors_without_tracebacks(self):
        incoming = io.StringIO(
            '{"jsonrpc":"2.0","id":1,"method":"unknown"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"resources/read","params":{"uri":"bad"}}\n'
        )
        outgoing = io.StringIO()
        serve_mcp(incoming, outgoing)
        messages = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual(messages[0]["error"]["code"], -32601)
        self.assertEqual(messages[1]["error"]["code"], -32602)

    def test_dashboard_is_loopback_and_serves_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, config_file = root / "source.md", root / "config.json"
            source.write_text("User prefers concise answers.\n", encoding="utf-8")
            config_file.write_text(json.dumps(Config(str(source), str(root / "out")).__dict__), encoding="utf-8")
            with patch.dict(os.environ, {"AISTENO_CONFIG": str(config_file)}):
                server = serve(port=0)
            self.assertRaises(ValueError, serve, host="0.0.0.0", port=0)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            server.server_close()

    def test_dashboard_escapes_dynamic_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, config_file = root / "source.md", root / "config.json"
            source.write_text("Project: <script>alert(1)</script>\n", encoding="utf-8")
            config_file.write_text(json.dumps(Config(str(source), str(root / "out")).__dict__), encoding="utf-8")
            with patch.dict(os.environ, {"AISTENO_CONFIG": str(config_file)}):
                server = serve(port=0)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                body = urlopen(
                    f"http://127.0.0.1:{server.server_address[1]}/", timeout=2
                ).read().decode()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
            self.assertNotIn("<script>alert(1)</script>", body)
            self.assertIn("&lt;script&gt;", body)


if __name__ == "__main__":
    unittest.main()
