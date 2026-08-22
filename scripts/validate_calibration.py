#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from count_submission_chars import COUNTER_VERSION, count_text, evaluate_bounds
from materialize_calibration_variants import MutationError, build_variant


DIMENSIONS = ("cognitive", "discourse")
KNOWN_PROBES = {
    "local_progression",
    "global_order",
    "spine_connectivity",
    "example_integration",
    "closure",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"file not found: {path}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {path}: {exc}")
    return {}


def load_jsonl(path: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        errors.append(f"file not found: {path}")
        return records
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8 {path}: {exc}")
        return records

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
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{path}:{line_number}: case_id must be a non-empty string")
            continue
        if case_id in records:
            errors.append(f"{path}:{line_number}: duplicate case_id {case_id}")
            continue
        record["__line_number"] = line_number
        records[case_id] = record
    return records


def collect_ids(value: Any, prefixes: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        item_id = value.get("id")
        if isinstance(item_id, str) and item_id.startswith(prefixes):
            result.add(item_id)
        for item in value.values():
            result.update(collect_ids(item, prefixes))
    elif isinstance(value, list):
        for item in value:
            result.update(collect_ids(item, prefixes))
    return result


def find_object_by_id(value: Any, target_id: str) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if value.get("id") == target_id:
            return value
        for item in value.values():
            match = find_object_by_id(item, target_id)
            if match is not None:
                return match
    elif isinstance(value, list):
        for item in value:
            match = find_object_by_id(item, target_id)
            if match is not None:
                return match
    return None


def validate_stable_selector(
    selector: Any,
    changed_ids: set[str],
    all_selector: str,
    label: str,
    errors: list[str],
) -> None:
    if not changed_ids:
        if selector != all_selector:
            errors.append(f"{label}: stable selector must be {all_selector}")
        return
    if not isinstance(selector, str) or not selector.startswith("all_except:"):
        errors.append(f"{label}: stable selector must use all_except:<changed IDs>")
        return
    selected_ids = {item for item in selector.removeprefix("all_except:").split(",") if item}
    if selected_ids != changed_ids:
        errors.append(
            f"{label}: all_except IDs {sorted(selected_ids)} do not match changed IDs "
            f"{sorted(changed_ids)}"
        )


def validate_exact_fraction(
    value: Any,
    passed: int,
    total: int,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or "/" not in value:
        return
    expected = f"{passed}/{total}"
    if value != expected:
        errors.append(f"{label}: expected exact fraction {expected}, found {value}")


def resolve_repo_path(repo_root: Path, value: Any, label: str) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = (repo_root / value).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError:
        return None
    return path


def validate_case_record(
    case_id: str,
    case: dict[str, Any],
    expected_dimension: str,
    all_cases: dict[str, dict[str, Any]],
    repo_root: Path,
    card_hashes: dict[str, str],
    panel_ids: set[str],
    errors: list[str],
) -> tuple[Path | None, str | None]:
    label = f"{expected_dimension} case {case_id}"
    if case.get("dimension") != expected_dimension:
        errors.append(f"{label}: dimension mismatch")

    baseline_id = case.get("baseline_text_id")
    if baseline_id is not None and baseline_id not in all_cases:
        errors.append(f"{label}: unknown baseline_text_id {baseline_id}")

    text_path = resolve_repo_path(repo_root, case.get("text_path"), f"{label} text_path")
    actual_sha256: str | None = None
    if text_path is None or not text_path.is_file():
        errors.append(f"{label}: invalid or missing text_path {case.get('text_path')}")
    else:
        try:
            data = text_path.read_bytes()
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{label}: text is not valid UTF-8: {exc}")
        else:
            actual_sha256 = sha256_bytes(data)
            if case.get("text_sha256") != actual_sha256:
                errors.append(
                    f"{label}: text_sha256 mismatch: expected {case.get('text_sha256')}, "
                    f"actual {actual_sha256}"
                )

    versions = case.get("versions")
    if not isinstance(versions, dict):
        errors.append(f"{label}: versions must be an object")
    else:
        if versions.get("book_card_sha256") != card_hashes["book"]:
            errors.append(f"{label}: book_card_sha256 mismatch")
        if versions.get("discourse_card_sha256") != card_hashes["discourse"]:
            errors.append(f"{label}: discourse_card_sha256 mismatch")
        if versions.get("panel_id") not in panel_ids:
            errors.append(f"{label}: unknown panel_id {versions.get('panel_id')}")
        if not isinstance(versions.get("judge_prompt_version"), str):
            errors.append(f"{label}: judge_prompt_version must be a string")

    mutation_spec_path = case.get("mutation_spec_path")
    if mutation_spec_path is not None:
        spec_path = resolve_repo_path(repo_root, mutation_spec_path, f"{label} mutation spec")
        if spec_path is None or not spec_path.is_file():
            errors.append(f"{label}: invalid or missing mutation_spec_path")
        else:
            try:
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"{label}: invalid mutation spec JSON: {exc}")
                spec = {}
            try:
                variant = build_variant(spec_path, repo_root)
            except MutationError as exc:
                errors.append(f"{label}: invalid mutation spec: {exc}")
            else:
                if variant["case_id"] != case_id:
                    errors.append(f"{label}: mutation spec case_id mismatch")
                if text_path is not None and variant["output_path"] != text_path:
                    errors.append(f"{label}: mutation output_path differs from text_path")
                if actual_sha256 is not None and variant["output_sha256"] != actual_sha256:
                    errors.append(f"{label}: materialized output differs from mutation spec")
            if not isinstance(spec.get("expected_output_sha256"), str):
                errors.append(f"{label}: mutation spec must freeze expected_output_sha256")
            if not isinstance(spec.get("expected_nonwhitespace_codepoints"), int):
                errors.append(
                    f"{label}: mutation spec must freeze expected_nonwhitespace_codepoints"
                )
            if baseline_id in all_cases:
                baseline = all_cases[baseline_id]
                if spec.get("baseline_text_path") != baseline.get("text_path"):
                    errors.append(f"{label}: mutation baseline_text_path differs from baseline case")
                if spec.get("baseline_sha256") != baseline.get("text_sha256"):
                    errors.append(f"{label}: mutation baseline_sha256 differs from baseline case")
            if spec.get("output_text_path") != case.get("text_path"):
                errors.append(f"{label}: mutation output path differs from case text_path")
            if spec.get("expected_output_sha256") != case.get("text_sha256"):
                errors.append(f"{label}: mutation output SHA differs from case text_sha256")

    human_confirmation = case.get("human_confirmation")
    if not isinstance(human_confirmation, dict) or human_confirmation.get("status") not in {
        "pending",
        "approved_for_development",
        "human_reviewed",
        "frozen",
    }:
        errors.append(f"{label}: invalid human_confirmation.status")

    return text_path, actual_sha256


def validate_cognitive_expected(
    case_id: str,
    expected: dict[str, Any],
    relation_ids: set[str],
    path_ids: set[str],
    text_path: Path | None,
    errors: list[str],
) -> None:
    label = f"cognitive expected {case_id}"
    changed_relations = expected.get("expected_changed_relation_ids")
    changed_paths = expected.get("expected_changed_path_ids")
    if not isinstance(changed_relations, list) or not set(changed_relations) <= relation_ids:
        errors.append(f"{label}: unknown or invalid changed relation IDs")
    if not isinstance(changed_paths, list) or not set(changed_paths) <= path_ids:
        errors.append(f"{label}: unknown or invalid changed path IDs")
    changed_relation_set = set(changed_relations) if isinstance(changed_relations, list) else set()
    changed_path_set = set(changed_paths) if isinstance(changed_paths, list) else set()
    validate_stable_selector(
        expected.get("expected_stable_relation_selector"),
        changed_relation_set,
        f"all_{len(relation_ids)}_book_card_relations",
        f"{label} relation selector",
        errors,
    )
    validate_stable_selector(
        expected.get("expected_stable_path_selector"),
        changed_path_set,
        f"all_{len(path_ids)}_mandatory_paths",
        f"{label} path selector",
        errors,
    )
    metrics = expected.get("expected_metrics")
    if isinstance(metrics, dict):
        validate_exact_fraction(
            metrics.get("cognitive_relation_coverage"),
            len(relation_ids) - len(changed_relation_set),
            len(relation_ids),
            f"{label} cognitive_relation_coverage",
            errors,
        )
        validate_exact_fraction(
            metrics.get("complete_core_path_rate"),
            len(path_ids) - len(changed_path_set),
            len(path_ids),
            f"{label} complete_core_path_rate",
            errors,
        )

    hard_constraints = expected.get("hard_constraints")
    if not isinstance(hard_constraints, dict):
        errors.append(f"{label}: hard_constraints must be an object")
        return
    if hard_constraints.get("counter_version") != COUNTER_VERSION:
        errors.append(f"{label}: counter version mismatch")
    if text_path is None or not text_path.is_file():
        return
    try:
        text = text_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    count = count_text(text)["nonwhitespace_codepoints"]
    minimum = hard_constraints.get("min_chars")
    maximum = hard_constraints.get("max_chars")
    actual_within_bounds = evaluate_bounds(count, minimum, maximum)
    if actual_within_bounds is None:
        actual_within_bounds = True
    if hard_constraints.get("expected_within_bounds") is not actual_within_bounds:
        errors.append(
            f"{label}: expected_within_bounds mismatch at count {count}, "
            f"bounds {minimum}..{maximum}"
        )


def validate_discourse_expected(
    case_id: str,
    expected: dict[str, Any],
    panel_edge_ids: set[str],
    errors: list[str],
) -> None:
    label = f"discourse expected {case_id}"
    changed_edges = expected.get("expected_changed_edge_ids")
    if not isinstance(changed_edges, list) or not set(changed_edges) <= panel_edge_ids:
        errors.append(f"{label}: unknown or invalid changed edge IDs")
    changed_edge_set = set(changed_edges) if isinstance(changed_edges, list) else set()
    unfrozen_edges = expected.get("expected_unfrozen_edge_ids", [])
    if not isinstance(unfrozen_edges, list) or not set(unfrozen_edges) <= panel_edge_ids:
        errors.append(f"{label}: unknown or invalid unfrozen edge IDs")
    unfrozen_edge_set = set(unfrozen_edges) if isinstance(unfrozen_edges, list) else set()
    if changed_edge_set & unfrozen_edge_set:
        errors.append(f"{label}: changed and unfrozen edge IDs overlap")
    validate_stable_selector(
        expected.get("expected_stable_edge_selector"),
        changed_edge_set | unfrozen_edge_set,
        f"all_{len(panel_edge_ids)}_PANEL-DEV-01_edges",
        f"{label} edge selector",
        errors,
    )
    for field in (
        "expected_changed_probes",
        "expected_stable_probes",
        "expected_unfrozen_probes",
    ):
        probes = expected.get(field, [])
        if not isinstance(probes, list) or not set(probes) <= KNOWN_PROBES:
            errors.append(f"{label}: unknown or invalid probes in {field}")
        elif len(probes) != len(set(probes)):
            errors.append(f"{label}: duplicate probes in {field}")
    changed = set(expected.get("expected_changed_probes", []))
    stable = set(expected.get("expected_stable_probes", []))
    unresolved = set(expected.get("expected_unfrozen_probes", []))
    if changed & stable or changed & unresolved or stable & unresolved:
        errors.append(f"{label}: changed/stable/unfrozen probes overlap")
    classified = changed | stable | unresolved
    if classified != KNOWN_PROBES:
        errors.append(
            f"{label}: probe tri-state must classify every known probe; "
            f"missing={sorted(KNOWN_PROBES - classified)}"
        )
    metrics = expected.get("expected_metrics")
    if not isinstance(metrics, dict):
        errors.append(f"{label}: expected_metrics must be an object")
    else:
        authorial_edge_recovery = metrics.get("authorial_edge_recovery")
        if (
            unfrozen_edge_set
            and isinstance(authorial_edge_recovery, str)
            and "/" in authorial_edge_recovery
        ):
            errors.append(
                f"{label}: exact authorial_edge_recovery is invalid while edges are unfrozen"
            )
        validate_exact_fraction(
            authorial_edge_recovery,
            len(panel_edge_ids) - len(changed_edge_set),
            len(panel_edge_ids),
            f"{label} authorial_edge_recovery",
            errors,
        )


def validate_strict_content_gate_expectations(
    cognitive_expected: dict[str, dict[str, Any]],
    discourse_expected: dict[str, dict[str, Any]],
    panel_edge_links: Mapping[str, set[str]],
    errors: list[str],
) -> None:
    """Ensure failed cognitive leaves propagate through the frozen strict edge gate."""

    for case_id in sorted(set(cognitive_expected) & set(discourse_expected)):
        failed_relations = set(
            cognitive_expected[case_id].get("expected_changed_relation_ids", [])
        )
        strictly_gated_edges = {
            edge_id
            for edge_id, linked_relations in panel_edge_links.items()
            if failed_relations & linked_relations
        }
        discourse = discourse_expected[case_id]
        classified_nonstable = set(
            discourse.get("expected_changed_edge_ids", [])
        ) | set(discourse.get("expected_unfrozen_edge_ids", []))
        missing = strictly_gated_edges - classified_nonstable
        if missing:
            errors.append(
                f"cross-dimension expected {case_id}: strict content gate requires "
                f"changed or unfrozen edges {sorted(missing)!r}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate book-level cognitive and discourse calibration JSONL."
    )
    parser.add_argument("calibration_dir", type=Path)
    parser.add_argument("--book-card", required=True, type=Path)
    parser.add_argument("--discourse-card", required=True, type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    calibration_dir = args.calibration_dir.resolve()
    errors: list[str] = []

    book_card_bytes = args.book_card.read_bytes()
    discourse_card_bytes = args.discourse_card.read_bytes()
    book_card = load_json(args.book_card, errors)
    discourse_card = load_json(args.discourse_card, errors)
    card_hashes = {
        "book": sha256_bytes(book_card_bytes),
        "discourse": sha256_bytes(discourse_card_bytes),
    }
    relation_ids = collect_ids(book_card, ("R-",))
    path_ids = collect_ids(book_card, ("P-",))
    edge_ids = collect_ids(discourse_card, ("AE-",))
    panel_ids = collect_ids(discourse_card, ("PANEL-",))
    panel = find_object_by_id(discourse_card, "PANEL-DEV-01")
    raw_panel_edge_ids = panel.get("edge_ids") if isinstance(panel, dict) else None
    panel_edge_ids = set(raw_panel_edge_ids) if isinstance(raw_panel_edge_ids, list) else set()
    if not panel_edge_ids or not panel_edge_ids <= edge_ids:
        errors.append("PANEL-DEV-01 is missing or contains unknown edge IDs")
    panel_edge_links = {
        edge["id"]: set(edge.get("linked_cognitive_relation_ids", []))
        for edge in discourse_card.get("authorial_edges", [])
        if edge.get("id") in panel_edge_ids
    }

    by_dimension: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for dimension in DIMENSIONS:
        dimension_dir = calibration_dir / dimension
        cases = load_jsonl(dimension_dir / "cases.jsonl", errors)
        expected = load_jsonl(dimension_dir / "expected.jsonl", errors)
        if set(cases) != set(expected):
            errors.append(
                f"{dimension}: case/expected ID mismatch: "
                f"cases_only={sorted(set(cases) - set(expected))}, "
                f"expected_only={sorted(set(expected) - set(cases))}"
            )
        by_dimension[dimension] = {"cases": cases, "expected": expected}

        text_paths: dict[str, Path | None] = {}
        for case_id, case in cases.items():
            text_path, _ = validate_case_record(
                case_id,
                case,
                dimension,
                cases,
                repo_root,
                card_hashes,
                panel_ids,
                errors,
            )
            text_paths[case_id] = text_path
        for case_id, expectation in expected.items():
            if dimension == "cognitive":
                validate_cognitive_expected(
                    case_id,
                    expectation,
                    relation_ids,
                    path_ids,
                    text_paths.get(case_id),
                    errors,
                )
            else:
                validate_discourse_expected(
                    case_id, expectation, panel_edge_ids, errors
                )

    cognitive_cases = by_dimension["cognitive"]["cases"]
    discourse_cases = by_dimension["discourse"]["cases"]
    if set(cognitive_cases) != set(discourse_cases):
        errors.append("cognitive and discourse calibration case sets differ")
    for case_id in set(cognitive_cases) & set(discourse_cases):
        cognitive = cognitive_cases[case_id]
        discourse = discourse_cases[case_id]
        for field in (
            "case_type",
            "case_target",
            "baseline_text_id",
            "text_path",
            "text_sha256",
            "mutation_spec_path",
        ):
            if cognitive.get(field) != discourse.get(field):
                errors.append(f"cross-dimension case {case_id}: {field} mismatch")

    validate_strict_content_gate_expectations(
        by_dimension["cognitive"]["expected"],
        by_dimension["discourse"]["expected"],
        panel_edge_links,
        errors,
    )

    result = {
        "calibration_dir": str(calibration_dir),
        "cognitive_cases": len(cognitive_cases),
        "discourse_cases": len(discourse_cases),
        "relations_in_card": len(relation_ids),
        "mandatory_paths_in_card": len(path_ids),
        "authorial_edges_in_card": len(edge_ids),
        "panel_edges": len(panel_edge_ids),
        "valid": not errors,
        "errors": errors,
    }
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
