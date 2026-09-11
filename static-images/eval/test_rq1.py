"""Offline tests: python -m unittest discover -s static-images/eval -v."""
import contextlib
import csv
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin
import run_rq1 as rq

ANSWER = {"identification": "binary tree", "confidence": 75,
          "visual_evidence": ["Branching edges", "Two children per node"], "alternatives": []}


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = json.loads((rq.HERE / "config.json").read_text())
        self.png = self.root / "intended-bst"
        meta = PngImagePlugin.PngInfo()
        meta.add_text("Title", "intended-bst")
        Image.new("RGB", (10, 10), "white").save(self.png, format="PNG", pnginfo=meta)

    def test_executable_on_path_takes_precedence(self):
        with patch.object(rq.shutil, "which", return_value="/custom/bin/codex"):
            self.assertEqual(rq.resolve_executable("codex"), "/custom/bin/codex")

    def test_codex_desktop_fallback_without_path(self):
        with patch.object(rq.shutil, "which", return_value=None), \
                patch.object(rq.sys, "platform", "darwin"), \
                patch.object(rq.Path, "is_file", side_effect=lambda: True), \
                patch.object(rq.os, "access", return_value=True):
            self.assertEqual(rq.resolve_executable("codex"),
                             "/Applications/Codex.app/Contents/Resources/codex")

    def test_explicit_missing_executable_does_not_fall_back(self):
        with patch.object(rq.shutil, "which", return_value=None):
            self.assertIsNone(rq.resolve_executable("/missing/codex"))

    def test_extensionless_discovery_and_output_exclusion(self):
        excluded = self.root / "results"
        excluded.mkdir()
        Image.new("RGB", (10, 10)).save(excluded / "old.png")
        (self.root / "notes.txt").write_text("not an image")
        found, skipped = rq.discover(self.root, [excluded])
        self.assertEqual(found, [self.png])
        self.assertEqual(skipped, ["notes.txt"])

    def test_metadata_removed_without_resizing(self):
        data = rq.prepare_image(self.png)
        self.assertNotIn(b"intended-bst", data)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (10, 10))
            self.assertFalse(image.info)

    def test_validation_rejects_malformed_answers(self):
        self.assertEqual(rq.validate(ANSWER), ANSWER)
        for change in ({"confidence": True}, {"confidence": 101}, {"confidence": float("nan")},
                       {"visual_evidence": ["one"]}, {"alternatives": ["a", "b", "c"]},
                       {"identification": ""}, {"extra": "no"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                rq.validate({**ANSWER, **change})

    def test_cli_backends_receive_only_neutral_image_and_prompt(self):
        for backend in ("claude-code", "codex"):
            def fake_run(command, **kwargs):
                self.assertNotIn("intended-bst", kwargs["input"])
                self.assertNotIn(str(self.png), " ".join(command))
                self.assertNotEqual(Path(kwargs["cwd"]), self.root)
                if backend == "claude-code":
                    content = json.loads(kwargs["input"])["message"]["content"]
                    self.assertEqual(content[0]["type"], "image")
                    output = json.dumps({"type": "result", "structured_output": ANSWER}) + "\n"
                else:
                    self.assertIn("--image", command)
                    Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(ANSWER))
                    output = json.dumps({"type": "turn.completed"}) + "\n"
                return subprocess.CompletedProcess(command, 0, output, "")
            with self.subTest(backend=backend), patch.object(rq.subprocess, "run", side_effect=fake_run):
                raw, parse = rq.request_cli(backend, self.settings, "model", "neutral prompt",
                                             rq.prepare_image(self.png))
                self.assertEqual(parse(), ANSWER)

    def test_http_payloads_and_responses(self):
        for backend in ("claude-api", "ollama"):
            def fake_post(url, payload, timeout, headers=None):
                self.assertNotIn("intended-bst", json.dumps(payload))
                self.assertEqual(payload["model"], "vision-model")
                self.assertNotIn("context", payload)
                self.assertNotIn("previous_response_id", payload)
                if backend == "ollama":
                    self.assertEqual(payload["format"], rq.SCHEMA)
                    self.assertEqual(payload["messages"][0],
                                     {"role": "system", "content": rq.SYSTEM_PROMPT})
                    self.assertEqual(len(payload["messages"]), 2)
                    self.assertEqual(len(payload["messages"][1]["images"]), 1)
                    return {"message": {"content": json.dumps(ANSWER)}, "done": True}
                self.assertEqual(payload["system"], rq.SYSTEM_PROMPT)
                self.assertEqual(len(payload["messages"]), 1)
                self.assertEqual(payload["output_config"]["format"]["schema"], rq.SCHEMA)
                self.assertEqual(payload["messages"][0]["content"][0]["type"], "image")
                return {"content": [{"type": "text", "text": json.dumps(ANSWER)}], "stop_reason": "end_turn"}
            with self.subTest(backend=backend), patch.object(rq, "post_json", side_effect=fake_post), \
                    patch.dict(rq.os.environ, {"ANTHROPIC_API_KEY": "test-only"}):
                raw, parse = rq.request_http(backend, self.settings, "vision-model", "neutral prompt",
                                              rq.prepare_image(self.png))
                self.assertEqual(parse(), ANSWER)

    def test_failure_is_saved_and_next_image_continues(self):
        Image.new("RGB", (10, 10)).save(self.root / "second.png")
        output = self.root / "run"
        calls = iter([({}, lambda: {"bad": "response"}), ({}, lambda: ANSWER)])
        with patch.object(rq, "request_http", side_effect=lambda *a: next(calls)), \
                contextlib.redirect_stdout(io.StringIO()):
            status = rq.main(["--backend", "ollama", "--images-dir", str(self.root),
                              "--output-dir", str(output)])
        self.assertEqual(status, 1)
        rows = [json.loads(x) for x in (output / "results.jsonl").read_text().splitlines()]
        self.assertEqual([r["status"] for r in rows], ["error", "ok"])
        self.assertEqual(len(list((output / "images").glob("*.json"))), 2)
        self.assertEqual(len(list((output / "raw").glob("*.json"))), 2)
        with (output / "results.csv").open() as file:
            csv_rows = list(csv.DictReader(file))
        self.assertEqual(json.loads(csv_rows[1]["visual_evidence"]), ANSWER["visual_evidence"])

    def test_dry_run_makes_no_calls_and_refuses_overwrite(self):
        output = self.root / "run"
        arguments = ["--dry-run", "--images-dir", str(self.root), "--output-dir", str(output)]
        with patch.object(rq, "request_cli") as cli, patch.object(rq, "request_http") as http, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rq.main(arguments), 0)
            with self.assertRaises(FileExistsError):
                rq.main(arguments)
        cli.assert_not_called()
        http.assert_not_called()
        manifest = json.loads((output / "manifest.json").read_text())
        self.assertEqual(len(manifest["images"]), 1)
        self.assertEqual(manifest["images"][0]["status"], "dry-run")

    def test_independent_cli_sessions_and_memory_overrides(self):
        for backend in ("codex", "claude-code"):
            seen = []
            def fake_run(command, **kwargs):
                seen.append((kwargs["cwd"], kwargs["input"]))
                self.assertNotIn("CODEX_THREAD_ID", kwargs["env"])
                self.assertNotIn("--resume", command)
                self.assertNotIn("--continue", command)
                if backend == "codex":
                    for key, value in rq.CODEX_ISOLATION_CONFIG.items():
                        self.assertIn(f"{key}={json.dumps(value)}", command)
                    self.assertIn("--ephemeral", command)
                    self.assertIn("--ignore-user-config", command)
                else:
                    for key in rq.CLAUDE_ISOLATION_ENV:
                        self.assertEqual(kwargs["env"][key], "1")
                    self.assertIn("--no-session-persistence", command)
                    self.assertTrue(json.loads(command[command.index("--settings") + 1])["disableAllHooks"])
                return subprocess.CompletedProcess(command, 0, "", "")
            inherited = {"CODEX_THREAD_ID": "prior-task", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0"}
            with patch.dict(rq.os.environ, inherited), \
                    patch.object(rq.subprocess, "run", side_effect=fake_run):
                for _ in range(2):
                    rq.request_cli(backend, self.settings, "model", "same prompt", b"same image")
            self.assertNotEqual(seen[0][0], seen[1][0])
            self.assertEqual(seen[0][1], seen[1][1])
            self.assertFalse(seen[0][0].exists())
            self.assertFalse(seen[1][0].exists())

    def test_codex_tool_use_rejected(self):
        def fake_run(command, **kwargs):
            Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(ANSWER))
            return subprocess.CompletedProcess(command, 0, json.dumps({
                "type": "item.completed", "item": {"type": "command_execution"}}), "")
        with patch.object(rq.subprocess, "run", side_effect=fake_run):
            raw, parse = rq.request_cli("codex", self.settings, "model", "prompt", b"png")
            with self.assertRaisesRegex(ValueError, "used a tool"):
                parse()


if __name__ == "__main__":
    unittest.main()
