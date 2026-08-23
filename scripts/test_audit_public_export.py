from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_public_export import content_findings, path_findings


class AuditPublicExportTests(unittest.TestCase):
    def test_rejects_private_source_and_local_results(self) -> None:
        root = Path("/repo")
        self.assertIn(
            "private book source",
            path_findings(root / "tasks/book/environment/source/book.md", root),
        )
        self.assertIn(
            "local result output",
            path_findings(root / "results/model-output.json", root),
        )
        self.assertEqual(path_findings(root / "results/README.md", root), [])

    def test_accepts_placeholder_and_rejects_literal_api_key(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            placeholder = Path(temporary_directory) / "placeholder.json"
            placeholder.write_text(
                json.dumps({"apiKey": "${QWEN_BENCHMARK_API_KEY}"}),
                encoding="utf-8",
            )
            literal = Path(temporary_directory) / "literal.json"
            literal.write_text(json.dumps({"apiKey": "not-a-placeholder"}), encoding="utf-8")
            self.assertEqual(content_findings(placeholder), [])
            self.assertTrue(
                any("literal API key" in finding for finding in content_findings(literal))
            )


if __name__ == "__main__":
    unittest.main()
