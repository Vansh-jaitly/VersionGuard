import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment import doctor
from experiment.dataset import sha256_of
from versionguard import ask


class AskCliTests(unittest.TestCase):
    def test_repair_json_command_reads_files_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.py"
            log = root / "build.log"
            docs = root / "docs.jsonl"
            original = "import minilib\nprint(minilib.scale([1], factor=2))\n"
            source.write_text(original, encoding="utf-8")
            log.write_text("TypeError: scale() got an unexpected keyword argument 'factor'", encoding="utf-8")
            docs.write_text(json.dumps({"qualname": "minilib.scale", "library": "minilib", "version": "2.0",
                                        "signature": "(values, by=1.0)", "doc": "Scale values."}) + "\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = ask.main(["Fix scale", "--library", "minilib", "--docs", str(docs), "--code", str(source),
                                   "--error-log", str(log), "--retriever", "bm25", "--model", "fake:stale", "--json"])
            self.assertEqual(status, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["version"], "2.0")
            self.assertEqual(payload["sources"], ["minilib.scale"])
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_missing_repair_partner_is_argument_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            ask.main(["Fix it", "--library", "minilib", "--code", "broken.py"])
        self.assertEqual(raised.exception.code, 2)

    def test_missing_repair_source_is_readable_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            status = ask.main(["Fix it", "--library", "minilib", "--model", "fake:stale",
                               "--code", "nonexistent-source-file-for-test.py", "--error-log", "build.log"])
        self.assertEqual(status, 2)
        self.assertIn("error:", output.getvalue())


class DoctorCliTests(unittest.TestCase):
    def check_cache(self, usable_ids):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, split, cache = (root / name for name in ("data.jsonl", "split.json", "cache.json"))
            data.write_text("{}\n", encoding="utf-8")
            split.write_text(json.dumps({"dev": ["a"], "test": ["b"], "dataset_sha256": sha256_of(data)}), encoding="utf-8")
            cache.write_text(json.dumps({"tasks": {key: {"usable": True} for key in usable_ids}}), encoding="utf-8")
            status = {"connected": True, "is_configured_model_available": True, "ollama_version": "test"}
            original_import = __import__

            def optional_import(name, *args, **kwargs):
                if name in {"langchain_ollama", "langchain_chroma", "langchain_huggingface"}:
                    raise ModuleNotFoundError(name)
                return original_import(name, *args, **kwargs)

            with patch.object(doctor, "DATA_FILE", data), patch.object(doctor, "SPLIT_FILE", split), \
                    patch.object(doctor, "RETRIEVAL_CACHE", cache), patch.object(doctor, "check_connection", return_value=status), \
                    patch.object(doctor.DockerExecutor, "available", return_value=(True, "test")), \
                    patch("builtins.__import__", side_effect=optional_import), contextlib.redirect_stdout(io.StringIO()) as output:
                result = doctor.main(["--model", "local-model"])
            return result, output.getvalue()

    def test_http_fallback_does_not_block_ready_laptop(self):
        result, output = self.check_cache(["a", "b"])
        self.assertEqual(result, 0)
        self.assertIn("HTTP fallback", output)
        self.assertIn("2/2 selected tasks usable", output)

    def test_incomplete_preparation_is_not_ready(self):
        result, output = self.check_cache(["a"])
        self.assertEqual(result, 1)
        self.assertIn("prepare is incomplete", output)


if __name__ == "__main__":
    unittest.main()
