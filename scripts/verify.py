"""Run the local CI checks and save logs, coverage and fixed-input integrity."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from experiment.dataset import DATA_FILE, RETRIEVAL_CACHE, SPLIT_FILE, sha256_of
from experiment.run import PROTOCOL_FILE
from versionguard.config import REPO_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO_ROOT / 'results' / 'verification')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixed_paths = [DATA_FILE, RETRIEVAL_CACHE, SPLIT_FILE, PROTOCOL_FILE]
    fixed_paths += sorted((REPO_ROOT / 'results').glob('*-qwen2.5_7b-instruct.*'))
    before = {str(path.relative_to(REPO_ROOT)): sha256_of(path) for path in fixed_paths if path.is_file()}
    commands = [
        ('lint', ['-m', 'ruff', 'check', '.']),
        ('tests', ['-m', 'coverage', 'run', f'--data-file={output / ".coverage"}', '-m', 'pytest', '-q']),
        ('coverage', ['-m', 'coverage', 'json', f'--data-file={output / ".coverage"}', '-o', str(output / 'coverage.json')]),
        ('fixtures', ['-m', 'experiment.run', '--split', 'fixtures', '--model', 'fake:stale', '--executor', 'host',
                      '--results-dir', str(output / 'fixtures')]),
        ('fixture_report', ['-m', 'experiment.report', '--split', 'fixtures', '--require-complete',
                           '--results-dir', str(output / 'fixtures')]),
        ('guard_demo', ['-m', 'scripts.guard_demo']),
    ]
    summary = {'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'python': sys.version,
               'input_hashes': before, 'checks': []}
    for label, arguments in commands:
        print(f'Running {label}...', flush=True)
        command = [sys.executable, *arguments]
        try:
            done = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, encoding='utf-8',
                                  errors='replace', check=False, timeout=900)
            log = done.stdout + '\n' + done.stderr
            code = done.returncode
        except subprocess.TimeoutExpired as exc:
            log, code = f'Timed out after {exc.timeout} seconds.', 124
        (output / f'{label}.log').write_text(log, encoding='utf-8')
        summary['checks'].append({'name': label, 'command': command, 'exit_code': code, 'log': f'{label}.log'})
        print(f'{label}: {"passed" if code == 0 else "FAILED"}', flush=True)
        if code:
            print(log[-2000:], file=sys.stderr)
            break
    after = {name: sha256_of(REPO_ROOT / name) for name in before}
    summary['fixed_inputs_unchanged'] = before == after
    summary['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    summary['passed'] = len(summary['checks']) == len(commands) and all(c['exit_code'] == 0 for c in summary['checks'])
    summary['passed'] = summary['passed'] and summary['fixed_inputs_unchanged']
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'Verification evidence: {output}')
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
