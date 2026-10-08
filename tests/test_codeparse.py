import unittest

from versionguard.codeparse import (
    NoCodeError,
    assemble_program,
    extract_python_code,
    preamble,
    reference_program,
    target_name,
)

START = "import minilib\n\ndef smooth(readings):\n"
TEST = "assert smooth([1, 2, 3]) == [2.0]\n"


class TargetTests(unittest.TestCase):
    def test_target_is_last_top_level_definition(self):
        code = "import x\n\ndef helper():\n    def inner():\n        pass\n\nclass Thing:\n"
        self.assertEqual(target_name(code), "Thing")
        self.assertEqual(target_name(START), "smooth")
        self.assertIsNone(target_name("import x\n"))

    def test_preamble_keeps_imports_only(self):
        self.assertEqual(preamble(START), "import minilib\n\n")


class AssembleTests(unittest.TestCase):
    def check(self, answer, mode):
        program = assemble_program(START, answer, TEST)
        self.assertEqual(program.mode, mode)
        compile(program.source, "prog.py", "exec")  # must be valid Python
        self.assertIn("import minilib", program.candidate)
        self.assertTrue(program.source.endswith(TEST))
        # Everything after candidate_lines is the test.
        tail = program.source.splitlines()[program.candidate_lines:]
        self.assertEqual("\n".join(tail).strip(), TEST.strip())
        return program

    def test_whole_file_in_fence(self):
        self.check("Here you go:\n```python\nimport minilib\n\ndef smooth(readings):\n    return [2.0]\n```\nDone.", "full")

    def test_function_only_gets_the_imports_back(self):
        self.check("```python\ndef smooth(readings):\n    return minilib.rolling_mean(readings, 3)\n```", "function")

    def test_body_only(self):
        self.check("```python\n    return minilib.rolling_mean(readings, 3)\n```", "body")
        self.check("```\nreturn minilib.rolling_mean(readings, 3)\n```", "body")

    def test_starting_code_that_stops_mid_statement(self):
        # Shape of a real sympy task: the starting code ends with "return ".
        start = "import minilib\n\ndef smooth(readings):\n    return "
        for answer, mode in [
            ("```python\nminilib.rolling_mean(readings, 3)\n```", "body"),
            ("```python\ndef smooth(readings):\n    return minilib.rolling_mean(readings, 3)\n```", "function"),
        ]:
            program = assemble_program(start, answer, TEST)
            self.assertEqual(program.mode, mode)
            self.assertIn("return minilib.rolling_mean(readings, 3)", program.candidate)
            self.assertNotIn("return\n", program.candidate)   # never a bare return

    def test_starting_code_that_ends_on_the_def_line_or_a_comment(self):
        # Shapes of real scipy tasks: no trailing newline after "def ...:" or after a comment.
        body = "```python\nwindow = 3\nreturn minilib.rolling_mean(readings, window)\n```"
        for start in ("import minilib\ndef smooth(readings):", "import minilib\ndef smooth(readings):\n    # return a list"):
            program = assemble_program(start, body, TEST)
            self.assertEqual(program.mode, "body")
            self.assertIn("\n    window = 3\n    return minilib.rolling_mean(readings, window)", program.candidate)

    def test_unclosed_fence(self):
        self.check("```python\ndef smooth(readings):\n    return [2.0]\n", "function")

    def test_no_fence_plain_code(self):
        self.check("def smooth(readings):\n    return [2.0]\n", "function")

    def test_prose_is_not_code(self):
        with self.assertRaises(NoCodeError):
            assemble_program(START, "I am sorry, I cannot help with that.", TEST)

    def test_wrong_function_name_falls_back_or_fails(self):
        with self.assertRaises(NoCodeError):
            assemble_program(START, "```python\ndef other():\n  return 1\n  x = (\n```", TEST)


class ReferenceTests(unittest.TestCase):
    def test_reference_rows_as_stored_in_the_benchmark(self):
        # Shapes copied from two real GitChameleon rows (torch 1.9.0 and flask 2.0.1).
        cases = [
            ("import torch\ndef erf(input_tensor: torch.Tensor) -> torch.Tensor:\n",
             "    import numpy as np\n    output = input_tensor\n    return output"),
            ("import flask\nimport datetime\n\ndef convert(td: datetime.timedelta) -> int:\n    ",
             "\n    return flask.helpers.total_seconds(td)\n"),
        ]
        for starting_code, solution in cases:
            program = reference_program(starting_code, solution, "assert True")
            compile(program.source, "prog.py", "exec")
            self.assertEqual(program.source.splitlines()[program.candidate_lines:][-1], "assert True")

    def test_extract_python_code_prefers_python_fence(self):
        answer = "```\nnot python (\n```\n```python\ndef f():\n    return 1\n```"
        self.assertEqual(extract_python_code(answer).strip(), "def f():\n    return 1")


if __name__ == "__main__":
    unittest.main()
