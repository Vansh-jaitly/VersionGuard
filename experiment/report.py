"""Turn results files into the tables for the presentation.

    python -m experiment.report --split test
    python -m experiment.report --split fixtures        # self-check output

Reads every results/<split>-*.jsonl (one per model, possibly from different
laptops), and writes results/report-<split>.md and results/summary-<split>.csv.

Statistics (all paired: the same tasks under two conditions)
  * difference in pass rate, in percentage points
  * 95% confidence interval by paired bootstrap (10,000 resamples, fixed seed)
  * p-value by sign-flip permutation test (10,000 flips, fixed seed)
The verdict applies the rule written down in experiment/PROTOCOL.md before
any test run.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, Sequence

from experiment.run import load_records
from experiment.dataset import load_split_file, tasks_for
from versionguard.config import RESULTS_DIR
from versionguard.prompts import CONDITIONS, REPAIR_BASE

# The rule fixed in PROTOCOL.md.
MIN_GAIN = 0.10
RESAMPLES = 10_000
STATS_SEED = 20261007

# (treatment, baseline, label, is the pre-registered rule applied?)
CONTRASTS = (
    ("lookup", "version", "Lookup vs version only", True),
    ("repair_docs", "repair_log", "Repair with docs vs repair with log only", True),
    ("version", "task_only", "Version only vs task only", False),
    ("oracle", "lookup", "Correct docs vs lookup (room left in the lookup)", False),
    ("repair_log", "version", "One repair round vs no repair", False),
)
LABELS = {
    "task_only": "1 Task only",
    "version": "2 Version",
    "lookup": "3 Lookup",
    "oracle": "4 Correct docs",
    "repair_log": "5 Repair, log only",
    "repair_docs": "6 Repair, log + docs",
}


def scored(record: dict) -> bool:
    """A record counts in a pass rate only if the cell was actually run."""
    return record.get("passed") is not None


def paired_bootstrap(pairs: Sequence[tuple[int, int]], rng: random.Random) -> tuple[float, float]:
    """95% interval for mean(treatment - baseline) over paired tasks."""
    n = len(pairs)
    diffs = [a - b for a, b in pairs]
    means = []
    for _ in range(RESAMPLES):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return means[int(0.025 * RESAMPLES)], means[int(0.975 * RESAMPLES) - 1]


def sign_flip_p(pairs: Sequence[tuple[int, int]], rng: random.Random) -> float:
    """Two-sided p-value: how often random sign flips give a mean this far from 0."""
    diffs = [a - b for a, b in pairs if a != b]
    if not diffs:
        return 1.0
    observed = abs(sum(diffs))
    extreme = 0
    for _ in range(RESAMPLES):
        total = sum(d if rng.random() < 0.5 else -d for d in diffs)
        if abs(total) >= observed:
            extreme += 1
    return (extreme + 1) / (RESAMPLES + 1)


def verdict(diff: float, low: float, high: float) -> str:
    if low > 0 and diff >= MIN_GAIN:
        return "useful"
    if low <= 0 <= high:
        return "no effect detected"
    if high < 0:
        return "worse"
    return "positive but below the 10-point threshold"


def contrast(by_task: dict, treatment: str, baseline: str) -> Optional[dict]:
    pairs = []
    for cells in by_task.values():
        a, b = cells.get(treatment), cells.get(baseline)
        if a is not None and b is not None and scored(a) and scored(b):
            pairs.append((int(bool(a["passed"])), int(bool(b["passed"]))))
    if len(pairs) < 2:
        return None
    rng = random.Random(STATS_SEED)
    diff = sum(a - b for a, b in pairs) / len(pairs)
    low, high = paired_bootstrap(pairs, rng)
    return {
        "n": len(pairs),
        "treatment_rate": sum(a for a, _ in pairs) / len(pairs),
        "baseline_rate": sum(b for _, b in pairs) / len(pairs),
        "diff": diff,
        "low": low,
        "high": high,
        "p": sign_flip_p(pairs, rng),
        "gained": sum(1 for a, b in pairs if a > b),
        "lost": sum(1 for a, b in pairs if a < b),
        "verdict": verdict(diff, low, high),
    }


def pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def points(value: float) -> str:
    return f"{100 * value:+.1f}"


def group_rate(group: list[dict]) -> str:
    if not group:
        return "n/a"
    return f"{pct(sum(1 for c in group if c['passed']) / len(group))} ({len(group)} tasks)"


def fixed_count(failed_first: list[dict], condition: str) -> str:
    tried = [c[condition] for c in failed_first if condition in c and scored(c[condition])]
    return f"{sum(1 for c in tried if c['passed'])}/{len(tried)}" if tried else "not run"


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def expected_tasks(split: str) -> Optional[set[str]]:
    try:
        if split == "fixtures":
            return {task.example_id for task in tasks_for(split)}
        return set(load_split_file()[split])
    except FileNotFoundError:
        return None


def load_results(split: str, directory: Path, model_filter: Optional[str] = None) -> tuple[dict, dict]:
    files = sorted(directory.glob(f"{split}-*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No results files named {split}-*.jsonl in {directory}")

    models: dict[str, dict[str, dict[str, dict]]] = {}
    metas: dict[str, dict] = {}
    for path in files:
        file_models: set[str] = set()
        for record in load_records(path):
            if model_filter and record["model"] != model_filter:
                continue
            if record.get("split") != split or record.get("condition") not in CONDITIONS:
                raise ValueError(f"Invalid split or condition in {path.name}")
            model = record["model"]
            file_models.add(model)
            cells = models.setdefault(model, defaultdict(dict))[record["example_id"]]
            if record["condition"] in cells:
                raise ValueError(f"Duplicate result for {model}, task {record['example_id']}, {record['condition']}")
            cells[record["condition"]] = record
        meta_path = path.with_suffix(".meta.json")
        if file_models and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if file_models != {meta.get("model")} or meta.get("split") != split:
                raise ValueError(f"Result metadata does not match {path.name}")
            metas[meta.get("model", path.stem)] = meta
    if not models:
        raise FileNotFoundError(f"No results for {model_filter or split} in {directory}")
    return models, metas


def coverage_issues(split: str, models: dict, metas: dict) -> list[str]:
    issues = []
    expected = expected_tasks(split)
    for model, by_task in models.items():
        if expected is None:
            issues.append(f"{model}: task split is unavailable; completeness cannot be verified.")
        else:
            missing = sum(1 for task in expected for condition in CONDITIONS
                          if condition not in by_task.get(task, {}))
            if missing:
                issues.append(f"{model}: incomplete run, {missing} of {len(expected) * len(CONDITIONS)} cells missing.")
            if set(by_task) - expected:
                issues.append(f"{model}: results include tasks outside the selected split.")
        unscored = sum(1 for cells in by_task.values() for condition, cell in cells.items()
                       if not scored(cell) and not (condition == "oracle" and cell.get("category") == "no_oracle"))
        if unscored:
            issues.append(f"{model}: {unscored} unscored cells (other than unavailable oracle documentation).")
        meta = metas.get(model, {})
        if split != "fixtures" and not model.startswith("fake:"):
            if not meta:
                issues.append(f"{model}: metadata is missing.")
            elif meta.get("executor") != "docker":
                issues.append(f"{model}: execution did not use pinned Docker environments.")
        if meta.get("forced_changes"):
            issues.append(f"{model}: settings were overridden with --force; this run mixes configurations.")
    for key in ("retrieval_cache_sha256", "protocol_sha256", "dataset_sha256", "split_sha256"):
        hashes = {meta[key] for meta in metas.values() if meta.get(key)}
        if len(hashes) > 1:
            issues.append(f"Models use different {key}; they do not share the same experiment inputs.")
    for key in ("temperature", "seed", "num_ctx", "num_predict", "exec_timeout_s"):
        values = {meta[key] for meta in metas.values() if key in meta}
        if len(values) > 1:
            issues.append(f"Models use different {key}; they do not share the same experiment settings.")
    ollama_versions = {meta.get("llm", {}).get("ollama_version") for meta in metas.values()
                       if meta.get("llm", {}).get("ollama_version")}
    if len(ollama_versions) > 1:
        issues.append("Models use different Ollama versions; check the cross-laptop setup.")
    return issues


def build(split: str, directory: Path, model_filter: Optional[str] = None) -> tuple[str, list[dict]]:
    models, metas = load_results(split, directory, model_filter)

    out: list[str] = [f"# VersionGuard results: {split} split", ""]
    if split == "fixtures" or any(name.startswith("fake:") for name in models):
        out += [
            "> **Self-check output.** Fixture tasks and/or a scripted stand-in model. "
            "This shows the pipeline works; it is not a finding about any model.",
            "",
        ]
    if split == "dev":
        out += ["> Development results are for checking the pipeline; the registered decision rule applies to test results.", ""]
    issues = coverage_issues(split, models, metas)
    if issues:
        out += ["> **Provisional report.** Coverage or provenance issues prevent treating this as a complete evaluation.", ""]
        out += [f"- {issue}" for issue in issues]
        out.append("")
    expected = expected_tasks(split)
    coverage_rows = []
    for model, by_task in models.items():
        recorded = sum(len(cells) for cells in by_task.values())
        full = sum(all(condition in cells for condition in CONDITIONS) for cells in by_task.values())
        coverage_rows.append([f"`{model}`", len(by_task), full, recorded,
                              len(expected) * len(CONDITIONS) if expected is not None else "unknown"])
    out += ["## Run coverage", "", table(["Model", "Tasks recorded", "Tasks with all six cells", "Cells recorded", "Expected cells"],
                                         coverage_rows), ""]
    summary_rows: list[dict] = []

    # 1. Pass rate per model and condition
    out += ["## 1. Tests passed, by condition", ""]
    rows = []
    for model, by_task in models.items():
        row = [f"`{model}`"]
        for condition in CONDITIONS:
            cells = [c[condition] for c in by_task.values() if condition in c and scored(c[condition])]
            passed = sum(1 for c in cells if c["passed"])
            rate = passed / len(cells) if cells else None
            row.append(f"{pct(rate)} ({passed}/{len(cells)})" if cells else "not run")
            summary_rows.append(
                {"model": model, "condition": condition, "n": len(cells), "passed": passed,
                 "pass_rate": "" if rate is None else round(rate, 4)}
            )
        rows.append(row)
    out += [table(["Model", *(LABELS[c] for c in CONDITIONS)], rows), ""]
    out += [
        "Conditions 5 and 6 are the result after one repair round: tasks that already passed in "
        "condition 2 keep their pass, tasks that failed get one retry. Condition 4 only covers tasks "
        "whose reference APIs could be matched to documentation.",
        "",
    ]

    # 2. Paired comparisons with the pre-registered verdict
    out += ["## 2. Paired comparisons", ""]
    rows = []
    for model, by_task in models.items():
        for treatment, baseline, label, ruled in CONTRASTS:
            result = contrast(by_task, treatment, baseline)
            if result is None:
                continue
            rows.append([
                f"`{model}`",
                label,
                result["n"],
                f"{pct(result['baseline_rate'])} -> {pct(result['treatment_rate'])}",
                f"{points(result['diff'])} [{points(result['low'])}, {points(result['high'])}]",
                f"{result['p']:.3f}",
                f"+{result['gained']} / -{result['lost']}",
                (f"**{result['verdict']}**" if ruled and split != "dev" and not issues else result["verdict"]),
            ])
    out += [
        table(["Model", "Comparison", "Tasks", "Pass rate", "Difference, points [95% CI]", "p", "Tasks gained / lost", "Verdict"], rows),
        "",
        f"Verdicts in bold apply the rule fixed in `experiment/PROTOCOL.md`: *useful* needs a gain of at least "
        f"{int(MIN_GAIN * 100)} points and a 95% interval above zero. The other rows are descriptive.",
        "",
    ]

    # 3. Lookup quality
    out += ["## 3. Did the lookup find the right documentation?", ""]
    rows = []
    for model, by_task in models.items():
        cells = [c["lookup"] for c in by_task.values() if "lookup" in c and scored(c["lookup"])]
        with_oracle = [c for c in cells if c.get("oracle_available")]
        hit = [c for c in with_oracle if c.get("retrieval_hit")]
        miss = [c for c in with_oracle if not c.get("retrieval_hit")]
        rows.append([
            f"`{model}`",
            f"{len(hit)}/{len(with_oracle)}" if with_oracle else "n/a",
            group_rate(hit),
            group_rate(miss),
            len(cells) - len(with_oracle),
        ])
    out += [
        table(["Model", "Lookup found a reference API", "Pass rate when found", "Pass rate when missed", "Tasks with no oracle"], rows),
        "",
        "The lookup is the same for every model (it is computed once and cached), so the first column "
        "is identical across models. A high pass rate when found and a low one when missed points at "
        "retrieval; a low pass rate even when found points at the model not using the documentation.",
        "",
    ]

    # 4. Why answers failed
    out += ["## 4. Why answers failed", ""]
    categories = ["wrong_result", "api_missing", "api_signature", "other_error", "no_code", "timeout"]
    rows = []
    for model, by_task in models.items():
        for condition in CONDITIONS:
            cells = [c[condition] for c in by_task.values() if condition in c and scored(c[condition])]
            failed = [c for c in cells if not c["passed"]]
            if not cells:
                continue
            counts = Counter(c.get("category") or "other_error" for c in failed)
            rows.append([f"`{model}`", LABELS[condition], len(failed), *(counts.get(k, 0) for k in categories)])
    out += [
        table(
            ["Model", "Condition", "Failed", "Wrong result", "API missing", "Wrong arguments", "Other error",
             "No code", "Timeout"],
            rows,
        ),
        "",
        "Categories are assigned automatically from the error: *API missing* is an AttributeError or "
        "ImportError, *wrong arguments* is a TypeError about the call's arguments, *wrong result* is a "
        "failed assertion.",
        "",
    ]

    # 5. Repair round
    out += ["## 5. The repair round", ""]
    rows = []
    for model, by_task in models.items():
        failed_first = [c for c in by_task.values() if REPAIR_BASE in c and c[REPAIR_BASE].get("passed") is False]
        if not failed_first:
            continue
        rows.append([
            f"`{model}`",
            len(failed_first),
            fixed_count(failed_first, "repair_log"),
            fixed_count(failed_first, "repair_docs"),
        ])
    out += [
        table(["Model", "Failed first attempt (condition 2)", "Fixed with log only", "Fixed with log + docs"], rows)
        if rows else "No failed first attempts to repair.",
        "",
    ]

    # 6. By kind of change
    out += ["## 6. By kind of library change", ""]
    rows = []
    for model, by_task in models.items():
        groups: dict[str, list[dict]] = defaultdict(list)
        for cells in by_task.values():
            any_cell = next(iter(cells.values()))
            groups[any_cell.get("type_of_change") or "unknown"].append(cells)
        for change, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            row = [f"`{model}`", change, len(items)]
            for condition in ("version", "lookup", "repair_docs"):
                cells = [c[condition] for c in items if condition in c and scored(c[condition])]
                row.append(pct(sum(1 for c in cells if c["passed"]) / len(cells)) if cells else "n/a")
            rows.append(row)
    out += [table(["Model", "Kind of change", "Tasks", "2 Version", "3 Lookup", "6 Repair, log + docs"], rows), ""]
    out += ["Groups this small are for spotting patterns, not for conclusions.", ""]

    # 7. Provenance
    out += ["## 7. How these numbers were produced", ""]
    rows = []
    for model in models:
        meta = metas.get(model, {})
        machine = meta.get("machine", {})
        llm = meta.get("llm", {})
        rows.append([
            f"`{model}`",
            (llm.get("model_digest") or "n/a")[:12],
            llm.get("ollama_version") or "n/a",
            f"{machine.get('system', '?')} {machine.get('machine', '')}".strip(),
            meta.get("temperature", "?"),
            meta.get("seed", "?"),
            meta.get("num_ctx", "?"),
            (meta.get("retrieval_cache_sha256") or "n/a")[:12],
            meta.get("executor", "?"),
        ])
    out += [
        table(["Model", "Model digest", "Ollama", "Laptop", "Temp.", "Seed", "Context", "Lookup cache", "Executor"], rows),
        "",
        "Each model ran on one laptop. Speed is not compared across laptops.",
        "",
    ]
    timing_rows = []
    for model, by_task in models.items():
        for condition in CONDITIONS:
            generated = [cells[condition] for cells in by_task.values()
                         if condition in cells and not cells[condition].get("carried")
                         and isinstance(cells[condition].get("latency_ms"), (int, float))]
            if generated:
                times = [cell["latency_ms"] / 1000 for cell in generated]
                timing_rows.append([f"`{model}`", LABELS[condition], len(generated),
                                    f"{statistics.median(times):.1f}", f"{sum(times) / 60:.1f}",
                                    sum(cell.get("input_tokens") or 0 for cell in generated),
                                    sum(cell.get("output_tokens") or 0 for cell in generated)])
    out += ["## 8. Model time and tokens on this laptop", "",
            table(["Model", "Condition", "Generated answers", "Median seconds", "Model minutes", "Input tokens", "Output tokens"],
                  timing_rows), "", "Carried first-attempt passes and skipped cells do not count as model calls.", ""]
    return "\n".join(out), summary_rows


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--split", default="test", choices=["fixtures", "dev", "test"])
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--model", help="report one model tag instead of all models")
    parser.add_argument("--require-complete", action="store_true", help="fail if coverage or provenance is incomplete")
    args = parser.parse_args(argv)
    directory = Path(args.results_dir)
    try:
        if args.require_complete:
            models, metas = load_results(args.split, directory, args.model)
            issues = coverage_issues(args.split, models, metas)
            if issues:
                raise ValueError("Cannot produce a complete report: " + " ".join(issues))
        text, summary = build(args.split, directory, args.model)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    report_path = directory / f"report-{args.split}.md"
    report_path.write_text(text + "\n", encoding="utf-8")
    summary_path = directory / f"summary-{args.split}.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["model", "condition", "n", "passed", "pass_rate"])
        writer.writeheader()
        writer.writerows(summary)
    models, _metas = load_results(args.split, directory, args.model)
    comparisons_path = directory / f"comparisons-{args.split}.csv"
    comparison_rows = []
    failure_rows = []
    for model, by_task in models.items():
        for treatment, baseline, _label, _ruled in CONTRASTS:
            result = contrast(by_task, treatment, baseline)
            if result is not None:
                comparison_rows.append({"model": model, "treatment": treatment, "baseline": baseline, **result})
        for task_id, cells in by_task.items():
            for condition, cell in cells.items():
                if cell.get("passed") is False:
                    failure_rows.append({"model": model, "example_id": task_id, "condition": condition,
                                         **{key: cell.get(key, "") for key in
                                            ("library", "version", "category", "error_type", "error_message", "code", "feedback")}})
    with open(comparisons_path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["model", "treatment", "baseline", "n", "treatment_rate", "baseline_rate",
                                                   "diff", "low", "high", "p", "gained", "lost", "verdict"])
        writer.writeheader()
        writer.writerows(comparison_rows)
    failures_path = directory / f"failures-{args.split}.csv"
    with open(failures_path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["model", "example_id", "condition", "library", "version", "category",
                                                   "error_type", "error_message", "code", "feedback"])
        writer.writeheader()
        writer.writerows(failure_rows)
    print(text)
    print(f"\nWrote {report_path} and {summary_path}")
    print(f"Wrote {comparisons_path} and {failures_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
