# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PLACEHOLDER_MARKERS = ("replace-me", "Replace Me")
ZERO_SHA256 = "0" * 64


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return value


def add_duplicate_errors(
    errors: list[str], values: list[str], label: str, scope: str
) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            errors.append(f"{scope}: duplicate {label} id {value!r}")
        seen.add(value)


def collect_book_card_ids(
    book_card: dict[str, Any],
) -> tuple[set[str], set[str]]:
    anchor_ids = {
        anchor.get("id", "") for anchor in book_card.get("source_anchors", [])
    }
    relation_ids: set[str] = set()
    for structure in book_card.get("cognitive_structures", []):
        for relation in structure.get("relations", []):
            relation_ids.add(relation.get("id", ""))
    return anchor_ids, relation_ids


def validate_cross_references(
    card: dict[str, Any],
    book_card: dict[str, Any],
    book_card_path: Path,
) -> list[str]:
    errors: list[str] = []

    edge_ids = [edge.get("id", "") for edge in card.get("authorial_edges", [])]
    add_duplicate_errors(errors, edge_ids, "authorial edge", "discourse card")
    edge_set = set(edge_ids)

    panel_ids = [
        panel.get("id", "")
        for panel in card.get("sampling_plan", {}).get("panels", [])
    ]
    add_duplicate_errors(errors, panel_ids, "panel", "sampling plan")

    perturbation_ids = [
        item.get("id", "") for item in card.get("calibration_perturbations", [])
    ]
    add_duplicate_errors(
        errors, perturbation_ids, "calibration perturbation", "discourse card"
    )

    source = card.get("source", {})
    book_source = book_card.get("source", {})

    if card.get("book_id") != book_card.get("book_id"):
        errors.append("book_id must match the linked Book Card")

    if source.get("document_sha256") != book_source.get("document_sha256"):
        errors.append("source.document_sha256 must match the linked Book Card")

    expected_book_card_sha = source.get("book_card_sha256")
    if isinstance(expected_book_card_sha, str) and expected_book_card_sha != ZERO_SHA256:
        actual_sha = hashlib.sha256(book_card_path.read_bytes()).hexdigest()
        if expected_book_card_sha.lower() != actual_sha.lower():
            errors.append(
                "source.book_card_sha256 does not match the linked Book Card file"
            )

    anchor_ids, relation_ids = collect_book_card_ids(book_card)

    edge_by_id = {
        edge.get("id", ""): edge for edge in card.get("authorial_edges", [])
    }
    for edge_id, edge in edge_by_id.items():
        scope = f"authorial edge {edge_id or '<missing-edge-id>'}"

        for field in ("source_a_anchor_ids", "source_b_anchor_ids"):
            for anchor_id in edge.get(field, []):
                if anchor_id not in anchor_ids:
                    errors.append(f"{scope}: unknown source anchor {anchor_id!r}")

        for relation_id in edge.get("linked_cognitive_relation_ids", []):
            if relation_id not in relation_ids:
                errors.append(
                    f"{scope}: unknown linked cognitive relation {relation_id!r}"
                )

    sampling = card.get("sampling_plan", {})
    required_strata = set(sampling.get("required_strata", []))
    rollout_membership: dict[int, str] = {}
    covered_edges: set[str] = set()

    for panel in sampling.get("panels", []):
        panel_id = panel.get("id", "<missing-panel-id>")
        panel_edges = panel.get("edge_ids", [])
        panel_strata: set[str] = set()

        for edge_id in panel_edges:
            edge = edge_by_id.get(edge_id)
            if edge is None:
                errors.append(f"panel {panel_id}: unknown edge id {edge_id!r}")
                continue
            covered_edges.add(edge_id)
            panel_strata.add(edge.get("stratum", ""))

        missing_strata = required_strata - panel_strata
        if missing_strata:
            errors.append(
                f"panel {panel_id}: missing required strata {sorted(missing_strata)!r}"
            )

        for rollout_index in panel.get("rollout_indices", []):
            previous = rollout_membership.get(rollout_index)
            if previous is not None:
                errors.append(
                    f"rollout index {rollout_index} appears in both "
                    f"{previous!r} and {panel_id!r}"
                )
            else:
                rollout_membership[rollout_index] = panel_id

    critical_edges = {
        edge.get("id", "")
        for edge in card.get("authorial_edges", [])
        if edge.get("critical") is True
    }
    for edge_id in sorted(critical_edges - covered_edges):
        errors.append(f"critical authorial edge {edge_id!r} is not in any panel")

    editorial_weights = card.get("editorial_probe_config", {}).get("weights", {})
    if editorial_weights:
        total = sum(
            value
            for value in editorial_weights.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            errors.append(
                f"editorial_probe_config.weights must sum to 1.0, got {total}"
            )

    dimension_weights = card.get("dimension_weights", {})
    if dimension_weights:
        total = sum(
            value
            for value in dimension_weights.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            errors.append(f"dimension_weights must sum to 1.0, got {total}")

    if card.get("status") == "frozen":
        provenance = card.get("provenance", {})
        if not provenance.get("reviewed_by"):
            errors.append("frozen discourse card must have a human reviewer")

        serialized = json.dumps(card, ensure_ascii=False)
        for marker in PLACEHOLDER_MARKERS:
            if marker in serialized:
                errors.append(
                    f"frozen discourse card still contains placeholder marker "
                    f"{marker!r}"
                )

        if source.get("book_card_sha256") == ZERO_SHA256:
            errors.append("frozen discourse card cannot use the zero Book Card SHA-256")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a discourse-reconstruction card and its Book Card links."
    )
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--book-card", type=Path, required=True)
    args = parser.parse_args()

    card = load_json(args.card)
    schema = load_json(args.schema)
    book_card = load_json(args.book_card)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(
        validator.iter_errors(card), key=lambda error: list(error.path)
    )

    errors: list[str] = []
    for error in schema_errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")

    errors.extend(validate_cross_references(card, book_card, args.book_card))

    if errors:
        print("Discourse Card validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Discourse Card is valid: {args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
