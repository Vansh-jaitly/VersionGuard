import sys
import unittest

from experiment.dataset import FIXTURE_LIBS
from versionguard.check import check_source

LIB_V2 = str(FIXTURE_LIBS / "minilib-2.0")


def codes(source):
    return [(f.code, f.level, f.symbol) for f in check_source(source, "example.py")]


class GuardTests(unittest.TestCase):
    """The guard is checked against the made-up minilib 2.0."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, LIB_V2)
        sys.modules.pop("minilib", None)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(LIB_V2)
        sys.modules.pop("minilib", None)

    def test_valid_code_is_clean(self):
        source = (
            "import json\nimport minilib\nfrom minilib import rolling_mean, Table\n\n"
            "def f(xs):\n    t = minilib.Table([1])\n    return minilib.scale(rolling_mean(xs, 2), by=2), t.count(), json.dumps(1)\n"
        )
        self.assertEqual(codes(source), [])

    def test_removed_function(self):
        found = codes("import minilib\n\ndef f(xs):\n    return minilib.moving_average(xs, 3)\n")
        self.assertEqual(found, [("VG001", "error", "minilib.moving_average")])

    def test_removed_function_via_from_import_and_alias(self):
        self.assertEqual(codes("from minilib import moving_average\n")[0][:2], ("VG001", "error"))
        self.assertEqual(codes("import minilib as ml\nml.moving_average\n")[0][2], "minilib.moving_average")

    def test_removed_method_on_the_class(self):
        self.assertEqual(codes("import minilib\nminilib.Table.append\n"), [("VG001", "error", "minilib.Table.append")])

    def test_renamed_keyword_argument(self):
        found = check_source("import minilib\nminilib.scale([1], factor=2)\n", "example.py")
        self.assertEqual([(f.code, f.symbol) for f in found], [("VG002", "minilib.scale(factor=)")])
        self.assertIn("Accepted arguments: values, by.", found[0].message)  # names what does exist
        self.assertEqual((found[0].line, found[0].file), (2, "example.py"))

    def test_missing_module_reported_once(self):
        found = codes("import not_a_real_package_xyz\nnot_a_real_package_xyz.a\nnot_a_real_package_xyz.b\n")
        self.assertEqual(found, [("VG003", "error", "not_a_real_package_xyz")])

    def test_known_limit_method_on_a_variable_is_invisible(self):
        self.assertEqual(codes("import minilib\n\ndef f(table, row):\n    return table.append(row)\n"), [])

    def test_guarded_and_conditional_code_is_not_an_error(self):
        guarded = "import minilib\ntry:\n    f = minilib.moving_average\nexcept AttributeError:\n    f = minilib.rolling_mean\n"
        self.assertEqual(codes(guarded), [])
        optional = "try:\n    import not_a_real_package_xyz\nexcept ImportError:\n    not_a_real_package_xyz = None\n"
        self.assertEqual(codes(optional), [])
        probed = "import minilib\nif hasattr(minilib, 'moving_average'):\n    f = minilib.moving_average\n"
        self.assertEqual(codes(probed), [])
        conditional = "import minilib\nimport sys\nif sys.version_info < (3, 8):\n    f = minilib.moving_average\n"
        self.assertEqual(codes(conditional), [("VG001", "warning", "minilib.moving_average")])

    def test_type_only_code_is_skipped(self):
        source = (
            "from typing import TYPE_CHECKING\nimport minilib\n"
            "if TYPE_CHECKING:\n    from minilib import NotARealType\n\n"
            "def f(x: minilib.AlsoNotReal) -> minilib.Nope:\n    return x\n"
        )
        self.assertEqual(codes(source), [])

    def test_reassigned_alias_is_not_trusted(self):
        self.assertEqual(codes("import minilib\nminilib = object()\nminilib.anything\n"), [])

    def test_local_modules_and_stdlib_are_ignored(self):
        self.assertEqual(codes("import os\nos.not_real\nfrom . import sibling\n"), [])

    def test_syntax_error_is_a_finding_not_a_crash(self):
        self.assertEqual(codes("def broken(:\n")[0][0], "VG000")


if __name__ == "__main__":
    unittest.main()
