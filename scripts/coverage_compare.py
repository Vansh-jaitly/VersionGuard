"""Compare coverage over matching core source files, keeping provenance explicit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def compare(before: dict, after: dict) -> list[dict]:
    def normalized(report):
        return {name.replace('\\', '/'): data for name, data in report['files'].items()}
    baseline, current = normalized(before), normalized(after)
    if set(baseline) != set(current):
        raise ValueError('Coverage file lists differ. Re-run before/after on the same source revision.')
    rows = []
    for name in sorted(baseline):
        a, b = baseline[name], current[name]
        lines_a = set(a['executed_lines']) | set(a['missing_lines'])
        lines_b = set(b['executed_lines']) | set(b['missing_lines'])
        if lines_a != lines_b:
            raise ValueError(f'Source statement lines differ for {name}. Use identical source for both measurements.')
        rows.append({'file': name, 'before': a['summary']['percent_covered'], 'after': b['summary']['percent_covered'],
                     'gain_points': b['summary']['percent_covered'] - a['summary']['percent_covered']})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        before, after = (json.loads(path.read_text(encoding='utf-8')) for path in (args.before, args.after))
        rows = compare(before, after)
        lines = ['# Coverage comparison', '',
                 'Comparison only; this does not establish which tool generated tests or that source bytes were identical.',
                 'Record tool provenance and source revision alongside this report.', '',
                 '| File | Before | After | Gain, points |', '|---|---:|---:|---:|']
        lines += [f"| {r['file']} | {r['before']:.1f}% | {r['after']:.1f}% | {r['gain_points']:+.1f} |" for r in rows]
        a, b = before['totals']['percent_covered'], after['totals']['percent_covered']
        lines += ['', f'Total: {a:.2f}% -> {b:.2f}% ({b-a:+.2f} points).', '']
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text('\n'.join(lines), encoding='utf-8')
        print(f'Coverage comparison saved: {args.output}')
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
