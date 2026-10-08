import json
import io
import urllib.error
import unittest
from unittest.mock import patch

from versionguard.llm import OllamaLLM


class _Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def read(self):
        return self.body


class HttpFallbackTests(unittest.TestCase):
    def test_direct_ollama_request_preserves_options_and_metrics(self):
        body = {
            "message": {"content": "```python\nprint(1)\n```"},
            "prompt_eval_count": 12,
            "eval_count": 5,
            "total_duration": 2_000_000,
        }
        with patch("versionguard.llm.urllib.request.urlopen", return_value=_Response(body)) as open_url:
            result = OllamaLLM("fake-model")._generate_http("system", "user")

        request = open_url.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "fake-model")
        self.assertEqual(payload["messages"][0]["content"], "system")
        self.assertEqual(payload["messages"][1]["content"], "user")
        self.assertEqual(payload["options"]["temperature"], 0.0)
        self.assertEqual(payload["options"]["seed"], 42)
        self.assertEqual(result.text, "```python\nprint(1)\n```")
        self.assertEqual(result.metrics["input_tokens"], 12)
        self.assertEqual(result.metrics["output_tokens"], 5)

    def test_http_failure_includes_ollama_server_reason(self):
        error = urllib.error.HTTPError("http://localhost/api/chat", 500, "error", {},
                                       io.BytesIO(b'{"error": "model runner has insufficient memory"}'))
        with patch("versionguard.llm.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 500: model runner has insufficient memory"):
                OllamaLLM()._generate_http("system", "user")

    def test_non_object_json_error_body_remains_readable(self):
        error = urllib.error.HTTPError("http://localhost/api/chat", 500, "error", {}, io.BytesIO(b'"server failed"'))
        with patch("versionguard.llm.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "server failed"):
                OllamaLLM()._generate_http("system", "user")


if __name__ == "__main__":
    unittest.main()
