import unittest

from scripts.coverage_compare import compare


class CoverageComparisonTests(unittest.TestCase):
    def report(self, executed, missing):
        total = len(executed) + len(missing)
        return {'files': {'versionguard/check.py': {'executed_lines': executed, 'missing_lines': missing,
                                                   'summary': {'percent_covered': 100 * len(executed) / total}}}}

    def test_new_test_covers_previously_missing_statement(self):
        rows = compare(self.report([1], [2]), self.report([1, 2], []))
        self.assertEqual(rows[0]['gain_points'], 50)

    def test_changed_source_cannot_be_presented_as_test_coverage_gain(self):
        with self.assertRaisesRegex(ValueError, 'Source statement lines differ'):
            compare(self.report([1], [2]), self.report([1, 2], [3]))

    def test_changed_module_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'file lists differ'):
            compare(self.report([1], [2]), {'files': {}})
