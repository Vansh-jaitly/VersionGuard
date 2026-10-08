import base64
import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import guard_changed, import_results, pr_repair, teammate_bundle
from experiment.report import coverage_issues
from versionguard.pr_comment import MARKER, render


class CommentTests(unittest.TestCase):
    def test_model_fences_cannot_escape_comment_and_validation_is_explicit(self):
        answer = {'answer': '```python\nprint(1)\n```\n@person <script>', 'library': 'numpy', 'version': '1.25.0',
                  'sources': [], 'guard': {'status': 'not_checked', 'reason': 'version < mismatch'}}
        body = render(answer, 'demo/<file>.py', 'a' * 40, 'qwen2.5:7b-instruct')
        self.assertTrue(body.startswith(MARKER))
        self.assertIn('````text', body)
        self.assertIn('has not been executed or tested', body)
        self.assertIn('demo/&lt;file&gt;.py', body)
        self.assertIn('version &lt; mismatch', body)


class PrRepairTests(unittest.TestCase):
    def run_proposal(self, changed=False, publish=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, output = root / 'build.log', root / 'preview.md'
            log.write_text('AttributeError: missing API', encoding='utf-8')
            answer = {'answer': 'def fixed():\n    return 1', 'library': 'numpy', 'version': '1.26.4',
                      'guard': {'status': 'clean', 'findings': []}, 'sources': []}
            source = "raise RuntimeError('never execute PR source')\n"
            contents = {'type': 'file', 'encoding': 'base64', 'size': len(source),
                        'content': base64.b64encode(source.encode()).decode()}
            process = SimpleNamespace(returncode=0, stdout=json.dumps(answer), stderr='')
            commits = [('a' * 40, 'owner/repo'), ('b' * 40 if changed else 'a' * 40, 'owner/repo')]
            with patch.object(pr_repair, 'head', side_effect=commits), \
                    patch.object(pr_repair, 'gh_json', return_value=contents), \
                    patch.object(pr_repair.subprocess, 'run', return_value=process) as command, \
                    patch.object(pr_repair, 'post_comment') as post, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
                args = ['--repo', 'owner/repo', '--pr', '12', '--code', 'src/space name.py', '--error-log', str(log),
                        '--library', 'numpy', '--output', str(output)]
                if publish:
                    args += ['--post']
                status = pr_repair.main(args)
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(output.with_suffix('.json').read_text())['head_sha'], 'a' * 40)
            self.assertIn('versionguard.ask', command.call_args.args[0])
            self.assertNotIn(source, command.call_args.args[0])
            return status, post.call_count, errors.getvalue()

    def test_preview_is_saved_without_posting(self):
        status, posts, _ = self.run_proposal()
        self.assertEqual((status, posts), (0, 0))

    def test_changed_head_blocks_post_but_keeps_preview(self):
        status, posts, error = self.run_proposal(changed=True, publish=True)
        self.assertEqual((status, posts), (2, 0))
        self.assertIn('PR changed', error)

    def test_explicit_post_uses_the_reviewed_commit(self):
        status, posts, _ = self.run_proposal(publish=True)
        self.assertEqual((status, posts), (0, 1))

    def test_comment_update_only_targets_owned_marker(self):
        comments = [[{'id': 1, 'user': {'login': 'other'}, 'body': MARKER},
                     {'id': 2, 'user': {'login': 'me'}, 'body': 'ordinary comment'},
                     {'id': 3, 'user': {'login': 'me'}, 'body': MARKER + '\nold'}]]
        with patch.object(pr_repair, 'gh_json', side_effect=[{'login': 'me'}, comments, {}]) as api:
            pr_repair.post_comment('owner/repo', 1, 'new body')
        self.assertEqual(api.call_args.args, ('repos/owner/repo/issues/comments/3', {'body': 'new body'}, 'PATCH'))

    def test_path_traversal_is_rejected_before_network(self):
        with patch.object(pr_repair, 'gh_json') as api, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                pr_repair.main(['--repo', 'owner/repo', '--pr', '1', '--code', '../evil.py', '--error-log', 'log',
                                '--library', 'numpy'])
        api.assert_not_called()


class DeliveryTests(unittest.TestCase):
    def test_cross_model_settings_are_checked(self):
        metas = {'a': {'temperature': 0, 'llm': {'ollama_version': 'one'}},
                 'b': {'temperature': 1, 'llm': {'ollama_version': 'two'}}}
        issues = coverage_issues('fixtures', {'a': {}, 'b': {}}, metas)
        self.assertTrue(any('different temperature' in issue for issue in issues))
        self.assertTrue(any('different Ollama' in issue for issue in issues))

    def test_result_import_rejects_changed_data_before_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'test-real_model.jsonl'
            path.write_text('', encoding='utf-8')
            path.with_suffix('.meta.json').write_text(json.dumps({'model': 'real:model', 'split': 'test',
                                                                'dataset_sha256': 'wrong'}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'dataset_sha256'):
                import_results.validate(path, root / 'destination')
            self.assertFalse((root / 'destination').exists())

    def test_bundle_round_trip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'README.md', root / 'handoff.zip'
            source.write_text('handoff content', encoding='utf-8')
            teammate_bundle.write_bundle(root, [source], output)
            self.assertEqual(teammate_bundle.verify_bundle(output), 1)
            with zipfile.ZipFile(output) as archive:
                manifest = archive.read('VersionGuard/HANDOFF_MANIFEST.json')
            with zipfile.ZipFile(output, 'w') as archive:
                archive.writestr('VersionGuard/README.md', 'tampered')
                archive.writestr('VersionGuard/HANDOFF_MANIFEST.json', manifest)
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                teammate_bundle.verify_bundle(output)

    def test_guard_preserves_spaces_and_excludes_fixture_examples(self):
        with patch.object(guard_changed.Path, 'is_file', return_value=True):
            paths = guard_changed.application_files(b'demo/space name.py\0experiment/fixtures/broken.py\0tests/test.py\0')
        self.assertEqual(paths, ['demo/space name.py'])


if __name__ == '__main__':
    unittest.main()
