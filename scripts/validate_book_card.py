# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PLACEHOLDER_MARKERS = ("replace-me", "Replace Me")


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


def validate_cross_references(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    anchors = card.get("source_anchors", [])
    anchor_ids = [item.get("id", "") for item in anchors]
    add_duplicate_errors(errors, anchor_ids, "source anchor", "book")
    anchor_set = set(anchor_ids)

    structure_ids = [
        structure.get("id", "") for structure in card.get("cognitive_structures", [])
    ]
    add_duplicate_errors(errors, structure_ids, "cognitive structure", "book")

    all_relation_ids: set[str] = set()

    for structure in card.get("cognitive_structures", []):
        structure_id = structure.get("id", "<missing-structure-id>")
        scope = f"structure {structure_id}"

        nodes = structure.get("nodes", [])
        node_ids = [node.get("id", "") for node in nodes]
        add_duplicate_errors(errors, node_ids, "node", scope)
        node_set = set(node_ids)

        relations = structure.get("relations", [])
        relation_ids = [relation.get("id", "") for relation in relations]
        add_duplicate_errors(errors, relation_ids, "relation", scope)
        relation_set = set(relation_ids)

        overlap = all_relation_ids.intersection(relation_set)
        for relation_id in sorted(overlap):
            errors.append(f"book: relation id {relation_id!r} is reused across structures")
        all_relation_ids.update(relation_set)

        paths = structure.get("paths", [])
        path_ids = [path.get("id", "") for path in paths]
        add_duplicate_errors(errors, path_ids, "path", scope)

        relation_membership: dict[str, int] = {relation_id: 0 for relation_id in relation_set}
        node_membership: dict[str, int] = {node_id: 0 for node_id in node_set}

        for node in nodes:
            node_id = node.get("id", "<missing-node-id>")
            for anchor_id in node.get("source_anchor_ids", []):
                if anchor_id not in anchor_set:
                    errors.append(
                        f"{scope}, node {node_id}: unknown source_anchor_id {anchor_id!r}"
                    )

            role = node.get("role")
            profile = node.get("case_profile")
            if role in {"case", "counterexample"} and not profile:
                errors.append(f"{scope}, node {node_id}: case_profile is required")
            if profile:
                function = profile.get("function")
                preservation = profile.get("preservation")
                if function == "constitutive" and preservation != "required":
                    errors.append(
                        f"{scope}, node {node_id}: constitutive cases must use "
                        "preservation='required'"
                    )

        for relation in relations:
            relation_id = relation.get("id", "<missing-relation-id>")

            for node_id in relation.get("source_node_ids", []):
                if node_id not in node_set:
                    errors.append(
                        f"{scope}, relation {relation_id}: unknown source node {node_id!r}"
                    )
                else:
                    node_membership[node_id] += 1

            for node_id in relation.get("target_node_ids", []):
                if node_id not in node_set:
                    errors.append(
                        f"{scope}, relation {relation_id}: unknown target node {node_id!r}"
                    )
                else:
                    node_membership[node_id] += 1

            for anchor_id in relation.get("source_anchor_ids", []):
                if anchor_id not in anchor_set:
                    errors.append(
                        f"{scope}, relation {relation_id}: unknown source_anchor_id "
                        f"{anchor_id!r}"
                    )

        critical_relations = {
            relation.get("id", "")
            for relation in relations
            if relation.get("critical") is True
        }

        alternative_groups: dict[str, int] = {}
        for path in paths:
            path_id = path.get("id", "<missing-path-id>")
            relation_ids_in_path = path.get("relation_ids", [])

            for relation_id in relation_ids_in_path:
                if relation_id not in relation_set:
                    errors.append(
                        f"{scope}, path {path_id}: unknown relation id {relation_id!r}"
                    )
                else:
                    relation_membership[relation_id] += 1

            if path.get("path_type") == "alternative":
                group = path.get("alternative_group")
                if not group:
                    errors.append(
                        f"{scope}, path {path_id}: alternative_group is required"
                    )
                else:
                    alternative_groups[group] = alternative_groups.get(group, 0) + 1

        for group, count in alternative_groups.items():
            if count < 2:
                errors.append(
                    f"{scope}: alternative_group {group!r} has only one path; "
                    "use mandatory or add a real alternative"
                )

        for relation_id in sorted(critical_relations):
            if relation_membership.get(relation_id, 0) == 0:
                errors.append(
                    f"{scope}: critical relation {relation_id!r} is not in any path"
                )

        for node in nodes:
            node_id = node.get("id", "")
            if node.get("essential") is True and node_membership.get(node_id, 0) == 0:
                errors.append(
                    f"{scope}: essential node {node_id!r} does not participate in a relation"
                )

    for trap in card.get("genericity_traps", []):
        trap_id = trap.get("id", "<missing-trap-id>")
        for relation_id in trap.get("related_relation_ids", []):
            if relation_id not in all_relation_ids:
                errors.append(
                    f"genericity trap {trap_id}: unknown relation id {relation_id!r}"
                )

    compression = card.get("compression", {})
    min_chars = compression.get("min_chars")
    max_chars = compression.get("max_chars")
    if isinstance(min_chars, int) and isinstance(max_chars, int):
        if min_chars > max_chars:
            errors.append("compression.min_chars must be <= compression.max_chars")

    if card.get("status") == "frozen":
        provenance = card.get("provenance", {})
        if not provenance.get("reviewed_by"):
            errors.append("frozen card must have at least one human reviewer")
        serialized = json.dumps(card, ensure_ascii=False)
        for marker in PLACEHOLDER_MARKERS:
            if marker in serialized:
                errors.append(
                    f"frozen card still contains placeholder marker {marker!r}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a cognitive-structure Book Card."
    )
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()

    card = load_json(args.card)
    schema = load_json(args.schema)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(validator.iter_errors(card), key=lambda error: list(error.path))

    errors: list[str] = []
    for error in schema_errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")

    errors.extend(validate_cross_references(card))

    if errors:
        print("Book Card validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Book Card is valid: {args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
