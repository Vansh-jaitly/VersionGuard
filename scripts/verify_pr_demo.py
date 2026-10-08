"""Independently verify the saved model repair and reviewed PR correction in Docker."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from experiment.executor import DockerExecutor
from scripts.rag_demo import CHECKS
from versionguard.codeparse import extract_python_code
from versionguard.config import REPO_ROOT
from versionguard.task import Task


def main() -> int:
    proposal = json.loads((REPO_ROOT / 'results/live-pr-repair.json').read_text(encoding='utf-8'))
    task = Task('standalone-pr-demo', 'numpy', '1.26.4', '3.12',
                'Convert a one-element array to a Python scalar.', '', CHECKS)
    evidence = {'kind': 'standalone_demo_not_benchmark', 'executor': 'docker',
                'environment': task.env_key, 'source_head': proposal['head_sha'],
                'model': proposal['model'], 'checks': CHECKS, 'proposals': {}}
    executor = DockerExecutor()
    sources = {'model': extract_python_code(proposal['answer']['answer']),
               'reviewed': (REPO_ROOT / 'demo/fixed.py').read_text(encoding='utf-8')}
    try:
        for label, code in sources.items():
            result = executor.run(task, code + '\nimport numpy as np\n'
                                  + "assert np.__version__ == '1.26.4'\n" + CHECKS)
            evidence['proposals'][label] = {'code': code, **asdict(result),
                                            'passed': result.returncode == 0 and not result.timed_out}
        evidence['reviewed_correction_passed'] = evidence['proposals']['reviewed']['passed']
        status = 0 if evidence['reviewed_correction_passed'] else 1
    except (OSError, RuntimeError, ValueError) as exc:
        evidence['error'] = str(exc)
        status = 2
    output = REPO_ROOT / 'results/live-pr-verification.json'
    output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(f'Independent PR verification: {output}')
    return status


if __name__ == '__main__':
    sys.exit(main())
