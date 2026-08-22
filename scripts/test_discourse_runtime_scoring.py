from __future__ import annotations

import hashlib
import unittest

from discourse_runtime_scoring import (
    aggregate_authorial_edges,
    aggregate_discourse,
    aggregate_editorial,
    canonical_global_score,
    deterministic_sample,
    prose_paragraph_spans,
    strict_content_gate,
    validate_structure,
)
from runtime_scoring import RuntimeValidationError


class DiscourseRuntimeScoringTests(unittest.TestCase):
    def test_strict_content_gate(self) -> None:
        self.assertEqual(
            strict_content_gate(["R1", "R2"], {"R1": "pass", "R2": "pass"})[0],
            1,
        )
        self.assertEqual(
            strict_content_gate(["R1", "R2"], {"R1": "pass", "R2": "fail"})[0],
            0,
        )
        self.assertIsNone(
            strict_content_gate(
                ["R1", "R2"], {"R1": "pass", "R2": "infrastructure_error"}
            )[0]
        )
        with self.assertRaises(RuntimeValidationError):
            strict_content_gate(["R1", "R2"], {"R1": "pass"})

    def test_structure_validation_rejects_overlap_and_bad_host(self) -> None:
        text = "第一单元。\n\n第二单元。"
        config = {
            "structure_extraction": {"max_major_units": 8},
            "spine_connectivity": {"accepted_roles": ["frame_problem"]},
        }
        structure = {
            "controlling_question": "怎样推进？",
            "major_units": [
                {
                    "unit_id": "U01",
                    "start_char": 0,
                    "end_char": 7,
                    "function": "frame_problem",
                    "spine_contribution": "提出问题",
                },
                {
                    "unit_id": "U02",
                    "start_char": 5,
                    "end_char": len(text),
                    "function": "frame_problem",
                    "spine_contribution": "回答问题",
                },
            ],
            "examples": [
                {
                    "example_id": "EX01",
                    "start_char": 0,
                    "end_char": 2,
                    "host_unit_id": "U02",
                    "proposed_function": "evidence",
                }
            ],
        }
        with self.assertRaises(RuntimeValidationError):
            validate_structure(structure, text, config)

    def test_deterministic_sampling_ignores_input_order(self) -> None:
        values = [{"id": str(index)} for index in range(12)]
        kwargs = {
            "sample_size": 4,
            "seed": 20260822,
            "submission_sha256": hashlib.sha256(b"submission").hexdigest(),
            "probe_name": "local_progression",
            "object_id": lambda value: value["id"],
        }
        first = deterministic_sample(values, **kwargs)
        second = deterministic_sample(list(reversed(values)), **kwargs)
        self.assertEqual(first, second)

    def test_paragraphs_exclude_heading_only_blocks(self) -> None:
        text = "# 标题\n\n第一段。\n\n## 小节\n\n第二段。"
        self.assertEqual(
            [item["text"] for item in prose_paragraph_spans(text)],
            ["第一段。", "第二段。"],
        )

    def test_position_reversal_mapping(self) -> None:
        self.assertEqual(
            canonical_global_score(
                {"winner": "left", "confidence": "sufficient"},
                {"winner": "right", "confidence": "sufficient"},
            ),
            (1.0, "original"),
        )
        self.assertEqual(
            canonical_global_score(
                {"winner": "right", "confidence": "sufficient"},
                {"winner": "left", "confidence": "sufficient"},
            ),
            (0.0, "swapped"),
        )
        self.assertEqual(
            canonical_global_score(
                {"winner": "left", "confidence": "sufficient"},
                {"winner": "left", "confidence": "sufficient"},
            )[0],
            0.5,
        )

    def test_aggregators_are_deterministic_and_keep_submetrics(self) -> None:
        panel = {"edge_ids": ["AE-1", "AE-2"]}
        edge_score, strata = aggregate_authorial_edges(
            [
                {
                    "edge_id": "AE-1",
                    "status": "complete",
                    "score": 1.0,
                    "weight": 1.0,
                    "stratum": "global",
                },
                {
                    "edge_id": "AE-2",
                    "status": "gated_out",
                    "score": 0.0,
                    "weight": 1.0,
                    "stratum": "local",
                },
            ],
            panel,
        )
        self.assertEqual(edge_score, 0.5)
        self.assertEqual(strata, {"global": 1.0, "local": 0.0})
        summaries = {
            name: {"status": "complete", "score": 1.0}
            for name in (
                "local_progression",
                "global_order",
                "spine_connectivity",
                "example_integration",
                "closure",
            )
        }
        weights = {
            "local_progression": 0.3,
            "global_order": 0.3,
            "spine_connectivity": 0.2,
            "example_integration": 0.1,
            "closure": 0.1,
        }
        editorial = aggregate_editorial(summaries, weights)
        aggregate = aggregate_discourse(
            book_id="book",
            submission_id="submission",
            panel_id="panel",
            authorial_score=edge_score,
            authorial_strata=strata,
            editorial=editorial,
            dimension_weights={
                "authorial_edge_recovery": 0.5,
                "editorial_coherence": 0.5,
            },
        )
        self.assertEqual(aggregate["discourse_reconstruction"], 0.75)


if __name__ == "__main__":
    unittest.main()
