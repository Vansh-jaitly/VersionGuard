import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment import report, run
from experiment import prepare
from experiment.dataset import FIXTURE_RETRIEVAL_CACHE, tasks_for
from experiment.executor import ExecResult
from versionguard.prompts import CONDITIONS


class ResumeIntegrityTests(unittest.TestCase):
    def test_timeout_protocol_and_model_digest_are_locked(self):
        initial = {"model": "test", "exec_timeout_s": 30, "protocol_sha256": "original",
                   "llm": {"model_digest": "first", "ollama_version": "one"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.meta.json"
            run.check_metadata(path, initial, False)
            for key, value in (("exec_timeout_s", 120), ("protocol_sha256", "changed")):
                with self.subTest(key=key), self.assertRaises(SystemExit):
                    run.check_metadata(path, {**initial, key: value}, False)
            with self.assertRaises(SystemExit):
                run.check_metadata(path, {**initial, "llm": {"model_digest": "second"}}, False)

    def test_incomplete_preparation_stops_before_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            cache.write_text(json.dumps({"tasks": {}}), encoding="utf-8")
            args = argparse.Namespace(split="fixtures", model="fake:stale", conditions=None, limit=None)
            with patch("experiment.run.retrieval_cache_path", return_value=cache):
                with self.assertRaisesRegex(SystemExit, "preparation is incomplete"):
                    run.run(args)

    def test_real_split_cannot_use_host_executor(self):
        args = argparse.Namespace(split="dev", model="fake:stale", conditions=None, limit=None, executor="host")
        with patch("experiment.run.tasks_for", return_value=tasks_for("fixtures")), \
                patch("experiment.run.retrieval_cache_path", return_value=FIXTURE_RETRIEVAL_CACHE):
            with self.assertRaisesRegex(SystemExit, "require --executor docker"):
                run.run(args)

    def test_non_positive_limits_are_rejected(self):
        for value in ("0", "-1"):
            with self.assertRaises(SystemExit):
                run.parse_args(["--split", "fixtures", "--limit", value])

    def test_failed_reference_is_persisted_even_when_it_is_the_last_task(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            task = tasks_for("fixtures")[0]
            with patch("experiment.prepare.retrieval_cache_path", return_value=path), \
                    patch("experiment.prepare.tasks_for", return_value=[task]), \
                    patch("experiment.prepare.make_executor") as executor:
                executor.return_value.run.return_value = ExecResult(1, "", "AssertionError: bad reference")
                prepare.prepare("fixtures", "host", "bm25", 3, None)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(saved["tasks"][task.example_id]["usable"])
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_verification_cannot_succeed_with_empty_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            path.write_text(json.dumps({"tasks": {}}), encoding="utf-8")
            with patch("experiment.prepare.retrieval_cache_path", return_value=path):
                self.assertEqual(prepare.verify("fixtures", "host", None), 1)


class ReportIntegrityTests(unittest.TestCase):
    @staticmethod
    def record(task="f1", condition="task_only", passed=True):
        return {"model": "fake:stale", "split": "fixtures", "example_id": task,
                "condition": condition, "passed": passed, "category": "", "latency_ms": 2000,
                "input_tokens": 10, "output_tokens": 5}

    def test_partial_results_are_labelled_and_complete_report_refuses_them(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures-one.jsonl"
            run.append_record(path, self.record())
            text, _summary = report.build("fixtures", Path(directory))
            self.assertIn("Provisional report", text)
            self.assertIn("35 of 36 cells missing", text)
            self.assertEqual(report.main(["--split", "fixtures", "--results-dir", directory, "--require-complete"]), 1)

    def test_duplicates_across_files_are_not_silently_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("one", "two"):
                run.append_record(Path(directory) / f"fixtures-{name}.jsonl", self.record())
            with self.assertRaisesRegex(ValueError, "Duplicate result"):
                report.build("fixtures", Path(directory))

    def test_complete_report_exports_failure_and_paired_comparison_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures-one.jsonl"
            for task in tasks_for("fixtures"):
                for condition in CONDITIONS:
                    row = self.record(task.example_id, condition, condition != "version")
                    run.append_record(path, row)
            self.assertEqual(report.main(["--split", "fixtures", "--results-dir", directory, "--require-complete"]), 0)
            self.assertTrue((Path(directory) / "comparisons-fixtures.csv").is_file())
            self.assertTrue((Path(directory) / "failures-fixtures.csv").is_file())
            text = (Path(directory) / "report-fixtures.md").read_text(encoding="utf-8")
            self.assertNotIn("Provisional report", text)
            self.assertIn("Model time and tokens", text)


if __name__ == "__main__":
    unittest.main()
