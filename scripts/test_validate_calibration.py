#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest

from validate_calibration import (
    KNOWN_PROBES,
    validate_discourse_expected,
    validate_strict_content_gate_expectations,
)


class DiscourseExpectedValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.panel_edges = {"AE-001", "AE-002"}
        self.valid = {
            "expected_changed_edge_ids": [],
            "expected_stable_edge_selector": "all_2_PANEL-DEV-01_edges",
            "expected_changed_probes": [],
            "expected_stable_probes": sorted(KNOWN_PROBES),
            "expected_unfrozen_probes": [],
            "expected_metrics": {"authorial_edge_recovery": "2/2"},
        }

    def validate(self, expected: dict[str, object]) -> list[str]:
        errors: list[str] = []
        validate_discourse_expected("TEST", expected, self.panel_edges, errors)
        return errors

    def test_complete_tri_state_is_valid(self) -> None:
        self.assertEqual(self.validate(self.valid), [])

    def test_missing_probe_is_rejected(self) -> None:
        expected = copy.deepcopy(self.valid)
        expected["expected_stable_probes"].remove("closure")
        errors = self.validate(expected)
        self.assertTrue(any("classify every known probe" in error for error in errors))

    def test_duplicate_probe_is_rejected(self) -> None:
        expected = copy.deepcopy(self.valid)
        expected["expected_stable_probes"].append("closure")
        errors = self.validate(expected)
        self.assertTrue(any("duplicate probes" in error for error in errors))

    def test_exact_fraction_is_rejected_with_unfrozen_edge(self) -> None:
        expected = copy.deepcopy(self.valid)
        expected["expected_unfrozen_edge_ids"] = ["AE-001"]
        expected["expected_stable_edge_selector"] = "all_except:AE-001"
        errors = self.validate(expected)
        self.assertTrue(
            any("exact authorial_edge_recovery is invalid" in error for error in errors)
        )

    def test_failed_linked_relation_must_propagate_to_edge(self) -> None:
        errors: list[str] = []
        validate_strict_content_gate_expectations(
            {"CASE": {"expected_changed_relation_ids": ["R-1"]}},
            {
                "CASE": {
                    "expected_changed_edge_ids": [],
                    "expected_unfrozen_edge_ids": [],
                }
            },
            {"AE-001": {"R-1"}, "AE-002": {"R-2"}},
            errors,
        )
        self.assertTrue(any("AE-001" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
