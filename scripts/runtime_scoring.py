# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

"""Deterministic cognitive-scoring runtime.

This module deliberately does not call an LLM. It validates already-produced
Evidence Locator and Relation Adjudicator records, verifies quoted spans against
the submitted text, and performs the graph aggregation frozen by the benchmark.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOK_CARD_SCHEMA = REPO_ROOT / "schemas/book-card.schema.json"
DEFAULT_EVIDENCE_SCHEMA = REPO_ROOT / "schemas/evidence-result.schema.json"
DEFAULT_JUDGE_SCHEMA = REPO_ROOT / "schemas/judge-result.schema.json"
DEFAULT_AGGREGATE_SCHEMA = REPO_ROOT / "schemas/cognitive-aggregate.schema.json"

RESOLVED_OUTCOMES = {"pass", "fail"}
UNRESOLVED_OUTCOMES = {"unresolved", "infrastructure_error"}
ALL_OUTCOMES = RESOLVED_OUTCOMES | UNRESOLVED_OUTCOMES


class RuntimeValidationError(ValueError):
    """Raised when runtime artifacts cannot be safely scored."""

    def __init__(self, errors: str | Sequence[str]):
        if isinstance(errors, str):
            normalized = [errors]
        else:
            normalized = [str(error) for error in errors]
        self.errors = normalized
        super().__init__("; ".join(normalized))


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeValidationError(f"file not found: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeValidationError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeValidationError(f"expected a JSON object in {path}")
    return value


def load_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise RuntimeValidationError(f"file not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise RuntimeValidationError(f"invalid UTF-8 {path}: {exc}") from exc

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{line_number}: record must be an object")
            continue
        records.append(record)
    if errors:
        raise RuntimeValidationError(errors)
    return records


def schema_validation_errors(
    instance: Any,
    schema: Mapping[str, Any],
    label: str,
) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    rendered: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{label}.{location}: {error.message}")
    return rendered


def _load_schema(
    schema: Mapping[str, Any] | None, default_path: Path
) -> Mapping[str, Any]:
    return schema if schema is not None else load_json_object(default_path)


def validate_evidence_result(
    evidence: Mapping[str, Any],
    submission_text: str,
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Mapping[str, Any]]:
    """Validate one locator result and return its candidates by ID.

    Character offsets are Python/Unicode code-point offsets into the exact UTF-8
    decoded submission. Optional contexts, when present, must be the immediately
    adjacent literal text.
    """

    evidence_schema = _load_schema(schema, DEFAULT_EVIDENCE_SCHEMA)
    label = f"evidence {evidence.get('evidence_result_id', '<missing-id>')}"
    errors = schema_validation_errors(evidence, evidence_schema, label)
    if errors:
        raise RuntimeValidationError(errors)

    if evidence["status"] == "none" and evidence["attempts"] < 2:
        errors.append(
            f"{label}: status 'none' requires at least two locator attempts "
            "(retry or frozen full-text review)"
        )

    candidates_by_id: dict[str, Mapping[str, Any]] = {}
    for index, candidate in enumerate(evidence["candidates"]):
        candidate_label = f"{label}.candidates[{index}]"
        candidate_id = candidate["candidate_id"]
        if candidate_id in candidates_by_id:
            errors.append(f"{candidate_label}: duplicate candidate_id {candidate_id!r}")
            continue
        candidates_by_id[candidate_id] = candidate

        start = candidate["start_char"]
        end = candidate["end_char"]
        if start >= end:
            errors.append(
                f"{candidate_label}: start_char must be smaller than end_char"
            )
            continue
        if end > len(submission_text):
            errors.append(
                f"{candidate_label}: end_char {end} exceeds submission length "
                f"{len(submission_text)}"
            )
            continue

        actual_quote = submission_text[start:end]
        if candidate["quote"] != actual_quote:
            errors.append(
                f"{candidate_label}: quote does not equal submission[{start}:{end}]"
            )

        if "context_before" in candidate:
            context_before = candidate["context_before"]
            actual_before = submission_text[start - len(context_before) : start]
            if start < len(context_before) or context_before != actual_before:
                errors.append(
                    f"{candidate_label}: context_before is not the immediately adjacent text"
                )

        if "context_after" in candidate:
            context_after = candidate["context_after"]
            actual_after = submission_text[end : end + len(context_after)]
            if context_after != actual_after:
                errors.append(
                    f"{candidate_label}: context_after is not the immediately adjacent text"
                )

    if errors:
        raise RuntimeValidationError(errors)
    return candidates_by_id


def validate_judge_result(
    judge: Mapping[str, Any],
    evidence: Mapping[str, Any],
    criterion: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> None:
    """Validate one narrow relation judgment and its cross-artifact links."""

    judge_schema = _load_schema(schema, DEFAULT_JUDGE_SCHEMA)
    label = f"judge {judge.get('criterion_id', '<missing-criterion>')}"
    errors = schema_validation_errors(judge, judge_schema, label)
    if errors:
        raise RuntimeValidationError(errors)

    for field in ("book_id", "submission_id", "criterion_id", "evidence_result_id"):
        evidence_field = (
            "evidence_result_id" if field == "evidence_result_id" else field
        )
        if judge[field] != evidence[evidence_field]:
            errors.append(
                f"{label}: {field} {judge[field]!r} does not match evidence "
                f"{evidence[evidence_field]!r}"
            )

    if judge["criterion_id"] != criterion.get("id"):
        errors.append(
            f"{label}: criterion_id does not match relation {criterion.get('id')!r}"
        )

    candidate_ids = {candidate["candidate_id"] for candidate in evidence["candidates"]}
    selected_ids = set(judge["selected_candidate_ids"])
    unknown_selected = selected_ids - candidate_ids
    if unknown_selected:
        errors.append(
            f"{label}: selected unknown candidate IDs {sorted(unknown_selected)!r}"
        )

    required_facets = set(criterion.get("required_facets", []))
    missing_facets = set(judge["missing_facets"])
    unknown_facets = missing_facets - required_facets
    if unknown_facets:
        errors.append(
            f"{label}: missing_facets contains facets not required by the relation: "
            f"{sorted(unknown_facets)!r}"
        )

    if evidence["status"] == "locator_error":
        errors.append(f"{label}: locator_error must not receive a semantic judgment")
    elif evidence["status"] == "none":
        if judge["decision"] != "fail":
            errors.append(
                f"{label}: exhausted 'none' evidence must be recorded as fail"
            )
        if selected_ids:
            errors.append(f"{label}: 'none' evidence cannot select candidates")
        if judge["support_found"] or judge["contradiction_found"]:
            errors.append(
                f"{label}: 'none' evidence cannot claim support or contradiction"
            )
        if missing_facets != required_facets:
            errors.append(
                f"{label}: 'none' evidence must mark every required facet as missing"
            )

    if judge["decision"] == "fail":
        machine_readable_failure = (
            not judge["support_found"]
            or judge["contradiction_found"]
            or bool(judge["missing_facets"])
        )
        if not machine_readable_failure:
            errors.append(
                f"{label}: fail decision has no machine-readable failure reason"
            )

    if (judge["support_found"] or judge["contradiction_found"]) and not selected_ids:
        errors.append(
            f"{label}: support or contradiction claims require selected evidence"
        )

    if errors:
        raise RuntimeValidationError(errors)


def _index_book_card(
    book_card: Mapping[str, Any],
) -> tuple[
    dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]], list[Mapping[str, Any]]
]:
    errors: list[str] = []
    structures = book_card.get("cognitive_structures")
    if not isinstance(structures, list) or not structures:
        raise RuntimeValidationError("book card must contain cognitive_structures")

    relation_index: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for structure in structures:
        structure_id = structure.get("id", "<missing-structure-id>")
        structure_weight = structure.get("weight")
        if (
            not isinstance(structure_weight, (int, float))
            or isinstance(structure_weight, bool)
            or structure_weight <= 0
        ):
            errors.append(f"structure {structure_id}: weight must be positive")

        relations = structure.get("relations")
        if not isinstance(relations, list) or not relations:
            errors.append(
                f"structure {structure_id}: relations must be a non-empty array"
            )
            relations = []
        local_relation_ids: set[str] = set()
        for relation in relations:
            relation_id = relation.get("id")
            if not isinstance(relation_id, str) or not relation_id:
                errors.append(f"structure {structure_id}: relation has no valid id")
                continue
            if relation_id in relation_index:
                errors.append(f"book card: duplicate relation id {relation_id!r}")
            relation_index[relation_id] = (structure, relation)
            local_relation_ids.add(relation_id)
            relation_weight = relation.get("weight")
            if (
                not isinstance(relation_weight, (int, float))
                or isinstance(relation_weight, bool)
                or relation_weight <= 0
            ):
                errors.append(f"relation {relation_id}: weight must be positive")

        paths = structure.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"structure {structure_id}: paths must be a non-empty array")
            paths = []
        alternative_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for path in paths:
            path_id = path.get("id", "<missing-path-id>")
            path_weight = path.get("weight")
            if (
                not isinstance(path_weight, (int, float))
                or isinstance(path_weight, bool)
                or path_weight <= 0
            ):
                errors.append(f"path {path_id}: weight must be positive")
            unknown_relations = set(path.get("relation_ids", [])) - local_relation_ids
            if unknown_relations:
                errors.append(
                    f"path {path_id}: references relations outside structure "
                    f"{sorted(unknown_relations)!r}"
                )
            if path.get("path_type") == "mandatory":
                if "alternative_group" in path:
                    errors.append(
                        f"path {path_id}: mandatory path cannot set alternative_group"
                    )
            elif path.get("path_type") == "alternative":
                group = path.get("alternative_group")
                if not isinstance(group, str) or not group:
                    errors.append(f"path {path_id}: alternative_group is required")
                else:
                    alternative_groups[group].append(path)
            else:
                errors.append(
                    f"path {path_id}: invalid path_type {path.get('path_type')!r}"
                )

        for group, paths in alternative_groups.items():
            if len(paths) < 2:
                errors.append(
                    f"structure {structure_id}: alternative group {group!r} needs at least two paths"
                )
                continue
            weights = [float(path["weight"]) for path in paths]
            if not all(
                math.isclose(weight, weights[0], rel_tol=0.0, abs_tol=1e-12)
                for weight in weights[1:]
            ):
                errors.append(
                    f"structure {structure_id}: equivalent paths in alternative group "
                    f"{group!r} must have the same weight"
                )

    if errors:
        raise RuntimeValidationError(errors)
    return relation_index, structures


def _judge_outcome(judge: Mapping[str, Any]) -> str:
    review_status = judge.get("review", {}).get("status", "not_run")
    if review_status in {"rejected", "conflict"}:
        return "unresolved"
    if judge["decision"] == "abstain":
        return "unresolved"
    return str(judge["decision"])


def score_adjudication_bundle(
    book_card: Mapping[str, Any],
    submission_text: str,
    submission_id: str,
    evidence_results: Sequence[Mapping[str, Any]],
    judge_results: Sequence[Mapping[str, Any]],
    *,
    evidence_schema: Mapping[str, Any] | None = None,
    judge_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a complete relation-level bundle and aggregate it."""

    relation_index, _ = _index_book_card(book_card)
    book_id = book_card.get("book_id")
    if not isinstance(book_id, str) or not book_id:
        raise RuntimeValidationError("book card must have a non-empty book_id")
    if not submission_id:
        raise RuntimeValidationError("submission_id must be non-empty")

    errors: list[str] = []
    evidence_by_criterion: dict[str, Mapping[str, Any]] = {}
    seen_evidence_ids: set[str] = set()
    invalid_evidence_criteria: set[str] = set()

    for evidence in evidence_results:
        criterion_id = evidence.get("criterion_id")
        evidence_id = evidence.get("evidence_result_id")
        if criterion_id in evidence_by_criterion:
            errors.append(f"duplicate evidence for criterion {criterion_id!r}")
            continue
        if evidence_id in seen_evidence_ids:
            errors.append(f"duplicate evidence_result_id {evidence_id!r}")
        if isinstance(evidence_id, str):
            seen_evidence_ids.add(evidence_id)
        if criterion_id not in relation_index:
            errors.append(f"evidence references unknown criterion {criterion_id!r}")
            continue
        evidence_by_criterion[str(criterion_id)] = evidence
        if evidence.get("book_id") != book_id:
            errors.append(f"evidence {evidence_id!r}: book_id mismatch")
        if evidence.get("submission_id") != submission_id:
            errors.append(f"evidence {evidence_id!r}: submission_id mismatch")
        try:
            validate_evidence_result(evidence, submission_text, evidence_schema)
        except RuntimeValidationError as exc:
            errors.extend(exc.errors)
            invalid_evidence_criteria.add(str(criterion_id))

    judge_by_criterion: dict[str, Mapping[str, Any]] = {}
    for judge in judge_results:
        criterion_id = judge.get("criterion_id")
        if criterion_id in judge_by_criterion:
            errors.append(f"duplicate judge result for criterion {criterion_id!r}")
            continue
        if criterion_id not in relation_index:
            errors.append(f"judge references unknown criterion {criterion_id!r}")
            continue
        judge_by_criterion[str(criterion_id)] = judge

    outcomes: dict[str, str] = {}
    for criterion_id, (_, relation) in relation_index.items():
        evidence = evidence_by_criterion.get(criterion_id)
        judge = judge_by_criterion.get(criterion_id)
        if evidence is None:
            errors.append(f"missing evidence result for criterion {criterion_id}")
            continue
        if criterion_id in invalid_evidence_criteria:
            continue
        if evidence.get("status") == "locator_error":
            if judge is not None:
                errors.append(
                    f"criterion {criterion_id}: locator_error must not have a judge result"
                )
            outcomes[criterion_id] = "infrastructure_error"
            continue
        if judge is None:
            errors.append(f"missing judge result for criterion {criterion_id}")
            continue
        try:
            validate_judge_result(judge, evidence, relation, judge_schema)
        except RuntimeValidationError as exc:
            errors.extend(exc.errors)
            continue
        outcomes[criterion_id] = _judge_outcome(judge)

    if errors:
        raise RuntimeValidationError(errors)
    return aggregate_cognitive(book_card, outcomes, submission_id)


def _concrete_path_state(
    path: Mapping[str, Any], relation_outcomes: Mapping[str, str]
) -> tuple[bool | None, list[str], list[str]]:
    blocking = sorted(
        relation_id
        for relation_id in path["relation_ids"]
        if relation_outcomes[relation_id] == "fail"
    )
    unresolved = sorted(
        relation_id
        for relation_id in path["relation_ids"]
        if relation_outcomes[relation_id] in UNRESOLVED_OUTCOMES
    )
    if blocking:
        return False, blocking, unresolved
    if unresolved:
        return None, blocking, unresolved
    return True, blocking, unresolved


def aggregate_cognitive(
    book_card: Mapping[str, Any],
    relation_outcomes: Mapping[str, str],
    submission_id: str,
) -> dict[str, Any]:
    """Aggregate validated relation outcomes without inventing a scalar reward."""

    relation_index, structures = _index_book_card(book_card)
    expected_ids = set(relation_index)
    actual_ids = set(relation_outcomes)
    errors: list[str] = []
    if missing := expected_ids - actual_ids:
        errors.append(f"missing relation outcomes {sorted(missing)!r}")
    if extra := actual_ids - expected_ids:
        errors.append(f"unknown relation outcomes {sorted(extra)!r}")
    for relation_id in sorted(expected_ids & actual_ids):
        outcome = relation_outcomes[relation_id]
        if outcome not in ALL_OUTCOMES:
            errors.append(f"relation {relation_id}: invalid outcome {outcome!r}")
    if errors:
        raise RuntimeValidationError(errors)

    relation_results: list[dict[str, Any]] = []
    structure_results: list[dict[str, Any]] = []
    path_results: list[dict[str, Any]] = []
    global_relation_numerator = 0.0
    global_relation_denominator = 0.0
    global_path_numerator = 0.0
    global_path_denominator = 0.0

    for structure in structures:
        structure_id = structure["id"]
        structure_weight = float(structure["weight"])
        local_numerator = 0.0
        local_denominator = 0.0
        local_unresolved = False

        for relation in structure["relations"]:
            relation_id = relation["id"]
            outcome = relation_outcomes[relation_id]
            relation_weight = float(relation["weight"])
            relation_results.append(
                {
                    "relation_id": relation_id,
                    "structure_id": structure_id,
                    "outcome": outcome,
                    "weight": relation_weight,
                }
            )
            local_denominator += relation_weight
            global_relation_denominator += structure_weight * relation_weight
            if outcome == "pass":
                local_numerator += relation_weight
                global_relation_numerator += structure_weight * relation_weight
            elif outcome in UNRESOLVED_OUTCOMES:
                local_unresolved = True

        concrete_path_states: dict[str, tuple[bool | None, list[str], list[str]]] = {}
        alternative_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        requirement_results: list[dict[str, Any]] = []

        for path in structure["paths"]:
            concrete_path_states[path["id"]] = _concrete_path_state(
                path, relation_outcomes
            )
            if path["path_type"] == "mandatory":
                state, blocking, unresolved_ids = concrete_path_states[path["id"]]
                requirement_results.append(
                    {
                        "unit_id": path["id"],
                        "structure_id": structure_id,
                        "unit_type": "mandatory",
                        "member_path_ids": [path["id"]],
                        "weight": float(path["weight"]),
                        "complete": state,
                        "blocking_relation_ids": blocking,
                        "unresolved_relation_ids": unresolved_ids,
                    }
                )
            else:
                alternative_groups[path["alternative_group"]].append(path)

        for group, paths in alternative_groups.items():
            states = [concrete_path_states[path["id"]][0] for path in paths]
            if any(state is True for state in states):
                group_state: bool | None = True
            elif all(state is False for state in states):
                group_state = False
            else:
                group_state = None
            blocking = sorted(
                {
                    relation_id
                    for path in paths
                    for relation_id in concrete_path_states[path["id"]][1]
                }
            )
            unresolved_ids = sorted(
                {
                    relation_id
                    for path in paths
                    for relation_id in concrete_path_states[path["id"]][2]
                }
            )
            requirement_results.append(
                {
                    "unit_id": f"alternative_group:{structure_id}:{group}",
                    "structure_id": structure_id,
                    "unit_type": "alternative_group",
                    "member_path_ids": [path["id"] for path in paths],
                    "weight": float(paths[0]["weight"]),
                    "complete": group_state,
                    "blocking_relation_ids": blocking,
                    "unresolved_relation_ids": unresolved_ids,
                }
            )

        local_path_numerator = 0.0
        local_path_denominator = 0.0
        for requirement in requirement_results:
            path_results.append(requirement)
            weight = requirement["weight"]
            local_path_denominator += weight
            global_path_denominator += structure_weight * weight
            if requirement["complete"] is True:
                local_path_numerator += weight
                global_path_numerator += structure_weight * weight

        requirement_states = [item["complete"] for item in requirement_results]
        if any(state is False for state in requirement_states):
            structure_path_complete: bool | None = False
        elif any(state is None for state in requirement_states):
            structure_path_complete = None
        else:
            structure_path_complete = True

        structure_results.append(
            {
                "structure_id": structure_id,
                "weight": structure_weight,
                "relation_coverage": (
                    None if local_unresolved else local_numerator / local_denominator
                ),
                "passed_relation_weight": local_numerator,
                "total_relation_weight": local_denominator,
                "path_requirements_completed": sum(
                    state is True for state in requirement_states
                ),
                "path_requirements_total": len(requirement_states),
                "path_requirement_rate": (
                    None
                    if any(state is None for state in requirement_states)
                    else local_path_numerator / local_path_denominator
                ),
                "path_complete": structure_path_complete,
            }
        )

    outcome_counts = Counter(relation_outcomes.values())
    unresolved = bool(UNRESOLVED_OUTCOMES & set(outcome_counts))
    status = "unscorable" if unresolved else "complete"
    metrics = {
        "cognitive_relation_coverage": (
            None
            if unresolved
            else global_relation_numerator / global_relation_denominator
        ),
        "complete_core_path_rate": (
            None if unresolved else global_path_numerator / global_path_denominator
        ),
    }

    return {
        "schema_version": "1.0",
        "status": status,
        "book_id": book_card["book_id"],
        "submission_id": submission_id,
        "relation_counts": {
            "pass": outcome_counts["pass"],
            "fail": outcome_counts["fail"],
            "unresolved": outcome_counts["unresolved"],
            "infrastructure_error": outcome_counts["infrastructure_error"],
            "total": len(relation_results),
        },
        "relation_results": relation_results,
        "structure_results": structure_results,
        "path_results": path_results,
        "metrics": metrics,
    }


def validate_cognitive_aggregate(
    aggregate: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> None:
    aggregate_schema = _load_schema(schema, DEFAULT_AGGREGATE_SCHEMA)
    errors = schema_validation_errors(aggregate, aggregate_schema, "aggregate")
    if errors:
        raise RuntimeValidationError(errors)


def _write_or_print(result: Mapping[str, Any], output: Path | None) -> None:
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Cognitive aggregate written: {output}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Evidence Locator / Relation Adjudicator JSONL and compute "
            "deterministic cognitive metrics."
        )
    )
    parser.add_argument("--book-card", type=Path, required=True)
    parser.add_argument(
        "--book-card-schema", type=Path, default=DEFAULT_BOOK_CARD_SCHEMA
    )
    parser.add_argument(
        "--allow-draft-card",
        action="store_true",
        help="Development only: permit a Book Card whose status is draft.",
    )
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--evidence-results", type=Path, required=True)
    parser.add_argument("--judge-results", type=Path, required=True)
    parser.add_argument("--evidence-schema", type=Path, default=DEFAULT_EVIDENCE_SCHEMA)
    parser.add_argument("--judge-schema", type=Path, default=DEFAULT_JUDGE_SCHEMA)
    parser.add_argument(
        "--aggregate-schema", type=Path, default=DEFAULT_AGGREGATE_SCHEMA
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        book_card = load_json_object(args.book_card)
        book_card_errors = schema_validation_errors(
            book_card,
            load_json_object(args.book_card_schema),
            "book_card",
        )
        if book_card_errors:
            raise RuntimeValidationError(book_card_errors)
        if book_card.get("status") == "draft" and not args.allow_draft_card:
            raise RuntimeValidationError(
                "draft Book Card is not scoreable without --allow-draft-card"
            )
        submission_text = args.submission.read_text(encoding="utf-8")
        evidence_results = load_jsonl_objects(args.evidence_results)
        judge_results = load_jsonl_objects(args.judge_results)
        result = score_adjudication_bundle(
            book_card,
            submission_text,
            args.submission_id,
            evidence_results,
            judge_results,
            evidence_schema=load_json_object(args.evidence_schema),
            judge_schema=load_json_object(args.judge_schema),
        )
        validate_cognitive_aggregate(result, load_json_object(args.aggregate_schema))
        _write_or_print(result, args.output)
    except (OSError, UnicodeDecodeError, RuntimeValidationError) as exc:
        print("Cognitive runtime failed:", file=sys.stderr)
        if isinstance(exc, RuntimeValidationError):
            for error in exc.errors:
                print(f"- {error}", file=sys.stderr)
        else:
            print(f"- {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
