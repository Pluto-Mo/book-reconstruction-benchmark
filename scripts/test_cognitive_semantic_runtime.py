from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Mapping
from typing import Any

from cognitive_semantic_runtime import (
    DEFAULT_CRITERION_SCHEMA,
    DEFAULT_JUDGE_RESPONSE_SCHEMA,
    DEFAULT_LOCATOR_RESPONSE_SCHEMA,
    DEFAULT_REQUEST_SCHEMA,
    LOCATOR_FORBIDDEN_KEYS,
    CommandProvider,
    all_keys,
    run_semantic_pipeline,
)
from runtime_scoring import load_json_object


class ScriptedProvider:
    model_id = "fixture-model"

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.requests: list[Mapping[str, Any]] = []

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        if request["stage"] == "evidence_locator":
            if self.mode == "retry_success" and request["attempt"] == 1:
                return {"status": "none", "quotes": []}
            if self.mode == "bad_quote":
                return {
                    "status": "found",
                    "quotes": [{"quote": "并不存在于文章"}],
                }
            return {"status": "found", "quotes": [{"quote": "甲使乙"}]}

        payload = json.loads(request["messages"][1]["content"])
        candidate_id = payload["evidence_candidates"][0]["candidate_id"]
        if self.mode == "bad_judge":
            candidate_id = "C-unknown"
        return {
            "selected_candidate_ids": [candidate_id],
            "decision": "pass",
            "support_found": True,
            "contradiction_found": False,
            "missing_facets": [],
            "reason": "候选文章明确表达了方向关系。",
            "confidence": 0.9,
        }


class CognitiveSemanticRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.submission = "开头。甲使乙。结尾。"
        self.book_card = {
            "book_id": "tiny-book",
            "cognitive_structures": [
                {
                    "id": "CS-1",
                    "weight": 1.0,
                    "relations": [
                        {
                            "id": "R-1",
                            "weight": 1.0,
                            "required_facets": ["direction"],
                        }
                    ],
                    "paths": [
                        {
                            "id": "P-1",
                            "relation_ids": ["R-1"],
                            "path_type": "mandatory",
                            "weight": 1.0,
                        }
                    ],
                }
            ],
        }
        self.criteria = [
            {
                "schema_version": "1.0",
                "visibility": "verifier_only",
                "book_id": "tiny-book",
                "criterion_id": "R-1",
                "relation": {
                    "relation_type": "causes",
                    "requirement": "候选文章须表达甲导致乙。",
                    "required_facets": ["direction"],
                    "source_nodes": [
                        {
                            "statement": "甲发生。",
                            "role": "premise",
                            "stance_owner": "author",
                            "epistemic_status": "asserted",
                        }
                    ],
                    "target_nodes": [
                        {
                            "statement": "乙发生。",
                            "role": "conclusion",
                            "stance_owner": "author",
                            "epistemic_status": "asserted",
                        }
                    ],
                    "acceptable_paraphrases": ["甲使乙。"],
                    "pass_if": ["明确表达甲到乙的方向。"],
                    "fail_if": ["只并列甲和乙。"],
                    "common_false_positives": ["甲、乙两个词共同出现。"],
                    "contradiction_patterns": ["乙导致甲。"],
                },
                "review_policy": {
                    "recommended": True,
                    "risk_flags": ["direction"],
                },
                "prompt_versions": {
                    "locator": "locator-v1-fixture",
                    "judge": "judge-v1-fixture",
                },
            }
        ]
        generation = {
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 512,
            "seed": 7,
        }
        self.provider_config = {
            "schema_version": "1.0",
            "provider_type": "command",
            "command": ["fixture"],
            "model_id": "fixture-model",
            "timeout_seconds": 5,
            "max_concurrency": 1,
            "max_protocol_attempts": 2,
            "locator_context_chars": 4,
            "generation_parameters": {
                "evidence_locator": generation,
                "relation_adjudicator": generation,
            },
        }
        self.criterion_schema = load_json_object(DEFAULT_CRITERION_SCHEMA)
        self.request_schema = load_json_object(DEFAULT_REQUEST_SCHEMA)
        self.locator_schema = load_json_object(DEFAULT_LOCATOR_RESPONSE_SCHEMA)
        self.judge_schema = load_json_object(DEFAULT_JUDGE_RESPONSE_SCHEMA)

    def run_pipeline(self, provider: ScriptedProvider) -> dict[str, Any]:
        return run_semantic_pipeline(
            book_card=self.book_card,
            criteria=self.criteria,
            submission_text=self.submission,
            submission_id="SUB-1",
            provider_config=self.provider_config,
            provider=provider,
            locator_prompt_text="locator system prompt",
            judge_prompt_text="judge system prompt",
            criterion_schema=self.criterion_schema,
            request_schema=self.request_schema,
            locator_response_schema=self.locator_schema,
            judge_response_schema=self.judge_schema,
        )

    def test_none_then_full_text_review_retries_and_scores(self) -> None:
        provider = ScriptedProvider("retry_success")
        result = self.run_pipeline(provider)
        evidence = result["evidence_results"][0]
        self.assertEqual(evidence["attempts"], 2)
        self.assertEqual(evidence["status"], "found")
        self.assertEqual(evidence["candidates"][0]["quote"], "甲使乙")
        self.assertEqual(result["aggregate"]["status"], "complete")
        self.assertEqual(
            result["aggregate"]["metrics"]["cognitive_relation_coverage"], 1.0
        )

        locator_requests = [
            request
            for request in provider.requests
            if request["stage"] == "evidence_locator"
        ]
        self.assertEqual(len(locator_requests), 2)
        locator_payload = json.loads(locator_requests[0]["messages"][1]["content"])
        self.assertEqual(
            all_keys(locator_payload).intersection(LOCATOR_FORBIDDEN_KEYS),
            set(),
        )

    def test_nonexistent_quotes_become_locator_error_not_semantic_fail(self) -> None:
        result = self.run_pipeline(ScriptedProvider("bad_quote"))
        self.assertEqual(result["evidence_results"][0]["status"], "locator_error")
        self.assertEqual(result["judge_results"], [])
        self.assertEqual(result["aggregate"]["status"], "unscorable")
        self.assertIsNone(result["aggregate"]["metrics"]["cognitive_relation_coverage"])

    def test_invalid_selected_candidate_retries_then_abstains(self) -> None:
        provider = ScriptedProvider("bad_judge")
        result = self.run_pipeline(provider)
        self.assertEqual(result["judge_results"][0]["decision"], "abstain")
        self.assertEqual(result["aggregate"]["status"], "unscorable")
        judge_requests = [
            request
            for request in provider.requests
            if request["stage"] == "relation_adjudicator"
        ]
        self.assertEqual(len(judge_requests), 2)

    def test_command_provider_uses_json_stdin_stdout_without_shell(self) -> None:
        code = (
            "import json,sys; value=json.load(sys.stdin); "
            "json.dump({'seen': value['x']}, sys.stdout)"
        )
        provider = CommandProvider([sys.executable, "-c", code], "fixture-command", 5)
        self.assertEqual(provider.complete({"x": 9}), {"seen": 9})


if __name__ == "__main__":
    unittest.main()
