import unittest

from versionguard.repair import GENERIC_ASSERTION, classify, sanitize_feedback

API_ERROR = '''Traceback (most recent call last):
  File "/work/prog.py", line 9, in <module>
    assert smooth([1, 2, 3, 4, 5]) == [2.0, 3.0, 4.0]
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/work/prog.py", line 4, in smooth
    return minilib.moving_average(readings, 3)
           ^^^^^^^^^^^^^^^^^^^^^^
AttributeError: module 'minilib' has no attribute 'moving_average'
'''

NUMPY_ASSERT = '''Traceback (most recent call last):
  File "/work/prog.py", line 12, in <module>
    np.testing.assert_allclose(f(x), expected_result)
  File "/usr/lib/python3/site-packages/numpy/testing/_private/utils.py", line 1504, in assert_allclose
    assert_array_compare(compare, actual, desired, err_msg=str(err_msg))
  File "/usr/lib/python3/site-packages/numpy/testing/_private/utils.py", line 797, in assert_array_compare
    raise AssertionError(msg)
AssertionError:
Not equal to tolerance rtol=1e-07, atol=0

Mismatched elements: 2 / 3 (66.7%)
 ACTUAL: array([1., 2., 3.])
 DESIRED: array([[9.87654, 8.76543],
                 [7.65432, 6.54321]])
'''


class ClassifyTests(unittest.TestCase):
    def test_categories(self):
        self.assertTrue(classify(0, "").passed)
        self.assertEqual(classify(1, API_ERROR).category, "api_missing")
        self.assertEqual(classify(1, NUMPY_ASSERT).category, "wrong_result")
        self.assertEqual(classify(1, "TypeError: scale() got an unexpected keyword argument 'factor'").category, "api_signature")
        self.assertEqual(classify(1, "TypeError: unsupported operand type(s) for +: 'int' and 'str'").category, "other_error")
        self.assertEqual(classify(1, "ModuleNotFoundError: No module named 'foo'").category, "api_missing")
        self.assertEqual(classify(1, "ValueError: bad").category, "other_error")
        self.assertEqual(classify(-1, "", timed_out=True).status, "timeout")
        self.assertEqual(classify(1, "").error_type, "UnknownError")


class SanitizeTests(unittest.TestCase):
    def test_test_frames_are_removed_and_candidate_frames_kept(self):
        text = sanitize_feedback(API_ERROR, candidate_lines=5)
        self.assertIn("minilib.moving_average(readings, 3)", text)
        self.assertIn("AttributeError: module 'minilib' has no attribute 'moving_average'", text)
        self.assertNotIn("assert smooth", text)       # the test's source line
        self.assertNotIn("[2.0, 3.0, 4.0]", text)     # the expected value
        self.assertNotIn("/work/", text)              # container path

    def test_assertion_messages_never_leak_expected_values(self):
        text = sanitize_feedback(NUMPY_ASSERT, candidate_lines=5)
        self.assertEqual(text, GENERIC_ASSERTION)
        for secret in ("9.87654", "6.54321", "DESIRED", "expected_result"):
            self.assertNotIn(secret, text)

    def test_error_raised_in_the_test_itself(self):
        log = ('Traceback (most recent call last):\n  File "/work/prog.py", line 9, in <module>\n'
               "    assert f(3).shape == (3, 4)\nAttributeError: 'NoneType' object has no attribute 'shape'\n")
        text = sanitize_feedback(log, candidate_lines=5)
        self.assertNotIn("(3, 4)", text)
        self.assertIn("'NoneType' object has no attribute 'shape'", text)

    def test_empty_log(self):
        self.assertTrue(sanitize_feedback("", 3))

    def test_long_logs_are_cut(self):
        log = "Traceback (most recent call last):\n" + "x" * 5000 + "\nValueError: boom\n"
        self.assertLess(len(sanitize_feedback(log, 3)), 1300)


if __name__ == "__main__":
    unittest.main()
