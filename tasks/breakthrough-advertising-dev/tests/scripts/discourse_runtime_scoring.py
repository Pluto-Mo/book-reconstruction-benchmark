#!/usr/bin/env python3

"""Deterministic scoring helpers for the discourse reconstruction runtime."""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

from runtime_scoring import RuntimeValidationError

T = TypeVar("T")
UNRESOLVED_OUTCOMES = {"unresolved", "infrastructure_error"}
EDITORIAL_PROBES = (
    "local_progression",
    "global_order",
    "spine_connectivity",
    "example_integration",
    "closure",
)


def strict_content_gate(
    linked_relation_ids: Sequence[str],
    relation_outcomes: Mapping[str, str],
) -> tuple[int | None, dict[str, str]]:
    """Apply the frozen strict-conjunction content gate for one Authorial Edge."""

    missing = sorted(set(linked_relation_ids) - set(relation_outcomes))
    if missing:
        raise RuntimeValidationError(
            f"content gate references missing cognitive relations {missing!r}"
        )
    linked = {relation_id: relation_outcomes[relation_id] for relation_id in linked_relation_ids}
    invalid = sorted(
        relation_id
        for relation_id, outcome in linked.items()
        if outcome not in {"pass", "fail", *UNRESOLVED_OUTCOMES}
    )
    if invalid:
        raise RuntimeValidationError(f"content gate has invalid outcomes for {invalid!r}")
    if any(outcome in UNRESOLVED_OUTCOMES for outcome in linked.values()):
        return None, linked
    if any(outcome == "fail" for outcome in linked.values()):
        return 0, linked
    return 1, linked


def select_panel(card: Mapping[str, Any], rollout_index: int) -> Mapping[str, Any]:
    matches = [
        panel
        for panel in card["sampling_plan"]["panels"]
        if rollout_index in panel["rollout_indices"]
    ]
    if len(matches) != 1:
        raise RuntimeValidationError(
            f"rollout {rollout_index} must map to exactly one discourse panel"
        )
    return matches[0]


def validate_structure(
    structure: Mapping[str, Any],
    submission_text: str,
    config: Mapping[str, Any],
) -> None:
    errors: list[str] = []
    units = structure.get("major_units", [])
    examples = structure.get("examples", [])
    max_units = config["structure_extraction"]["max_major_units"]
    accepted_roles = set(config["spine_connectivity"]["accepted_roles"])
    if not 2 <= len(units) <= max_units:
        errors.append(f"structure must contain 2..{max_units} major units")

    seen_unit_ids: set[str] = set()
    previous_end = -1
    units_by_id: dict[str, Mapping[str, Any]] = {}
    for index, unit in enumerate(units):
        unit_id = unit.get("unit_id")
        start = unit.get("start_char")
        end = unit.get("end_char")
        if unit_id in seen_unit_ids:
            errors.append(f"duplicate major unit id {unit_id!r}")
        seen_unit_ids.add(str(unit_id))
        units_by_id[str(unit_id)] = unit
        if unit.get("function") not in accepted_roles:
            errors.append(f"unit {unit_id}: function is not accepted")
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"unit {unit_id}: character span must be integers")
            continue
        if not 0 <= start < end <= len(submission_text):
            errors.append(f"unit {unit_id}: invalid character span [{start}, {end})")
            continue
        if index and start < previous_end:
            errors.append(f"unit {unit_id}: major unit spans overlap or are unsorted")
        previous_end = end
        if not submission_text[start:end].strip():
            errors.append(f"unit {unit_id}: span contains no text")

    seen_example_ids: set[str] = set()
    for example in examples:
        example_id = str(example.get("example_id"))
        if example_id in seen_example_ids:
            errors.append(f"duplicate example id {example_id!r}")
        seen_example_ids.add(example_id)
        host = units_by_id.get(str(example.get("host_unit_id")))
        if host is None:
            errors.append(f"example {example_id}: unknown host unit")
            continue
        start = example.get("start_char")
        end = example.get("end_char")
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"example {example_id}: character span must be integers")
            continue
        if not 0 <= start < end <= len(submission_text):
            errors.append(f"example {example_id}: invalid character span [{start}, {end})")
            continue
        if start < host["start_char"] or end > host["end_char"]:
            errors.append(f"example {example_id}: span is outside its host unit")
        if not submission_text[start:end].strip():
            errors.append(f"example {example_id}: span contains no text")
    if errors:
        raise RuntimeValidationError(errors)


def prose_paragraph_spans(text: str) -> list[dict[str, Any]]:
    """Return deterministic non-heading Markdown paragraph spans."""

    separators = list(re.finditer(r"\n[ \t]*\n+", text))
    boundaries = [(0, separator.start()) for separator in separators]
    starts = [0] + [separator.end() for separator in separators]
    ends = [separator.start() for separator in separators] + [len(text)]
    del boundaries  # only starts/ends are needed; retained construction documents the split.

    paragraphs: list[dict[str, Any]] = []
    for raw_start, raw_end in zip(starts, ends, strict=True):
        segment = text[raw_start:raw_end]
        if not segment.strip():
            continue
        leading = len(segment) - len(segment.lstrip())
        trailing = len(segment.rstrip())
        start = raw_start + leading
        end = raw_start + trailing
        content = text[start:end]
        nonempty_lines = [line.strip() for line in content.splitlines() if line.strip()]
        if nonempty_lines and all(line.startswith("#") for line in nonempty_lines):
            continue
        paragraphs.append(
            {
                "paragraph_id": f"P:{start}:{end}",
                "start_char": start,
                "end_char": end,
                "text": content,
            }
        )
    return paragraphs


def deterministic_sample(
    values: Sequence[T],
    *,
    sample_size: int,
    seed: int,
    submission_sha256: str,
    probe_name: str,
    object_id: Callable[[T], str],
) -> list[T]:
    def key(value: T) -> tuple[str, str]:
        identifier = object_id(value)
        payload = (
            f"editorial-v1\0{seed}\0{submission_sha256}\0{probe_name}\0{identifier}"
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest(), identifier

    return sorted(values, key=key)[: min(sample_size, len(values))]


def canonical_global_score(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> tuple[float, str]:
    """Map two position-reversed pairwise responses back to canonical order."""

    if first["confidence"] == "insufficient" or second["confidence"] == "insufficient":
        return 0.5, "insufficient"
    if first["winner"] == "tie" or second["winner"] == "tie":
        return 0.5, "tie"
    first_canonical = "original" if first["winner"] == "left" else "swapped"
    second_canonical = "swapped" if second["winner"] == "left" else "original"
    if first_canonical == second_canonical == "original":
        return 1.0, "original"
    if first_canonical == second_canonical == "swapped":
        return 0.0, "swapped"
    return 0.5, "disagreement"


def aggregate_authorial_edges(
    edge_results: Sequence[Mapping[str, Any]],
    panel: Mapping[str, Any],
) -> tuple[float | None, dict[str, float | None]]:
    expected = list(panel["edge_ids"])
    actual = [str(result["edge_id"]) for result in edge_results]
    if actual != expected:
        raise RuntimeValidationError("Authorial Edge results do not match frozen panel order")
    strata_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
    if any(result["status"] == "unscorable" for result in edge_results):
        for result in edge_results:
            strata_values[str(result["stratum"])]
        return None, {stratum: None for stratum in sorted(strata_values)}

    numerator = 0.0
    denominator = 0.0
    for result in edge_results:
        score = result.get("score")
        weight = result.get("weight")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise RuntimeValidationError(f"edge {result['edge_id']} has no numeric score")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight <= 0:
            raise RuntimeValidationError(f"edge {result['edge_id']} has invalid weight")
        numerator += float(score) * float(weight)
        denominator += float(weight)
        strata_values[str(result["stratum"])].append((float(score), float(weight)))
    strata = {
        stratum: sum(score * weight for score, weight in values)
        / sum(weight for _, weight in values)
        for stratum, values in sorted(strata_values.items())
    }
    return numerator / denominator, strata


def aggregate_editorial(
    summaries: Mapping[str, Mapping[str, Any]],
    weights: Mapping[str, float],
) -> dict[str, float | None]:
    missing = sorted(set(EDITORIAL_PROBES) - set(summaries))
    if missing:
        raise RuntimeValidationError(f"missing editorial probe summaries {missing!r}")
    if not math.isclose(sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeValidationError("editorial weights must sum to 1.0")
    result: dict[str, float | None] = {}
    complete = True
    for name in EDITORIAL_PROBES:
        summary = summaries[name]
        score = summary.get("score")
        if summary.get("status") != "complete" or not isinstance(score, (int, float)):
            result[name] = None
            complete = False
        else:
            result[name] = float(score)
    result["editorial_coherence"] = (
        sum(float(result[name]) * float(weights[name]) for name in EDITORIAL_PROBES)
        if complete
        else None
    )
    return result


def aggregate_discourse(
    *,
    book_id: str,
    submission_id: str,
    panel_id: str,
    authorial_score: float | None,
    authorial_strata: Mapping[str, float | None],
    editorial: Mapping[str, float | None],
    dimension_weights: Mapping[str, float],
) -> dict[str, Any]:
    editorial_score = editorial["editorial_coherence"]
    complete = authorial_score is not None and editorial_score is not None
    discourse_score = None
    if complete:
        discourse_score = (
            float(authorial_score) * float(dimension_weights["authorial_edge_recovery"])
            + float(editorial_score) * float(dimension_weights["editorial_coherence"])
        )
    return {
        "schema_version": "1.0",
        "status": "complete" if complete else "unscorable",
        "book_id": book_id,
        "submission_id": submission_id,
        "panel_id": panel_id,
        "authorial_edge_recovery": authorial_score,
        "authorial_strata": dict(authorial_strata),
        "editorial": dict(editorial),
        "discourse_reconstruction": discourse_score,
    }
