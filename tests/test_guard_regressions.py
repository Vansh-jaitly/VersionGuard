import sys
import tempfile
import unittest
from pathlib import Path

from experiment.dataset import FIXTURE_LIBS
from versionguard.check import Finding, check_source, main


class ProbeScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = str(FIXTURE_LIBS / "minilib-2.0")
        sys.path.insert(0, cls.lib)
        sys.modules.pop("minilib", None)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.lib)
        sys.modules.pop("minilib", None)

    def test_probe_only_protects_true_branch(self):
        source = ("import minilib as ml\nif hasattr(ml, 'moving_average'):\n"
                  "    ml.moving_average([1], 2)\nml.moving_average([1], 2)\n")
        findings = check_source(source)
        self.assertEqual([(f.line, f.code, f.level) for f in findings], [(4, "VG001", "error")])

    def test_probe_for_other_owner_does_not_hide_error(self):
        source = "import minilib\nif hasattr(minilib, 'append'):\n    minilib.Table.append\n"
        self.assertEqual([f.symbol for f in check_source(source)], ["minilib.Table.append"])

    def test_or_condition_does_not_guarantee_attribute_presence(self):
        source = ("import minilib\nif hasattr(minilib, 'moving_average') or True:\n"
                  "    minilib.moving_average([1], 2)\n")
        self.assertEqual(len(check_source(source)), 1)

    def test_truthy_getattr_default_does_not_guarantee_presence(self):
        source = ("import minilib\nif getattr(minilib, 'moving_average', True):\n"
                  "    minilib.moving_average([1], 2)\n")
        self.assertEqual(len(check_source(source)), 1)

    def test_empty_and_missing_targets_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main([directory]), 2)
            self.assertEqual(main([str(Path(directory) / "missing.py")]), 2)

    def test_annotations_escape_filename_and_message(self):
        finding = Finding("file,one.py", 1, 1, "VG001", "error", "x", "line\r\nnext%")
        annotation = finding.github()
        self.assertIn("file=file%2Cone.py", annotation)
        self.assertIn("line%0D%0Anext%25", annotation)


if __name__ == "__main__":
    unittest.main()
