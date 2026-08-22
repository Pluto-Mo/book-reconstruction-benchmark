from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from count_submission_chars import (
    COUNTER_VERSION,
    WHITE_SPACE_CODEPOINTS,
    build_result,
    count_text,
    evaluate_bounds,
)


SCRIPT = Path(__file__).with_name("count_submission_chars.py")


class CountTextTests(unittest.TestCase):
    def test_counts_codepoints_not_bytes_or_graphemes(self) -> None:
        self.assertEqual(
            count_text("中 A。\n"),
            {
                "raw_codepoints": 5,
                "whitespace_codepoints": 2,
                "nonwhitespace_codepoints": 3,
            },
        )
        self.assertEqual(count_text("e\u0301")["nonwhitespace_codepoints"], 2)

    def test_pinned_unicode_white_space_set_is_excluded(self) -> None:
        whitespace = "".join(chr(value) for value in sorted(WHITE_SPACE_CODEPOINTS))
        counts = count_text(whitespace)
        self.assertEqual(counts["raw_codepoints"], len(WHITE_SPACE_CODEPOINTS))
        self.assertEqual(counts["nonwhitespace_codepoints"], 0)

    def test_zero_width_space_is_not_excluded(self) -> None:
        self.assertEqual(count_text("\u200b")["nonwhitespace_codepoints"], 1)

    def test_bounds(self) -> None:
        self.assertIsNone(evaluate_bounds(10, None, None))
        self.assertTrue(evaluate_bounds(10, 10, 10))
        self.assertFalse(evaluate_bounds(9, 10, None))
        self.assertFalse(evaluate_bounds(11, None, 10))

    def test_result_records_auditable_policy(self) -> None:
        result = build_result(Path("submission.md"), "# 标题\n正文", None, 10)
        self.assertEqual(result["counter_version"], COUNTER_VERSION)
        self.assertEqual(result["scope"], "entire_submission_file")
        self.assertEqual(result["normalization"], "none")
        self.assertTrue(result["within_bounds"])


class CliTests(unittest.TestCase):
    def test_cli_returns_one_when_over_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submission.md"
            path.write_text("一二三", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(path),
                    "--max-chars",
                    "2",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn('"within_bounds": false', completed.stdout)

    def test_cli_returns_two_for_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submission.md"
            path.write_bytes(b"\xff")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("not valid UTF-8", completed.stderr)


if __name__ == "__main__":
    unittest.main()
