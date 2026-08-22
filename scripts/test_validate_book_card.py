from __future__ import annotations

import copy
import unittest

from validate_book_card import validate_cross_references


class AlternativePathValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = {
            "source_anchors": [],
            "cognitive_structures": [
                {
                    "id": "CS-1",
                    "nodes": [],
                    "relations": [
                        {"id": "R-1", "critical": False},
                        {"id": "R-2", "critical": False},
                    ],
                    "paths": [
                        {
                            "id": "P-1",
                            "relation_ids": ["R-1"],
                            "path_type": "alternative",
                            "alternative_group": "G-1",
                            "weight": 1.0,
                        },
                        {
                            "id": "P-2",
                            "relation_ids": ["R-2"],
                            "path_type": "alternative",
                            "alternative_group": "G-1",
                            "weight": 1.0,
                        },
                    ],
                }
            ],
            "genericity_traps": [],
            "compression": {"min_chars": 1, "max_chars": 2},
            "status": "draft",
        }

    def test_equivalent_alternative_paths_require_equal_weight(self) -> None:
        card = copy.deepcopy(self.card)
        card["cognitive_structures"][0]["paths"][1]["weight"] = 2.0
        errors = validate_cross_references(card)
        self.assertTrue(any("must have the same weight" in error for error in errors))

    def test_mandatory_path_cannot_carry_alternative_group(self) -> None:
        card = copy.deepcopy(self.card)
        first_path = card["cognitive_structures"][0]["paths"][0]
        first_path["path_type"] = "mandatory"
        errors = validate_cross_references(card)
        self.assertTrue(
            any(
                "mandatory path cannot set alternative_group" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
