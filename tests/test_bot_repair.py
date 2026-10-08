import unittest
from unittest.mock import Mock, patch

from versionguard.bot import Bot
from versionguard.llm import LLMResult
from versionguard.check import Finding
from versionguard.store import ApiDoc


class BotRepairTests(unittest.TestCase):
    def test_repair_looks_up_docs_and_sanitizes_assertion_feedback(self):
        bot = Bot("fake:stale", "bm25")
        bot.llm = Mock()
        bot.llm.generate.return_value = LLMResult("proposed code")
        code = "import minilib\ndef smooth(xs):\n    return minilib.moving_average(xs, 2)\n"
        log = "AssertionError: expected secret 123456"
        doc = ApiDoc("minilib.rolling_mean", doc="Compute a moving average.", library="minilib", version="2.0")
        answer = bot.ask("Fix moving average", "minilib", "2.0", [doc], code=code, error_log=log)
        system, user = bot.llm.generate.call_args.args
        self.assertEqual(answer.text, "proposed code")
        self.assertEqual(answer.sources, [doc])
        self.assertIn(code.rstrip(), user)
        self.assertIn("minilib.rolling_mean", user)
        self.assertIn("wrong result", user)
        self.assertNotIn("123456", user)
        self.assertIn("installed version", system)

    def test_repair_requires_both_inputs(self):
        bot = Bot("fake:stale", "bm25")
        with self.assertRaisesRegex(ValueError, "both source code"):
            bot.ask("Fix it", "minilib", code="print(1)")

    def test_proposal_does_not_execute_source(self):
        bot = Bot("fake:stale", "bm25")
        bot.llm = Mock()
        bot.llm.generate.return_value = LLMResult("proposed code")
        answer = bot.ask("Fix it", "minilib", "2.0", [], use_docs=False,
                         code="raise RuntimeError('must not run')", error_log="RuntimeError: broken")
        self.assertEqual(answer.text, "proposed code")

    def test_docs_for_wrong_version_are_rejected_before_generation(self):
        bot = Bot("fake:stale", "bm25")
        bot.llm = Mock()
        doc = ApiDoc("minilib.scale", library="minilib", version="1.0")
        with self.assertRaisesRegex(RuntimeError, "not 2.0"):
            bot.ask("Fix scale", "minilib", "2.0", [doc])
        bot.llm.generate.assert_not_called()

    def test_supplied_documentation_version_is_inferred(self):
        bot = Bot("fake:stale", "bm25")
        doc = ApiDoc("minilib.scale", library="minilib", version="2.0")
        answer = bot.ask("scale", "minilib", docs=[doc])
        self.assertEqual(answer.version, "2.0")

    def test_guard_log_diagnostics_survive_summary_line(self):
        bot = Bot("fake:stale", "bm25")
        bot.llm = Mock()
        bot.llm.generate.return_value = LLMResult("proposed code")
        log = "file.py:3:1: VG001 minilib has no attribute moving_average\nversionguard: 1 error(s)"
        bot.ask("Fix it", "minilib", "2.0", [], use_docs=False, code="import minilib", error_log=log)
        user = bot.llm.generate.call_args.args[1]
        self.assertIn("VG001 minilib has no attribute moving_average", user)

    def test_bad_proposal_is_flagged_when_installed_version_matches(self):
        bot = Bot("fake:stale", "bm25")
        bot.llm = Mock()
        bot.llm.generate.return_value = LLMResult("```python\nimport minilib\nminilib.missing()\n```")
        finding = Finding("<model>", 2, 1, "VG001", "error", "minilib.missing", "missing API")
        with patch("versionguard.bot.apidocs.dist_version", return_value="2.0"), \
                patch("versionguard.bot.check_source", return_value=[finding]):
            answer = bot.ask("Fix it", "minilib", "2.0", [], use_docs=False, code="import minilib", error_log="failed")
        self.assertEqual(answer.guard["status"], "failed")
        self.assertEqual(answer.as_dict()["guard"]["findings"][0]["code"], "VG001")

    def test_different_installed_version_is_not_claimed_to_be_checked(self):
        bot = Bot("fake:stale", "bm25")
        with patch("versionguard.bot.apidocs.dist_version", return_value="1.0"), \
                patch("versionguard.bot.check_source") as guard:
            answer = bot.ask("Fix it", "minilib", "2.0", [], use_docs=False, code="import minilib", error_log="failed")
        guard.assert_not_called()
        self.assertEqual(answer.guard["status"], "not_checked")


if __name__ == "__main__":
    unittest.main()
