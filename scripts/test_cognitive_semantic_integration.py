from __future__ import annotations

import json
import unittest
from collections.abc import Mapping
from typing import Any

from cognitive_semantic_runtime import (
    DEFAULT_CRITERION_SCHEMA,
    DEFAULT_JUDGE_RESPONSE_SCHEMA,
    DEFAULT_LOCATOR_RESPONSE_SCHEMA,
    DEFAULT_REQUEST_SCHEMA,
    REPO_ROOT,
    run_semantic_pipeline,
)
from runtime_scoring import load_json_object, load_jsonl_objects


class ProtocolPassProvider:
    """Protocol smoke fixture; it makes no semantic claim."""

    model_id = "protocol-pass-fixture"

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = json.loads(request["messages"][1]["content"])
        if request["stage"] == "evidence_locator":
            return {
                "status": "found",
                "quotes": [{"quote": payload["submission_text"]}],
                "notes": "Protocol-only full-submission fixture.",
            }
        return {
            "selected_candidate_ids": [
                payload["evidence_candidates"][0]["candidate_id"]
            ],
            "decision": "pass",
            "support_found": True,
            "contradiction_found": False,
            "missing_facets": [],
            "reason": "Protocol-only fixture judgment; not semantic calibration.",
            "confidence": 1.0,
        }


class FullDevelopmentCardProtocolTests(unittest.TestCase):
    def test_all_sixty_relations_complete_the_provider_protocol(self) -> None:
        book_card = load_json_object(
            REPO_ROOT / "workbench/breakthrough-advertising/book_card.draft.json"
        )
        criteria = load_jsonl_objects(
            REPO_ROOT / "workbench/breakthrough-advertising/runtime/"
            "cognitive_criteria.draft.jsonl"
        )
        submission = (
            REPO_ROOT / "workbench/breakthrough-advertising/oracle_l8000.draft.md"
        ).read_text(encoding="utf-8")
        generation = {
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 512,
            "seed": 7,
        }
        provider_config = {
            "schema_version": "1.0",
            "provider_type": "command",
            "command": ["protocol-fixture"],
            "model_id": "protocol-pass-fixture",
            "timeout_seconds": 5,
            "max_concurrency": 4,
            "max_protocol_attempts": 2,
            "locator_context_chars": 8,
            "generation_parameters": {
                "evidence_locator": generation,
                "relation_adjudicator": generation,
            },
        }

        result = run_semantic_pipeline(
            book_card=book_card,
            criteria=criteria,
            submission_text=submission,
            submission_id="PROTOCOL-SMOKE-001",
            provider_config=provider_config,
            provider=ProtocolPassProvider(),
            locator_prompt_text="locator protocol smoke",
            judge_prompt_text="judge protocol smoke",
            criterion_schema=load_json_object(DEFAULT_CRITERION_SCHEMA),
            request_schema=load_json_object(DEFAULT_REQUEST_SCHEMA),
            locator_response_schema=load_json_object(DEFAULT_LOCATOR_RESPONSE_SCHEMA),
            judge_response_schema=load_json_object(DEFAULT_JUDGE_RESPONSE_SCHEMA),
        )

        self.assertEqual(len(result["evidence_results"]), 60)
        self.assertEqual(len(result["judge_results"]), 60)
        self.assertEqual(len(result["events"]), 120)
        self.assertEqual(result["aggregate"]["relation_counts"]["pass"], 60)
        self.assertEqual(result["aggregate"]["status"], "complete")
        self.assertEqual(
            result["aggregate"]["metrics"]["cognitive_relation_coverage"], 1.0
        )
        self.assertEqual(result["aggregate"]["metrics"]["complete_core_path_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
