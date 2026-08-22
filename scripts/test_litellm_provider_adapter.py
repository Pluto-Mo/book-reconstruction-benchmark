from __future__ import annotations

import unittest

from litellm_provider_adapter import (
    AdapterProtocolError,
    build_completion_kwargs,
    parse_response_object,
)


class LiteLLMProviderAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = {
            "model_id": "anthropic/frozen-model",
            "stage": "evidence_locator",
            "messages": [
                {"role": "system", "content": "Locate evidence."},
                {"role": "user", "content": "{}"},
            ],
            "generation_parameters": {
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 512,
                "seed": 17,
            },
            "response_schema": {
                "type": "object",
                "required": ["status"],
                "properties": {"status": {"type": "string"}},
            },
        }

    def test_maps_frozen_request_without_own_retries(self) -> None:
        kwargs = build_completion_kwargs(self.request, {})
        self.assertEqual(kwargs["model"], "anthropic/frozen-model")
        self.assertEqual(kwargs["max_tokens"], 512)
        self.assertEqual(kwargs["num_retries"], 0)
        self.assertTrue(kwargs["response_format"]["json_schema"]["strict"])

    def test_maps_explicit_qwen_judge_connection_and_thinking(self) -> None:
        kwargs = build_completion_kwargs(
            self.request,
            {
                "BENCHMARK_JUDGE_API_KEY": "test-secret",
                "BENCHMARK_JUDGE_BASE_URL": "https://qwen.example/v1",
                "BENCHMARK_JUDGE_ENABLE_THINKING": "true",
            },
        )
        self.assertEqual(kwargs["api_key"], "test-secret")
        self.assertEqual(kwargs["api_base"], "https://qwen.example/v1")
        self.assertEqual(kwargs["extra_body"], {"enable_thinking": True})

    def test_rejects_partial_explicit_judge_connection(self) -> None:
        with self.assertRaisesRegex(AdapterProtocolError, "must be set together"):
            build_completion_kwargs(
                self.request,
                {"BENCHMARK_JUDGE_API_KEY": "test-secret"},
            )

    def test_parses_json_object_from_text_content(self) -> None:
        response = {
            "choices": [{"message": {"content": '{"status":"found","quotes":[]}'}}]
        }
        self.assertEqual(
            parse_response_object(response),
            {"status": "found", "quotes": []},
        )

    def test_rejects_non_object_provider_content(self) -> None:
        response = {"choices": [{"message": {"content": "[]"}}]}
        with self.assertRaisesRegex(AdapterProtocolError, "one JSON object"):
            parse_response_object(response)


if __name__ == "__main__":
    unittest.main()
