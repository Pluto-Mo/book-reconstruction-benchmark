from __future__ import annotations

import copy
import json
import unittest

from compile_cognitive_criteria import (
    DEFAULT_CRITERION_SCHEMA,
    DEFAULT_JUDGE_PROMPT,
    DEFAULT_LOCATOR_PROMPT,
    REPO_ROOT,
    audit_criteria,
    compile_criteria,
)


class CognitiveCriteriaCompilationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.book_card = json.loads(
            (
                REPO_ROOT / "workbench/breakthrough-advertising/book_card.draft.json"
            ).read_text(encoding="utf-8")
        )
        cls.schema = json.loads(DEFAULT_CRITERION_SCHEMA.read_text(encoding="utf-8"))

    def test_development_card_compiles_to_sixty_narrow_criteria(self) -> None:
        criteria = compile_criteria(
            self.book_card, DEFAULT_LOCATOR_PROMPT, DEFAULT_JUDGE_PROMPT
        )
        self.assertEqual(len(criteria), 60)
        self.assertEqual(audit_criteria(criteria, self.book_card, self.schema), [])
        self.assertEqual(
            {criterion["criterion_id"] for criterion in criteria},
            {
                relation["id"]
                for structure in self.book_card["cognitive_structures"]
                for relation in structure["relations"]
            },
        )

    def test_leakage_audit_rejects_hidden_graph_weight(self) -> None:
        criterion = compile_criteria(
            self.book_card, DEFAULT_LOCATOR_PROMPT, DEFAULT_JUDGE_PROMPT
        )[0]
        leaked = copy.deepcopy(criterion)
        leaked["relation"]["weight"] = 1.0
        errors = audit_criteria([leaked], self.book_card, self.schema)
        self.assertTrue(any("forbidden keys leaked" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
