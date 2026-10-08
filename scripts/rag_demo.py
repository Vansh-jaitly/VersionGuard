"""Save a real RAG answer and independently test its proposal inside Docker."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path
import sys

from experiment.dataset import tasks_for
from experiment.executor import DockerExecutor
from versionguard.bot import Bot
from versionguard.codeparse import extract_python_code
from versionguard.config import APIDOCS_DIR, REPO_ROOT
from versionguard.store import load_api_docs

QUESTION = 'Convert a one-element NumPy array into a standard Python scalar. Define as_scalar(array).'
CHECKS = '''
value = as_scalar(np.array([42], dtype=np.int64))
assert value == 42 and type(value) is int
value = as_scalar(np.array([2.5], dtype=np.float64))
assert value == 2.5 and type(value) is float
assert as_scalar(np.array([[7]])) == 7
try:
    as_scalar(np.array([1, 2]))
except ValueError:
    pass
else:
    raise AssertionError('multiple elements must be rejected')
print('Docker scalar checks passed')
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen2.5:7b-instruct')
    parser.add_argument('--retriever', choices=['vector', 'bm25'], default='vector')
    parser.add_argument('--output', type=Path, default=REPO_ROOT / 'results' / 'rag-demo.json')
    args = parser.parse_args(argv)
    evidence: dict = {'kind': 'standalone_demo_not_benchmark', 'question': QUESTION, 'model': args.model,
                      'retriever': args.retriever, 'started_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    status = 2
    try:
        task = next(t for t in tasks_for('dev') if t.example_id == '73')
        docs = load_api_docs(APIDOCS_DIR / f'{task.env_key}.jsonl')
        answer = Bot(args.model, args.retriever).ask(QUESTION, task.library, task.version, docs)
        evidence['answer'] = answer.as_dict()
        evidence['environment'] = task.env_key
        code = extract_python_code(answer.text)
        result = DockerExecutor().run(task, code + '\nimport numpy as np\n' + CHECKS)
        evidence['execution'] = asdict(result)
        evidence['passed'] = result.returncode == 0 and not result.timed_out
        status = 0 if evidence['passed'] else 1
    except (OSError, ValueError, RuntimeError) as exc:
        evidence.update(passed=False, error=str(exc))
        print(f'error: {exc}', file=sys.stderr)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        print(f'RAG demo evidence: {args.output}', flush=True)
    return status


if __name__ == '__main__':
    sys.exit(main())
