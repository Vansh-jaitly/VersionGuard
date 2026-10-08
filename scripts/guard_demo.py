"""Record an expected removed-API failure and its corrected passing example."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from versionguard.apidocs import dist_version
from versionguard.config import REPO_ROOT


def main() -> int:
    version = dist_version('numpy')
    if version != '1.26.4':
        print(f'error: install requirements-ci.txt for this demo; numpy is {version}', file=sys.stderr)
        return 2
    evidence = {'library': 'numpy', 'version': version, 'examples': {}}
    with tempfile.TemporaryDirectory() as directory:
        for label, filename in [('broken', 'broken.py.txt'), ('fixed', 'fixed.py')]:
            source = REPO_ROOT / 'demo' / filename
            target = Path(directory) / 'example.py'
            target.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'versionguard.check', str(target), '--json'],
                                    capture_output=True, text=True, check=False, cwd=REPO_ROOT)
            if result.returncode not in (0, 1):
                raise RuntimeError(result.stderr or 'Guard demo could not run')
            findings = json.loads(result.stdout)
            for finding in findings:
                finding['file'] = f'demo/{filename}'
            evidence['examples'][label] = {'exit_code': result.returncode, 'findings': findings}
    broken, fixed = evidence['examples']['broken'], evidence['examples']['fixed']
    passed = (broken['exit_code'] == 1 and any(f['code'] == 'VG001' and f['symbol'] == 'numpy.asscalar'
                                            for f in broken['findings']) and fixed['exit_code'] == 0)
    evidence['expected_behavior_verified'] = passed
    output = REPO_ROOT / 'results' / 'guard-demo.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(f'Guard demo: {"passed" if passed else "FAILED"}; evidence: {output}')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
