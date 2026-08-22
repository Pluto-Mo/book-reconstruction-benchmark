from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from discourse_semantic_runtime import run_pipeline
from runtime_scoring import REPO_ROOT, load_json_object


class FakeProvider:
    model_id = "fake/frozen-model"

    def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(request["messages"][1]["content"])
        stage = request["stage"]
        if stage == "authorial_edge_locator":
            return {"status": "found", "quotes": [{"quote": "第一段建立前提。"}]}
        if stage == "authorial_edge_adjudicator":
            return {
                "edge_id": payload["edge"]["edge_id"],
                "selected_candidate_ids": [
                    payload["evidence_candidates"][0]["candidate_id"]
                ],
                "rhetorical_function_preserved": True,
                "downstream_dependency_preserved": True,
                "contradiction_found": False,
                "missing_facets": [],
                "reason": "关系和下游使用均明确。",
                "confidence": 1.0,
            }
        if stage == "discourse_structure_extractor":
            text = payload["submission_text"]
            first_end = text.index("\n\n")
            second_start = first_end + 2
            return {
                "controlling_question": "前提如何产生结论？",
                "major_units": [
                    {
                        "unit_id": "U01",
                        "start_char": 0,
                        "end_char": first_end,
                        "function": "establish_premise",
                        "spine_contribution": "建立前提",
                    },
                    {
                        "unit_id": "U02",
                        "start_char": second_start,
                        "end_char": len(text),
                        "function": "close_argument",
                        "spine_contribution": "推出并回收结论",
                    },
                ],
                "examples": [
                    {
                        "example_id": "EX01",
                        "start_char": second_start,
                        "end_char": second_start + len("第二段用案例"),
                        "host_unit_id": "U02",
                        "proposed_function": "evidence",
                    }
                ],
            }
        if stage == "editorial_local_progression":
            return {
                "probe_id": payload["probe_id"],
                "relation_identifiable": True,
                "forward_dependency": True,
                "advances_argument": True,
                "evidence": ["因此"],
                "reason": "后段使用前段。",
            }
        if stage == "editorial_global_order":
            return {
                "probe_id": payload["probe_id"],
                "winner": "left" if payload["left"]["order"] == "original" else "right",
                "confidence": "sufficient",
                "reason": "前提必须先出现。",
            }
        if stage == "editorial_spine_connectivity":
            return {
                "units": [
                    {"unit_id": unit["unit_id"], "orphan": False, "reason": "推进中心线。"}
                    for unit in payload["units"]
                ]
            }
        if stage == "editorial_example_integration":
            return {
                "probe_id": payload["probe_id"],
                "function": "evidence",
                "integrated": True,
                "reason": "案例支撑结论。",
            }
        if stage == "editorial_closure":
            return {
                "returns_to_opening": True,
                "depends_on_body": True,
                "non_generic": True,
                "evidence": ["回到前提"],
                "reason": "结尾依赖全文推进。",
            }
        raise AssertionError(f"unexpected stage {stage}")


class DiscourseSemanticRuntimeTests(unittest.TestCase):
    def test_complete_pipeline_with_position_reversal(self) -> None:
        submission = "第一段建立前提。\n\n第二段用案例，因此推出结论并回到前提。"
        book_card = {
            "book_id": "book-dev",
            "source_anchors": [
                {
                    "id": "SA-A",
                    "evidence_summary": "前提。",
                    "argument_function": "建立前提。",
                },
                {
                    "id": "SA-B",
                    "evidence_summary": "结论。",
                    "argument_function": "推出结论。",
                },
            ],
        }
        edge = {
            "id": "AE-001",
            "source_a_anchor_ids": ["SA-A"],
            "source_b_anchor_ids": ["SA-B"],
            "linked_cognitive_relation_ids": ["R-1"],
            "edge_type": "premise_to_consequence",
            "relation_description": "前提产生结论。",
            "rhetorical_role": "governing_premise",
            "required_facets": [
                "direction",
                "rhetorical_function",
                "downstream_dependency",
            ],
            "expected_downstream": ["正文使用前提推出结论。"],
            "hard_negative_relations": ["只并列前提和结论。"],
            "stratum": "global_cross_chapter",
            "weight": 1.0,
            "critical": True,
        }
        discourse_card = {
            "authorial_edges": [edge],
            "sampling_plan": {
                "seed": 20260822,
                "panels": [
                    {"id": "PANEL-1", "edge_ids": ["AE-001"], "rollout_indices": [1]}
                ],
            },
            "editorial_probe_config": {
                "structure_extraction": {"max_major_units": 8},
                "local_progression": {
                    "sample_size": 8,
                    "criteria": [
                        "relation_identifiable",
                        "forward_dependency",
                        "advances_argument",
                    ],
                },
                "global_order": {"sample_size": 4},
                "spine_connectivity": {
                    "accepted_roles": ["establish_premise", "close_argument"],
                    "orphan_definition": "不能推进中心问题。",
                },
                "example_integration": {
                    "sample_size": 3,
                    "accepted_functions": [
                        "evidence",
                        "counterexample",
                        "boundary",
                        "turn",
                        "application",
                        "synthesis",
                    ],
                },
                "closure": {
                    "criteria": [
                        "returns_to_opening",
                        "depends_on_body",
                        "non_generic",
                    ]
                },
                "weights": {
                    "local_progression": 0.3,
                    "global_order": 0.3,
                    "spine_connectivity": 0.2,
                    "example_integration": 0.1,
                    "closure": 0.1,
                },
            },
            "dimension_weights": {
                "authorial_edge_recovery": 0.5,
                "editorial_coherence": 0.5,
            },
        }
        cognitive = {
            "relation_results": [
                {"relation_id": "R-1", "outcome": "pass"}
            ]
        }
        provider_config = {
            "model_id": FakeProvider.model_id,
            "max_concurrency": 1,
            "max_protocol_attempts": 2,
            "locator_context_chars": 80,
            "generation_parameters": {
                "evidence_locator": {
                    "temperature": 0,
                    "top_p": 1,
                    "max_output_tokens": 512,
                    "seed": 17,
                },
                "relation_adjudicator": {
                    "temperature": 0,
                    "top_p": 1,
                    "max_output_tokens": 512,
                    "seed": 17,
                },
            },
        }
        schema_names = {
            "request": "model-request.schema.json",
            "locator": "locator-model-response.schema.json",
            "edge_judge": "authorial-edge-judge-model-response.schema.json",
            "structure": "discourse-structure-model-response.schema.json",
            "local": "editorial-local-model-response.schema.json",
            "global": "editorial-global-order-model-response.schema.json",
            "spine": "editorial-spine-model-response.schema.json",
            "example": "editorial-example-model-response.schema.json",
            "closure": "editorial-closure-model-response.schema.json",
            "aggregate": "discourse-aggregate.schema.json",
        }
        schemas = {
            key: load_json_object(REPO_ROOT / "schemas" / filename)
            for key, filename in schema_names.items()
        }
        result = run_pipeline(
            book_card=book_card,
            discourse_card=discourse_card,
            cognitive_aggregate=cognitive,
            submission_text=submission,
            submission_id="submission-1",
            rollout_index=1,
            provider_config=provider_config,
            provider=FakeProvider(),
            prompts={
                "edge_locator": "locator",
                "edge_judge": "edge judge",
                "structure": "structure",
                "editorial": "editorial",
            },
            prompt_versions={
                "edge_locator": "locator-v1",
                "edge_judge": "edge-v1",
                "structure": "structure-v1",
                "editorial": "editorial-v1",
            },
            schemas=schemas,
        )
        self.assertEqual(result["aggregate"]["status"], "complete")
        self.assertEqual(result["aggregate"]["authorial_edge_recovery"], 1.0)
        self.assertEqual(result["aggregate"]["editorial"]["global_order"], 1.0)
        self.assertEqual(result["aggregate"]["discourse_reconstruction"], 1.0)


if __name__ == "__main__":
    unittest.main()
