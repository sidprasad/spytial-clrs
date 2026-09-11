"""Offline RQ2 regression tests; never contact providers."""
import base64
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import run_rq1 as shared
import run_rq2 as rq

ANSWER = {"same_structure_score": 90, "representational_correspondence_score": 75,
          "shared_structural_cues": ["Parent-child hierarchy"], "important_mismatch": "None observed",
          "confidence": 80, "explanation": "Both show branching; some role annotations are missing."}


class RQ2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = json.loads((rq.HERE / "rq2-config.json").read_text())

    def image(self, name, color="white"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), color).save(path, format="PNG")
        return path

    def dataset(self):
        for name in ("a-spytial.png", "a-clrs.png", "b-spytial.png", "b-clrs.png", "extra-clrs.png"):
            self.image(name)

    def test_catalog_variants_mapping_and_extra_reference(self):
        self.dataset()
        self.image("a-spytial-label-masked.png")
        self.image("a-clrs-label-masked.png")
        self.image("a-spytial-content-neutral")
        self.image("a-clrs-content-neutral")
        self.settings["ground_truth"] = {"b-spytial.png": ["a-clrs.png", "extra-clrs.png"]}
        qs, refs, _ = rq.catalog(self.root, self.settings, [])
        self.assertEqual((len(qs), len(refs)), (4, 5))
        self.assertEqual(next(q for q in qs if q["source"] == "b-spytial.png")["ground_truth"],
                         ["a-clrs.png", "extra-clrs.png"])
        self.assertEqual(sum(q["variant"] == r["variant"] for q in qs for r in refs), 8)
        self.settings["ground_truth"] = {"typo.png": ["a-clrs.png"]}
        with self.assertRaises(ValueError):
            rq.catalog(self.root, self.settings, [])

    def test_missing_and_cross_variant_truth_rejected(self):
        self.image("a-spytial.png")
        self.image("b-clrs.png")
        with self.assertRaisesRegex(ValueError, "ground truth"):
            rq.catalog(self.root, self.settings, [])
        self.image("a-clrs-label-masked.png")
        self.settings["ground_truth"] = {"a-spytial.png": ["a-clrs-label-masked.png"]}
        with self.assertRaises(ValueError):
            rq.catalog(self.root, self.settings, [])

    def test_validation(self):
        self.assertEqual(rq.validate(ANSWER), ANSWER)
        for change in ({"same_structure_score": True}, {"confidence": float("nan")},
                       {"representational_correspondence_score": 101}, {"shared_structural_cues": [""]},
                       {"important_mismatch": ""}, {"explanation": ""}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                rq.validate({**ANSWER, **change})

    def test_two_image_http_and_cli_payloads_and_schema(self):
        images = [shared.prepare_image(self.image("secret-a.png")),
                  shared.prepare_image(self.image("secret-b.png", "black"))]
        def check(content):
            self.assertEqual([base64.b64decode(b["source"]["data"]) for b in content[:2]], images)
            self.assertEqual(content[2], {"type": "text", "text": "neutral prompt"})
            self.assertNotIn("secret", json.dumps(content))
        def post(url, payload, timeout, headers):
            check(payload["messages"][0]["content"])
            self.assertEqual(payload["output_config"]["format"]["schema"], rq.SCHEMA)
            self.assertEqual(payload["system"], rq.SYSTEM_PROMPT)
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(ANSWER)}]}
        def cli(command, **kwargs):
            check(json.loads(kwargs["input"])["message"]["content"])
            self.assertEqual(json.loads(command[command.index("--json-schema") + 1]), rq.SCHEMA)
            self.assertEqual(command[command.index("--system-prompt") + 1], rq.SYSTEM_PROMPT)
            return subprocess.CompletedProcess(command, 0, json.dumps({"type": "result", "structured_output": ANSWER}), "")
        with patch.object(shared, "post_json", side_effect=post), patch.dict(shared.os.environ, {"ANTHROPIC_API_KEY": "test"}):
            _, parse = shared.request_http("claude-api", self.settings, "model", "neutral prompt", images,
                                           schema=rq.SCHEMA, system_prompt=rq.SYSTEM_PROMPT)
            self.assertEqual(parse(), ANSWER)
        with patch.object(shared.subprocess, "run", side_effect=cli):
            _, parse = shared.request_cli("claude-code", self.settings, "model", "neutral prompt", images,
                                          schema=rq.SCHEMA, system_prompt=rq.SYSTEM_PROMPT)
            self.assertEqual(parse(), ANSWER)

    def test_metrics_ties_multiple_truth_and_incomplete_rows(self):
        self.dataset()
        qs, refs, _ = rq.catalog(self.root, self.settings, [])
        records = []
        for q in qs:
            for ref in refs:
                score = 90 if ref["source"] == "a-clrs.png" else 80
                records.append({"query": q["source"], "reference": ref["source"], "status": "ok",
                                "result": {**ANSWER, **{s: score for s in rq.SCORES}}})
        report = rq.analysis(self.root, qs, refs, records, [1, 2, 3])
        result = report["variants"]["original"][rq.SCORES[0]]
        self.assertEqual([r["first_relevant_rank"] for r in result["rankings"]], [1, 3])
        self.assertAlmostEqual(result["metrics"]["mrr"], 2 / 3)
        self.assertEqual(result["metrics"]["top_k"], {"1": .5, "2": .5, "3": 1})
        qs[1]["ground_truth"].append("extra-clrs.png")
        report = rq.analysis(self.root, qs, refs, records, [1])
        self.assertEqual(report["variants"]["original"][rq.SCORES[0]]["rankings"][1]["first_relevant_rank"], 2)
        records.pop()
        result = rq.analysis(self.root, qs, refs, records, [1])["variants"]["original"][rq.SCORES[0]]
        self.assertIsNone(result["metrics"])
        self.assertEqual(result["complete_queries"], 1)
        self.assertIsNone(result["matrix"][1][-1])

    def test_run_failure_continuation_and_reanalysis(self):
        self.dataset()
        output = self.root / "run"
        calls = iter([({}, lambda: {})] + [({}, lambda: ANSWER)] * 5)
        with patch.object(shared, "request_http", side_effect=lambda *a, **kw: next(calls)), \
                patch.dict(shared.os.environ, {"ANTHROPIC_API_KEY": "test"}), contextlib.redirect_stdout(io.StringIO()):
            status = rq.main(["--backend", "claude-api", "--images-dir", str(self.root), "--output-dir", str(output)])
            self.assertEqual(rq.main(["--analyze", str(output)]), 0)
        self.assertEqual(status, 1)
        records = json.loads((output / "results.json").read_text())
        self.assertEqual(len(records), 6)
        self.assertEqual([r["status"] for r in records], ["error"] + ["ok"] * 5)
        self.assertEqual(len(list((output / "pairs").glob("*.json"))), 6)
        self.assertEqual(len(list((output / "raw").glob("*.json"))), 6)
        self.assertEqual(len((output / "results.jsonl").read_text().splitlines()), 6)
        self.assertIn("shared_structural_cues", (output / "results.csv").read_text())

    def test_dry_run_full_cartesian_product_and_limit(self):
        self.dataset()
        with patch.object(shared, "request_cli") as cli, patch.object(shared, "request_http") as http, \
                contextlib.redirect_stdout(io.StringIO()):
            for limit in (None, 1):
                output = self.root / f"run-{limit}"
                args = ["--dry-run", "--images-dir", str(self.root), "--output-dir", str(output)]
                if limit:
                    args += ["--limit", str(limit)]
                self.assertEqual(rq.main(args), 0)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertEqual(manifest["total_pairs"], 6)
                self.assertEqual(manifest["selected_pairs"], limit or 6)
                report = json.loads((output / "analysis.json").read_text())
                self.assertIsNone(report["variants"]["original"][rq.SCORES[0]]["metrics"])
                with self.assertRaises(FileExistsError):
                    rq.main(args)
        cli.assert_not_called()
        http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
