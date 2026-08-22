from __future__ import annotations

import unittest

from replay_calibration import run_replay


class CalibrationReplayTests(unittest.TestCase):
    def test_all_development_cases_match_deterministic_aggregation(self) -> None:
        result = run_replay()
        self.assertEqual(result["case_count"], 19)
        self.assertEqual(result["passed_count"], 19)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["semantic_judge_exercised"])


if __name__ == "__main__":
    unittest.main()
