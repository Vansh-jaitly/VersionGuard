"""Replay recorded documentation-assisted repair gains without calling a model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from experiment.dataset import tasks_for
from experiment.executor import DockerExecutor
from experiment.report import load_results
from experiment.run import execute
from scripts.import_results import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    evidence: dict = {'kind': 'independent_replay_not_new_model_evaluation',
                      'model_calls': 0, 'executor': 'docker', 'tasks': []}
    status = 2
    try:
        model, _ = validate(args.jsonl, args.jsonl.parent)
        models, _ = load_results('test', args.jsonl.parent, model)
        tasks = {task.example_id: task for task in tasks_for('test')}
        executor = DockerExecutor()
        evidence['model'] = model
        for task_id, cells in sorted(models[model].items()):
            if not cells['repair_docs']['passed'] or cells['repair_log']['passed']:
                continue
            item: dict = {'example_id': task_id, 'environment': tasks[task_id].env_key, 'conditions': {}}
            for condition in ('repair_log', 'repair_docs'):
                cell = cells[condition]
                outcome, code, _mode, feedback, elapsed = execute(
                    executor, tasks[task_id], cell['answer'], tasks[task_id].test, 120)
                item['conditions'][condition] = {
                    'recorded_passed': cell['passed'], 'replayed_passed': outcome.passed,
                    'passed_matches': outcome.passed == cell['passed'],
                    'candidate_matches': code == cell['code'], 'status': outcome.status,
                    'category': outcome.category, 'feedback': feedback, 'execution_ms': elapsed,
                }
            evidence['tasks'].append(item)
            matched = all(c['passed_matches'] and c['candidate_matches'] for c in item['conditions'].values())
            print(f'Task {task_id}: {"confirmed" if matched else "MISMATCH"}', flush=True)
        evidence['gains_checked'] = len(evidence['tasks'])
        evidence['all_checked_gains_confirmed'] = bool(evidence['tasks']) and all(
            c['passed_matches'] and c['candidate_matches']
            for item in evidence['tasks'] for c in item['conditions'].values())
        status = 0 if evidence['all_checked_gains_confirmed'] else 1
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        evidence['error'] = str(exc)
        print(f'error: {exc}', file=sys.stderr)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return status


if __name__ == '__main__':
    sys.exit(main())
