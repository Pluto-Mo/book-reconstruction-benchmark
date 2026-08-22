from __future__ import annotations

import copy
import math
import unittest

from runtime_scoring import (
    RuntimeValidationError,
    score_adjudication_bundle,
    validate_cognitive_aggregate,
    validate_evidence_result,
    validate_judge_result,
)


class RuntimeScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.submission = "甲乙丙丁"
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
                        },
                        {
                            "id": "R-2",
                            "weight": 3.0,
                            "required_facets": ["direction"],
                        },
                        {
                            "id": "R-3",
                            "weight": 1.0,
                            "required_facets": ["direction"],
                        },
                        {
                            "id": "R-4",
                            "weight": 1.0,
                            "required_facets": ["direction"],
                        },
                    ],
                    "paths": [
                        {
                            "id": "P-M",
                            "relation_ids": ["R-1", "R-2"],
                            "path_type": "mandatory",
                            "weight": 2.0,
                        },
                        {
                            "id": "P-A1",
                            "relation_ids": ["R-3"],
                            "path_type": "alternative",
                            "alternative_group": "G-1",
                            "weight": 1.0,
                        },
                        {
                            "id": "P-A2",
                            "relation_ids": ["R-4"],
                            "path_type": "alternative",
                            "alternative_group": "G-1",
                            "weight": 1.0,
                        },
                    ],
                }
            ],
        }

    def evidence(self, relation_id: str, *, status: str = "found") -> dict[str, object]:
        index = int(relation_id[-1]) - 1
        candidates: list[dict[str, object]]
        attempts = 1
        if status == "found":
            candidates = [
                {
                    "candidate_id": f"C-{relation_id}",
                    "quote": self.submission[index : index + 1],
                    "start_char": index,
                    "end_char": index + 1,
                    "context_before": self.submission[max(0, index - 1) : index],
                    "context_after": self.submission[index + 1 : index + 2],
                }
            ]
        else:
            candidates = []
            attempts = 2 if status == "none" else 1
        return {
            "schema_version": "1.0",
            "evidence_result_id": f"E-{relation_id}",
            "book_id": "tiny-book",
            "submission_id": "SUB-1",
            "criterion_id": relation_id,
            "status": status,
            "candidates": candidates,
            "attempts": attempts,
            "locator_model": "fixture-locator",
            "prompt_version": "fixture-v1",
        }

    def judge(
        self,
        relation_id: str,
        decision: str,
        *,
        evidence_status: str = "found",
    ) -> dict[str, object]:
        if decision == "pass":
            selected = [f"C-{relation_id}"]
            support = True
            contradiction = False
            missing: list[str] = []
            confidence = 0.9
        elif decision == "fail":
            selected = [] if evidence_status == "none" else [f"C-{relation_id}"]
            support = False
            contradiction = False
            missing = ["direction"]
            confidence = 0.9
        else:
            selected = [f"C-{relation_id}"]
            support = True
            contradiction = False
            missing = []
            confidence = 0.4
        return {
            "schema_version": "2.0",
            "book_id": "tiny-book",
            "submission_id": "SUB-1",
            "criterion_id": relation_id,
            "evidence_result_id": f"E-{relation_id}",
            "selected_candidate_ids": selected,
            "decision": decision,
            "support_found": support,
            "contradiction_found": contradiction,
            "missing_facets": missing,
            "reason": "fixture judgment",
            "confidence": confidence,
            "judge_model": "fixture-judge",
            "prompt_version": "fixture-v1",
        }

    def bundle(
        self,
        decisions: dict[str, str],
        *,
        evidence_statuses: dict[str, str] | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        statuses = evidence_statuses or {}
        evidence_results: list[dict[str, object]] = []
        judge_results: list[dict[str, object]] = []
        for relation_id in ("R-1", "R-2", "R-3", "R-4"):
            status = statuses.get(relation_id, "found")
            evidence_results.append(self.evidence(relation_id, status=status))
            if status != "locator_error":
                judge_results.append(
                    self.judge(
                        relation_id,
                        decisions.get(relation_id, "pass"),
                        evidence_status=status,
                    )
                )
        return evidence_results, judge_results

    def test_quote_and_context_must_match_exact_submission(self) -> None:
        evidence = self.evidence("R-1")
        evidence["candidates"][0]["quote"] = "错"
        with self.assertRaisesRegex(RuntimeValidationError, "quote does not equal"):
            validate_evidence_result(evidence, self.submission)

    def test_none_requires_retry_or_full_text_review(self) -> None:
        evidence = self.evidence("R-1", status="none")
        evidence["attempts"] = 1
        with self.assertRaisesRegex(
            RuntimeValidationError, "at least two locator attempts"
        ):
            validate_evidence_result(evidence, self.submission)

    def test_judge_cannot_select_unknown_candidate(self) -> None:
        evidence = self.evidence("R-1")
        judge = self.judge("R-1", "pass")
        judge["selected_candidate_ids"] = ["C-unknown"]
        with self.assertRaisesRegex(RuntimeValidationError, "unknown candidate"):
            validate_judge_result(
                judge,
                evidence,
                self.book_card["cognitive_structures"][0]["relations"][0],
            )

    def test_weighted_relations_and_alternative_group_aggregate(self) -> None:
        evidence, judges = self.bundle(
            {"R-1": "pass", "R-2": "fail", "R-3": "fail", "R-4": "pass"}
        )
        result = score_adjudication_bundle(
            self.book_card, self.submission, "SUB-1", evidence, judges
        )
        validate_cognitive_aggregate(result)

        self.assertEqual(result["status"], "complete")
        self.assertTrue(
            math.isclose(
                result["metrics"]["cognitive_relation_coverage"],
                2 / 6,
                rel_tol=0,
                abs_tol=1e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                result["metrics"]["complete_core_path_rate"],
                1 / 3,
                rel_tol=0,
                abs_tol=1e-12,
            )
        )
        path_by_id = {item["unit_id"]: item for item in result["path_results"]}
        self.assertFalse(path_by_id["P-M"]["complete"])
        self.assertTrue(path_by_id["alternative_group:CS-1:G-1"]["complete"])

    def test_exhausted_none_can_be_a_semantic_fail(self) -> None:
        evidence, judges = self.bundle(
            {"R-1": "fail"},
            evidence_statuses={"R-1": "none"},
        )
        result = score_adjudication_bundle(
            self.book_card, self.submission, "SUB-1", evidence, judges
        )
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["relation_counts"]["fail"], 1)

    def test_locator_error_makes_trial_unscorable_not_zero(self) -> None:
        evidence, judges = self.bundle(
            {},
            evidence_statuses={"R-1": "locator_error"},
        )
        result = score_adjudication_bundle(
            self.book_card, self.submission, "SUB-1", evidence, judges
        )
        validate_cognitive_aggregate(result)
        self.assertEqual(result["status"], "unscorable")
        self.assertIsNone(result["metrics"]["cognitive_relation_coverage"])
        self.assertIsNone(result["metrics"]["complete_core_path_rate"])
        self.assertEqual(result["relation_counts"]["infrastructure_error"], 1)

    def test_abstain_or_review_conflict_makes_trial_unscorable(self) -> None:
        evidence, judges = self.bundle({"R-1": "abstain"})
        result = score_adjudication_bundle(
            self.book_card, self.submission, "SUB-1", evidence, judges
        )
        self.assertEqual(result["status"], "unscorable")

        evidence, judges = self.bundle({})
        judges[0]["review"] = {"status": "conflict", "reason": "fixture conflict"}
        result = score_adjudication_bundle(
            self.book_card, self.submission, "SUB-1", evidence, judges
        )
        self.assertEqual(result["status"], "unscorable")

    def test_alternative_group_members_must_have_equal_weight(self) -> None:
        card = copy.deepcopy(self.book_card)
        card["cognitive_structures"][0]["paths"][2]["weight"] = 2.0
        evidence, judges = self.bundle({})
        with self.assertRaisesRegex(
            RuntimeValidationError, "must have the same weight"
        ):
            score_adjudication_bundle(card, self.submission, "SUB-1", evidence, judges)


if __name__ == "__main__":
    unittest.main()
