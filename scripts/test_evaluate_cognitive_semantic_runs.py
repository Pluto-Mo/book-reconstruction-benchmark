from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluate_cognitive_semantic_runs import (
    DEFAULT_BOOK_CARD,
    DEFAULT_CASES,
    DEFAULT_EXPECTED,
    compare_relation_outcomes,
    evaluate_runs,
)
from runtime_scoring import RuntimeValidationError


class SemanticRunComparisonTests(unittest.TestCase):
    def test_false_pass_false_fail_and_unresolved_are_separate(self) -> None:
        comparison = compare_relation_outcomes(
            {"R-1"},
            {
                "R-1": "pass",
                "R-2": "fail",
                "R-3": "unresolved",
                "R-4": "infrastructure_error",
            },
            {"R-1", "R-2", "R-3", "R-4"},
        )
        self.assertEqual(comparison["false_pass_relation_ids"], ["R-1"])
        self.assertEqual(comparison["false_fail_relation_ids"], ["R-2"])
        self.assertEqual(comparison["unresolved_relation_ids"], ["R-3", "R-4"])

    def test_unknown_selected_case_cannot_vacuously_pass(self) -> None:
        with (
            TemporaryDirectory() as temporary_directory,
            self.assertRaisesRegex(RuntimeValidationError, "unknown selected case IDs"),
        ):
            evaluate_runs(
                book_card_path=DEFAULT_BOOK_CARD,
                cases_path=DEFAULT_CASES,
                expected_path=DEFAULT_EXPECTED,
                runs_dir=Path(temporary_directory),
                selected_case_ids={"BA-CAL-DOES-NOT-EXIST"},
            )


if __name__ == "__main__":
    unittest.main()
