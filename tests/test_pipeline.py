"""End-to-end self-check: six conditions on the fixture tasks with a scripted model."""

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from experiment import report, run
from experiment.dataset import FIXTURE_RETRIEVAL_CACHE, tasks_for
from experiment.prepare import prepare, resolve_oracle
from versionguard.prompts import CONDITIONS
from versionguard.store import ApiDoc
from versionguard.task import Task


def run_args(directory, model, **overrides):
    values = dict(split="fixtures", model=model, conditions=None, executor="host", limit=None,
                  timeout=30, results_dir=directory, force=False)
    values.update(overrides)
    return argparse.Namespace(**values)


def rates(path):
    records = run.load_records(path)
    out = {}
    for condition in CONDITIONS:
        cells = [r for r in records if r["condition"] == condition]
        out[condition] = (sum(1 for r in cells if r["passed"]), len(cells))
    return out


class PipelineTests(unittest.TestCase):
    def test_prepare_is_deterministic(self):
        before = json.loads(FIXTURE_RETRIEVAL_CACHE.read_text(encoding="utf-8"))
        after = prepare("fixtures", "host", "bm25", 3, None)
        self.assertEqual(before, after)
        self.assertTrue(all(t["usable"] and t["retrieval_hit"] for t in after["tasks"].values()))

    def test_scripted_model_gives_the_known_table(self):
        with tempfile.TemporaryDirectory() as directory:
            path = run.run(run_args(directory, "fake:stale"))
            self.assertEqual(
                rates(path),
                {"task_only": (1, 6), "version": (1, 6), "lookup": (6, 6), "oracle": (6, 6),
                 "repair_log": (1, 6), "repair_docs": (6, 6)},
            )
            records = run.load_records(path)
            carried = [r for r in records if r.get("carried")]
            self.assertEqual({(r["example_id"], r["condition"]) for r in carried},
                             {("f6", "repair_log"), ("f6", "repair_docs")})
            categories = {r["example_id"]: r["category"] for r in records if r["condition"] == "version"}
            self.assertEqual(categories, {"f1": "api_missing", "f2": "api_signature", "f3": "api_missing",
                                          "f4": "wrong_result", "f5": "api_missing", "f6": ""})
            # No failed record leaks the test into the feedback it stores.
            tests = {t.example_id: t.test for t in tasks_for("fixtures")}
            for record in records:
                for line in tests[record["example_id"]].splitlines():
                    self.assertNotIn(line.strip(), record.get("feedback") or "")

            text, summary = report.build("fixtures", Path(directory))
            self.assertIn("Self-check output", text)
            self.assertIn("**useful**", text)
            self.assertEqual(len(summary), 6)

    def test_reference_model_passes_everything(self):
        with tempfile.TemporaryDirectory() as directory:
            path = run.run(run_args(directory, "fake:reference"))
            self.assertTrue(all(passed == total == 6 for passed, total in rates(path).values()))

    def test_resume_adds_nothing_and_settings_are_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = run.run(run_args(directory, "fake:stale", limit=2, conditions=["task_only", "version"]))
            self.assertEqual(len(run.load_records(path)), 4)
            run.run(run_args(directory, "fake:stale", limit=2, conditions=["task_only", "version"]))
            self.assertEqual(len(run.load_records(path)), 4)            # nothing repeated
            run.run(run_args(directory, "fake:stale"))                  # continue to the full matrix
            records = run.load_records(path)
            self.assertEqual(len(records), 36)
            self.assertEqual(len({(r["example_id"], r["condition"]) for r in records}), 36)
            with self.assertRaises(SystemExit):                         # other settings, same file
                run.run(run_args(directory, "fake:stale", executor="docker"))

    def test_repair_needs_its_first_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                run.run(run_args(directory, "fake:stale", conditions=["repair_log"]))


class OracleTests(unittest.TestCase):
    def test_oracle_matching(self):
        docs = [ApiDoc("scipy.stats.norm"), ApiDoc("torch.from_numpy"), ApiDoc("flask.helpers")]
        task = Task.from_row({
            "example_id": "0", "library": "torch", "version": "1.9.0", "problem": "", "starting_code": "",
            "test": "", "api_calls": ["torch.from_numpy", "input_tensor.numpy", "scipy.stats.norm.logcdf"],
        })
        self.assertEqual([d.qualname for d in resolve_oracle(task, docs)], ["torch.from_numpy", "scipy.stats.norm"])
        variable_only = Task.from_row({
            "example_id": "1", "library": "flask", "version": "3.0.0", "problem": "", "starting_code": "",
            "test": "", "api_calls": ["td.total_seconds"],
        })
        self.assertEqual(resolve_oracle(variable_only, docs), [])


class TaskTests(unittest.TestCase):
    def test_requirements_and_environment_key(self):
        row = {"example_id": 7, "library": "torch", "version": "1.9.0", "python_version": "3.7", "problem": "p",
               "starting_code": "s", "test": "t", "additional_dependencies": "scipy==1.7.3 numpy==1.21.6",
               "extra_dependencies": None, "docs": ["https://example.org/doc"]}
        task = Task.from_row(row)
        self.assertEqual(task.example_id, "7")
        self.assertEqual(task.requirements, ("torch==1.9.0", "scipy==1.7.3", "numpy==1.21.6"))
        self.assertEqual(task.distributions, ("torch", "scipy", "numpy"))
        self.assertEqual(task.doc_urls, ("https://example.org/doc",))
        self.assertTrue(task.env_key.startswith("py37-torch-1-9-0-"))
        same = Task.from_row({**row, "example_id": 8, "problem": "other"})
        self.assertEqual(task.env_key, same.env_key)          # same environment is shared
        other = Task.from_row({**row, "version": "1.10.0"})
        self.assertNotEqual(task.env_key, other.env_key)


class BuildLogTests(unittest.TestCase):
    def test_pip_error_is_pulled_out_of_a_build_log(self):
        from experiment.executor import build_error_summary

        log = (
            "#1 [internal] load build definition\n#5 2.1 Collecting numpy==1.21.0\n"
            "#5 9.9 ERROR: Could not build wheels for numpy, which is required to install pyproject.toml-based projects\n"
            "#5 ERROR: process did not complete successfully: exit code: 1\nDockerfile:3\n   3 | >>> RUN pip install\n"
        )
        summary = build_error_summary(log)
        self.assertIn("Could not build wheels for numpy", summary)
        self.assertNotIn("load build definition", summary)
        self.assertTrue(build_error_summary("line one\nline two"))


class StatsTests(unittest.TestCase):
    def test_contrast_on_known_data(self):
        by_task = {}
        for index in range(40):                                # 30 of 40 gained, none lost
            by_task[str(index)] = {
                "version": {"passed": False},
                "lookup": {"passed": index < 30},
            }
        result = report.contrast(by_task, "lookup", "version")
        self.assertEqual((result["n"], result["gained"], result["lost"]), (40, 30, 0))
        self.assertAlmostEqual(result["diff"], 0.75)
        self.assertTrue(0.55 < result["low"] < 0.75 < result["high"] <= 0.90)
        self.assertLess(result["p"], 0.001)
        self.assertEqual(result["verdict"], "useful")

    def test_no_effect_and_small_effect(self):
        mixed = {str(i): {"version": {"passed": i % 2 == 0}, "lookup": {"passed": i % 2 == 1}} for i in range(40)}
        self.assertEqual(report.contrast(mixed, "lookup", "version")["verdict"], "no effect detected")
        self.assertEqual(report.verdict(0.05, 0.01, 0.09), "positive but below the 10-point threshold")
        self.assertEqual(report.verdict(-0.2, -0.3, -0.1), "worse")

    def test_unscored_cells_are_left_out(self):
        by_task = {
            "a": {"version": {"passed": True}, "oracle": {"passed": None}},
            "b": {"version": {"passed": False}, "oracle": {"passed": True}},
            "c": {"version": {"passed": False}, "oracle": {"passed": True}},
        }
        self.assertEqual(report.contrast(by_task, "oracle", "version")["n"], 2)


if __name__ == "__main__":
    unittest.main()
