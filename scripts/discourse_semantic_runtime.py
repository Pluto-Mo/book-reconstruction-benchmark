#!/usr/bin/env python3

"""Provider-neutral Authorial Edge and Editorial Coherence runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from cognitive_semantic_runtime import (
    CommandProvider,
    ProviderError,
    StructuredProvider,
    event,
    make_request,
    read_text,
    resolve_locator_quotes,
    response_errors,
    sha256_bytes,
    write_json,
    write_jsonl,
)
from discourse_runtime_scoring import (
    aggregate_authorial_edges,
    aggregate_discourse,
    aggregate_editorial,
    canonical_global_score,
    deterministic_sample,
    prose_paragraph_spans,
    select_panel,
    strict_content_gate,
    validate_structure,
)
from runtime_scoring import (
    REPO_ROOT,
    RuntimeValidationError,
    load_json_object,
    schema_validation_errors,
)
from validate_book_card import validate_cross_references as validate_book_cross_references
from validate_discourse_card import validate_cross_references as validate_discourse_cross_references

DEFAULT_BOOK_SCHEMA = REPO_ROOT / "schemas/book-card.schema.json"
DEFAULT_DISCOURSE_SCHEMA = REPO_ROOT / "schemas/discourse-card.schema.json"
DEFAULT_PROVIDER_SCHEMA = REPO_ROOT / "schemas/cognitive-provider-config.schema.json"
DEFAULT_REQUEST_SCHEMA = REPO_ROOT / "schemas/model-request.schema.json"
DEFAULT_LOCATOR_RESPONSE_SCHEMA = REPO_ROOT / "schemas/locator-model-response.schema.json"
DEFAULT_EDGE_JUDGE_SCHEMA = (
    REPO_ROOT / "schemas/authorial-edge-judge-model-response.schema.json"
)
DEFAULT_STRUCTURE_SCHEMA = REPO_ROOT / "schemas/discourse-structure-model-response.schema.json"
DEFAULT_LOCAL_SCHEMA = REPO_ROOT / "schemas/editorial-local-model-response.schema.json"
DEFAULT_GLOBAL_SCHEMA = (
    REPO_ROOT / "schemas/editorial-global-order-model-response.schema.json"
)
DEFAULT_SPINE_SCHEMA = REPO_ROOT / "schemas/editorial-spine-model-response.schema.json"
DEFAULT_EXAMPLE_SCHEMA = REPO_ROOT / "schemas/editorial-example-model-response.schema.json"
DEFAULT_CLOSURE_SCHEMA = REPO_ROOT / "schemas/editorial-closure-model-response.schema.json"
DEFAULT_AGGREGATE_SCHEMA = REPO_ROOT / "schemas/discourse-aggregate.schema.json"
DEFAULT_EDGE_LOCATOR_PROMPT = (
    REPO_ROOT / "prompts/discourse/authorial-edge-locator-v1.md"
)
DEFAULT_EDGE_JUDGE_PROMPT = REPO_ROOT / "prompts/discourse/authorial-edge-judge-v1.md"
DEFAULT_STRUCTURE_PROMPT = REPO_ROOT / "prompts/discourse/structure-extractor-v1.md"
DEFAULT_EDITORIAL_PROMPT = REPO_ROOT / "prompts/discourse/editorial-probes-v1.md"


def prompt_version(label: str, path: Path) -> str:
    return f"{label}-{sha256_bytes(path.read_bytes())[:12]}"


def read_relation_outcomes(cognitive: Mapping[str, Any]) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for result in cognitive.get("relation_results", []):
        relation_id = result.get("relation_id")
        outcome = result.get("outcome")
        if not isinstance(relation_id, str) or relation_id in outcomes:
            raise RuntimeValidationError("cognitive aggregate has duplicate/invalid relation ids")
        if not isinstance(outcome, str):
            raise RuntimeValidationError(f"cognitive relation {relation_id} has no outcome")
        outcomes[relation_id] = outcome
    return outcomes


def source_anchor_summaries(
    book_card: Mapping[str, Any], anchor_ids: Sequence[str]
) -> list[dict[str, str]]:
    """Return compact Card summaries; draft runtime never sends raw copyrighted source."""

    by_id = {anchor["id"]: anchor for anchor in book_card["source_anchors"]}
    result: list[dict[str, str]] = []
    for anchor_id in anchor_ids:
        anchor = by_id.get(anchor_id)
        if anchor is None:
            raise RuntimeValidationError(f"unknown Source Anchor {anchor_id!r}")
        result.append(
            {
                "anchor_id": anchor_id,
                "evidence_summary": anchor["evidence_summary"],
                "argument_function": anchor["argument_function"],
            }
        )
    return result


def call_structured(
    *,
    stage: str,
    object_id: str,
    book_id: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    system_prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
    payload_factory: Callable[[int], Mapping[str, Any]],
    validator: Callable[[Mapping[str, Any]], None] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    last_error = ""
    generation_key = (
        "evidence_locator" if stage == "authorial_edge_locator" else "relation_adjudicator"
    )
    for attempt in range(1, provider_config["max_protocol_attempts"] + 1):
        request = make_request(
            stage=stage,
            attempt=attempt,
            model_id=provider_config["model_id"],
            generation_parameters=provider_config["generation_parameters"][generation_key],
            system_prompt=system_prompt,
            user_payload=payload_factory(attempt),
            response_schema=response_schema,
            book_id=book_id,
            submission_id=submission_id,
            submission_sha256=submission_sha256,
            criterion_id=object_id,
            prompt_version=prompt_version_value,
            request_schema=request_schema,
        )
        try:
            response = provider.complete(request)
        except ProviderError as exc:
            last_error = str(exc)
            events.append(event(request, "provider_error", detail=last_error))
            continue
        errors = response_errors(response, response_schema, f"{stage} {object_id}")
        if not errors and validator is not None:
            try:
                validator(response)
            except RuntimeValidationError as exc:
                errors.extend(exc.errors)
        if errors:
            last_error = "; ".join(errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue
        events.append(event(request, "complete"))
        return response, events, ""
    return None, events, last_error or "unknown provider/protocol error"


def run_edge_locator(
    *,
    edge: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    system_prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    last_error = ""
    max_attempts = provider_config["max_protocol_attempts"]
    for attempt in range(1, max_attempts + 1):
        request = make_request(
            stage="authorial_edge_locator",
            attempt=attempt,
            model_id=provider_config["model_id"],
            generation_parameters=provider_config["generation_parameters"]["evidence_locator"],
            system_prompt=system_prompt,
            user_payload={
                "mode": "initial" if attempt == 1 else "full_text_review",
                "edge": {
                    "edge_type": edge["edge_type"],
                    "relation_description": edge["relation_description"],
                    "rhetorical_role": edge["rhetorical_role"],
                    "required_facets": edge["required_facets"],
                    "expected_downstream": edge["expected_downstream"],
                },
                "submission_text": submission_text,
            },
            response_schema=response_schema,
            book_id=book_id,
            submission_id=submission_id,
            submission_sha256=submission_sha256,
            criterion_id=edge["id"],
            prompt_version=prompt_version_value,
            request_schema=request_schema,
        )
        try:
            response = provider.complete(request)
        except ProviderError as exc:
            last_error = str(exc)
            events.append(event(request, "provider_error", detail=last_error))
            continue
        errors = response_errors(response, response_schema, f"edge locator {edge['id']}")
        if errors:
            last_error = "; ".join(errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue
        if response["status"] == "none":
            events.append(event(request, "none"))
            if attempt < max_attempts:
                continue
            return {
                "status": "none",
                "candidates": [],
                "attempts": attempt,
                "notes": response.get("notes", "No evidence after full-text review."),
            }, events
        try:
            candidates = resolve_locator_quotes(
                response,
                submission_text,
                edge["id"],
                provider_config["locator_context_chars"],
            )
        except RuntimeValidationError as exc:
            last_error = "; ".join(exc.errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue
        events.append(event(request, "found"))
        return {
            "status": "found",
            "candidates": candidates,
            "attempts": attempt,
            "notes": response.get("notes", f"Evidence resolved on attempt {attempt}."),
        }, events
    return {
        "status": "locator_error",
        "candidates": [],
        "attempts": max_attempts,
        "notes": last_error or "unknown provider/protocol error",
    }, events


def run_authorial_edge(
    *,
    edge: Mapping[str, Any],
    panel_id: str,
    book_card: Mapping[str, Any],
    relation_outcomes: Mapping[str, str],
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    edge_locator_prompt: str,
    edge_judge_prompt: str,
    edge_locator_prompt_version: str,
    edge_judge_prompt_version: str,
    locator_response_schema: Mapping[str, Any],
    edge_judge_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gate, linked = strict_content_gate(
        edge["linked_cognitive_relation_ids"], relation_outcomes
    )
    base = {
        "schema_version": "1.0",
        "edge_id": edge["id"],
        "panel_id": panel_id,
        "content_gate": gate,
        "linked_cognitive_outcomes": linked,
        "weight": float(edge["weight"]),
        "stratum": edge["stratum"],
        "critical": bool(edge["critical"]),
        "source_context_mode": "book_card_summaries_development_only",
    }
    if gate is None:
        return {
            **base,
            "status": "unscorable",
            "rhetorical_function_preserved": None,
            "downstream_dependency_preserved": None,
            "score": None,
            "selected_evidence": [],
            "reason": "A linked cognitive relation is unresolved.",
        }, []
    if gate == 0:
        return {
            **base,
            "status": "gated_out",
            "rhetorical_function_preserved": None,
            "downstream_dependency_preserved": None,
            "score": 0.0,
            "selected_evidence": [],
            "reason": "At least one linked cognitive relation failed; no edge Judge call was made.",
        }, []

    evidence, locator_events = run_edge_locator(
        edge=edge,
        book_id=book_card["book_id"],
        submission_text=submission_text,
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        system_prompt=edge_locator_prompt,
        prompt_version_value=edge_locator_prompt_version,
        response_schema=locator_response_schema,
        request_schema=request_schema,
    )
    if evidence["status"] == "locator_error":
        return {
            **base,
            "status": "unscorable",
            "rhetorical_function_preserved": None,
            "downstream_dependency_preserved": None,
            "score": None,
            "selected_evidence": [],
            "reason": f"Edge Locator failed: {evidence['notes']}",
        }, locator_events
    if evidence["status"] == "none":
        return {
            **base,
            "status": "complete",
            "rhetorical_function_preserved": False,
            "downstream_dependency_preserved": False,
            "score": 0.0,
            "selected_evidence": [],
            "reason": "Two frozen Locator attempts found no explicit edge evidence.",
        }, locator_events

    candidate_ids = {candidate["candidate_id"] for candidate in evidence["candidates"]}

    def validate_edge_response(response: Mapping[str, Any]) -> None:
        errors: list[str] = []
        if response.get("edge_id") != edge["id"]:
            errors.append("edge_id does not match request")
        selected = set(response.get("selected_candidate_ids", []))
        if not selected.issubset(candidate_ids):
            errors.append("selected_candidate_ids contain unknown candidates")
        if (
            response.get("rhetorical_function_preserved")
            or response.get("downstream_dependency_preserved")
        ) and not selected:
            errors.append("a positive edge facet requires selected evidence")
        if response.get("contradiction_found") and (
            response.get("rhetorical_function_preserved")
            or response.get("downstream_dependency_preserved")
        ):
            errors.append("contradiction_found cannot accompany a positive edge facet")
        if not set(response.get("missing_facets", [])).issubset(edge["required_facets"]):
            errors.append("missing_facets include facets not required by this edge")
        if errors:
            raise RuntimeValidationError(errors)

    judge, judge_events, judge_error = call_structured(
        stage="authorial_edge_adjudicator",
        object_id=edge["id"],
        book_id=book_card["book_id"],
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        system_prompt=edge_judge_prompt,
        prompt_version_value=edge_judge_prompt_version,
        response_schema=edge_judge_schema,
        request_schema=request_schema,
        payload_factory=lambda attempt: {
            "mode": "initial" if attempt == 1 else "protocol_retry",
            "edge": {
                "edge_id": edge["id"],
                "source_a": source_anchor_summaries(
                    book_card, edge["source_a_anchor_ids"]
                ),
                "source_b": source_anchor_summaries(
                    book_card, edge["source_b_anchor_ids"]
                ),
                "relation_description": edge["relation_description"],
                "rhetorical_role": edge["rhetorical_role"],
                "required_facets": edge["required_facets"],
                "expected_downstream": edge["expected_downstream"],
                "hard_negative_relations": edge["hard_negative_relations"],
            },
            "content_gate": 1,
            "evidence_candidates": evidence["candidates"],
            "submission_text": submission_text,
        },
        validator=validate_edge_response,
    )
    all_events = locator_events + judge_events
    if judge is None:
        return {
            **base,
            "status": "unscorable",
            "rhetorical_function_preserved": None,
            "downstream_dependency_preserved": None,
            "score": None,
            "selected_evidence": [],
            "reason": f"Edge Judge failed: {judge_error}",
        }, all_events
    r = bool(judge["rhetorical_function_preserved"])
    d = bool(judge["downstream_dependency_preserved"])
    selected_by_id = {
        candidate["candidate_id"]: candidate for candidate in evidence["candidates"]
    }
    return {
        **base,
        "status": "complete",
        "rhetorical_function_preserved": r,
        "downstream_dependency_preserved": d,
        "score": 0.5 * float(r) + 0.5 * float(d),
        "selected_evidence": [
            selected_by_id[candidate_id]
            for candidate_id in judge["selected_candidate_ids"]
        ],
        "missing_facets": judge["missing_facets"],
        "contradiction_found": judge["contradiction_found"],
        "confidence": judge["confidence"],
        "reason": judge["reason"],
        "judge_model": provider.model_id,
    }, all_events


def run_authorial_panel(
    *,
    card: Mapping[str, Any],
    panel: Mapping[str, Any],
    book_card: Mapping[str, Any],
    relation_outcomes: Mapping[str, str],
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompts: Mapping[str, str],
    prompt_versions: Mapping[str, str],
    schemas: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edge_by_id = {edge["id"]: edge for edge in card["authorial_edges"]}
    edges = [edge_by_id[edge_id] for edge_id in panel["edge_ids"]]

    def process(edge: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return run_authorial_edge(
            edge=edge,
            panel_id=panel["id"],
            book_card=book_card,
            relation_outcomes=relation_outcomes,
            submission_text=submission_text,
            submission_id=submission_id,
            submission_sha256=submission_sha256,
            provider_config=provider_config,
            provider=provider,
            edge_locator_prompt=prompts["edge_locator"],
            edge_judge_prompt=prompts["edge_judge"],
            edge_locator_prompt_version=prompt_versions["edge_locator"],
            edge_judge_prompt_version=prompt_versions["edge_judge"],
            locator_response_schema=schemas["locator"],
            edge_judge_schema=schemas["edge_judge"],
            request_schema=schemas["request"],
        )

    if provider_config["max_concurrency"] == 1:
        processed = [process(edge) for edge in edges]
    else:
        with ThreadPoolExecutor(
            max_workers=provider_config["max_concurrency"],
            thread_name_prefix="authorial-edge",
        ) as executor:
            processed = list(executor.map(process, edges))
    return [item[0] for item in processed], [evt for item in processed for evt in item[1]]


def run_structure_extractor(
    *,
    card: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
    config = card["editorial_probe_config"]

    def validator(response: Mapping[str, Any]) -> None:
        validate_structure(response, submission_text, config)

    return call_structured(
        stage="discourse_structure_extractor",
        object_id="EDITORIAL-STRUCTURE",
        book_id=book_id,
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        system_prompt=prompt,
        prompt_version_value=prompt_version_value,
        response_schema=response_schema,
        request_schema=request_schema,
        payload_factory=lambda attempt: {
            "mode": "initial" if attempt == 1 else "protocol_retry",
            "submission_text": submission_text,
            "config": {
                **config["structure_extraction"],
                "accepted_roles": config["spine_connectivity"]["accepted_roles"],
                "accepted_example_functions": config["example_integration"][
                    "accepted_functions"
                ],
            },
        },
        validator=validator,
    )


def run_local_progression(
    *,
    card: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    paragraphs = prose_paragraph_spans(submission_text)
    pairs = [
        {
            "probe_id": (
                f"LP:{left['start_char']}:{left['end_char']}"
                f"->{right['start_char']}:{right['end_char']}"
            ),
            "left": left,
            "right": right,
        }
        for left, right in zip(paragraphs, paragraphs[1:])
    ]
    config = card["editorial_probe_config"]["local_progression"]
    sampled = deterministic_sample(
        pairs,
        sample_size=config["sample_size"],
        seed=card["sampling_plan"]["seed"],
        submission_sha256=submission_sha256,
        probe_name="local_progression",
        object_id=lambda pair: pair["probe_id"],
    )
    if not sampled:
        return {"probe": "local_progression", "status": "unscorable", "score": None}, [], []

    def process(pair: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        def validator(response: Mapping[str, Any]) -> None:
            if response.get("probe_id") != pair["probe_id"]:
                raise RuntimeValidationError("local probe_id does not match request")

        response, events, error = call_structured(
            stage="editorial_local_progression",
            object_id=pair["probe_id"],
            book_id=book_id,
            submission_id=submission_id,
            submission_sha256=submission_sha256,
            provider_config=provider_config,
            provider=provider,
            system_prompt=prompt,
            prompt_version_value=prompt_version_value,
            response_schema=response_schema,
            request_schema=request_schema,
            payload_factory=lambda attempt: {
                "probe": "local_progression",
                "probe_id": pair["probe_id"],
                "previous_paragraph": pair["left"]["text"],
                "next_paragraph": pair["right"]["text"],
                "criteria": config["criteria"],
            },
            validator=validator,
        )
        if response is None:
            return {
                "probe": "local_progression",
                "probe_id": pair["probe_id"],
                "status": "unscorable",
                "score": None,
                "reason": error,
            }, events
        score = sum(
            float(response[name]) for name in config["criteria"]
        ) / len(config["criteria"])
        return {
            "probe": "local_progression",
            "probe_id": pair["probe_id"],
            "status": "complete",
            "score": score,
            "verdict": {name: response[name] for name in config["criteria"]},
            "evidence": response["evidence"],
            "reason": response["reason"],
        }, events

    with ThreadPoolExecutor(
        max_workers=min(provider_config["max_concurrency"], len(sampled)),
        thread_name_prefix="editorial-local",
    ) as executor:
        processed = list(executor.map(process, sampled))
    audits = [item[0] for item in processed]
    summary = {
        "probe": "local_progression",
        "status": "complete" if all(item["status"] == "complete" for item in audits) else "unscorable",
        "score": (
            sum(item["score"] for item in audits) / len(audits)
            if all(item["status"] == "complete" for item in audits)
            else None
        ),
        "sampled_probe_ids": [item["probe_id"] for item in audits],
    }
    return summary, audits, [evt for item in processed for evt in item[1]]


def run_global_order(
    *,
    card: Mapping[str, Any],
    structure: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    units = structure["major_units"]
    pairs = [
        {
            "pair_id": f"GO:{left['unit_id']}->{right['unit_id']}",
            "left_unit": left,
            "right_unit": right,
        }
        for left, right in zip(units, units[1:])
    ]
    config = card["editorial_probe_config"]["global_order"]
    sampled = deterministic_sample(
        pairs,
        sample_size=config["sample_size"],
        seed=card["sampling_plan"]["seed"],
        submission_sha256=submission_sha256,
        probe_name="global_order",
        object_id=lambda pair: pair["pair_id"],
    )
    if not sampled:
        return {"probe": "global_order", "status": "unscorable", "score": None}, [], []

    def process(pair: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        first_text = submission_text[
            pair["left_unit"]["start_char"] : pair["left_unit"]["end_char"]
        ]
        second_text = submission_text[
            pair["right_unit"]["start_char"] : pair["right_unit"]["end_char"]
        ]

        def make_call(reversal: bool) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
            suffix = "BA" if reversal else "AB"
            probe_id = f"{pair['pair_id']}:{suffix}"
            original = {"order": "original", "first": first_text, "second": second_text}
            swapped = {"order": "swapped", "first": second_text, "second": first_text}

            def validator(response: Mapping[str, Any]) -> None:
                if response.get("probe_id") != probe_id:
                    raise RuntimeValidationError("global-order probe_id does not match request")

            return call_structured(
                stage="editorial_global_order",
                object_id=probe_id,
                book_id=book_id,
                submission_id=submission_id,
                submission_sha256=submission_sha256,
                provider_config=provider_config,
                provider=provider,
                system_prompt=prompt,
                prompt_version_value=prompt_version_value,
                response_schema=response_schema,
                request_schema=request_schema,
                payload_factory=lambda attempt: {
                    "probe": "global_order",
                    "probe_id": probe_id,
                    "instruction": "只比较思想依赖；选择 left、right 或 tie。",
                    "left": swapped if reversal else original,
                    "right": original if reversal else swapped,
                },
                validator=validator,
            )

        first, first_events, first_error = make_call(False)
        second, second_events, second_error = make_call(True)
        all_events = first_events + second_events
        if first is None or second is None:
            return {
                "probe": "global_order",
                "probe_id": pair["pair_id"],
                "status": "unscorable",
                "score": None,
                "reason": first_error or second_error,
                "position_reversal": {"AB": first, "BA": second},
            }, all_events
        score, outcome = canonical_global_score(first, second)
        return {
            "probe": "global_order",
            "probe_id": pair["pair_id"],
            "status": "complete",
            "score": score,
            "canonical_outcome": outcome,
            "position_reversal": {"AB": first, "BA": second},
        }, all_events

    with ThreadPoolExecutor(
        max_workers=min(provider_config["max_concurrency"], len(sampled)),
        thread_name_prefix="editorial-global",
    ) as executor:
        processed = list(executor.map(process, sampled))
    audits = [item[0] for item in processed]
    complete = all(item["status"] == "complete" for item in audits)
    summary = {
        "probe": "global_order",
        "status": "complete" if complete else "unscorable",
        "score": sum(item["score"] for item in audits) / len(audits) if complete else None,
        "sampled_probe_ids": [item["probe_id"] for item in audits],
    }
    return summary, audits, [evt for item in processed for evt in item[1]]


def run_spine_connectivity(
    *,
    card: Mapping[str, Any],
    structure: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    units = structure["major_units"]
    expected_ids = [unit["unit_id"] for unit in units]

    def validator(response: Mapping[str, Any]) -> None:
        actual = [unit.get("unit_id") for unit in response.get("units", [])]
        if actual != expected_ids:
            raise RuntimeValidationError("spine response unit IDs/order do not match structure")

    response, events, error = call_structured(
        stage="editorial_spine_connectivity",
        object_id="SPINE",
        book_id=book_id,
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        system_prompt=prompt,
        prompt_version_value=prompt_version_value,
        response_schema=response_schema,
        request_schema=request_schema,
        payload_factory=lambda attempt: {
            "probe": "spine_connectivity",
            "controlling_question": structure["controlling_question"],
            "orphan_definition": card["editorial_probe_config"]["spine_connectivity"][
                "orphan_definition"
            ],
            "units": [
                {
                    "unit_id": unit["unit_id"],
                    "function": unit["function"],
                    "spine_contribution": unit["spine_contribution"],
                    "text": submission_text[unit["start_char"] : unit["end_char"]],
                }
                for unit in units
            ],
        },
        validator=validator,
    )
    if response is None:
        return {"probe": "spine_connectivity", "status": "unscorable", "score": None}, [
            {
                "probe": "spine_connectivity",
                "probe_id": "SPINE",
                "status": "unscorable",
                "score": None,
                "reason": error,
            }
        ], events
    score = 1.0 - sum(unit["orphan"] for unit in response["units"]) / len(units)
    audit = {
        "probe": "spine_connectivity",
        "probe_id": "SPINE",
        "status": "complete",
        "score": score,
        "units": response["units"],
    }
    return {"probe": "spine_connectivity", "status": "complete", "score": score}, [audit], events


def run_example_integration(
    *,
    card: Mapping[str, Any],
    structure: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    config = card["editorial_probe_config"]["example_integration"]
    sampled = deterministic_sample(
        structure["examples"],
        sample_size=config["sample_size"],
        seed=card["sampling_plan"]["seed"],
        submission_sha256=submission_sha256,
        probe_name="example_integration",
        object_id=lambda example: example["example_id"],
    )
    if not sampled:
        return {"probe": "example_integration", "status": "unscorable", "score": None}, [], []

    def process(example: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        probe_id = f"EX:{example['example_id']}"

        def validator(response: Mapping[str, Any]) -> None:
            if response.get("probe_id") != probe_id:
                raise RuntimeValidationError("example probe_id does not match request")

        start = example["start_char"]
        end = example["end_char"]
        response, events, error = call_structured(
            stage="editorial_example_integration",
            object_id=probe_id,
            book_id=book_id,
            submission_id=submission_id,
            submission_sha256=submission_sha256,
            provider_config=provider_config,
            provider=provider,
            system_prompt=prompt,
            prompt_version_value=prompt_version_value,
            response_schema=response_schema,
            request_schema=request_schema,
            payload_factory=lambda attempt: {
                "probe": "example_integration",
                "probe_id": probe_id,
                "case_text": submission_text[start:end],
                "context_before": submission_text[max(0, start - 500) : start],
                "context_after": submission_text[end : min(len(submission_text), end + 500)],
                "accepted_functions": config["accepted_functions"],
            },
            validator=validator,
        )
        if response is None:
            return {
                "probe": "example_integration",
                "probe_id": probe_id,
                "status": "unscorable",
                "score": None,
                "reason": error,
            }, events
        score = float(
            response["integrated"] and response["function"] in config["accepted_functions"]
        )
        return {
            "probe": "example_integration",
            "probe_id": probe_id,
            "status": "complete",
            "score": score,
            "function": response["function"],
            "integrated": response["integrated"],
            "reason": response["reason"],
        }, events

    with ThreadPoolExecutor(
        max_workers=min(provider_config["max_concurrency"], len(sampled)),
        thread_name_prefix="editorial-example",
    ) as executor:
        processed = list(executor.map(process, sampled))
    audits = [item[0] for item in processed]
    complete = all(item["status"] == "complete" for item in audits)
    summary = {
        "probe": "example_integration",
        "status": "complete" if complete else "unscorable",
        "score": sum(item["score"] for item in audits) / len(audits) if complete else None,
        "sampled_probe_ids": [item["probe_id"] for item in audits],
    }
    return summary, audits, [evt for item in processed for evt in item[1]]


def run_closure(
    *,
    card: Mapping[str, Any],
    structure: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    units = structure["major_units"]
    criteria = card["editorial_probe_config"]["closure"]["criteria"]
    response, events, error = call_structured(
        stage="editorial_closure",
        object_id="CLOSURE",
        book_id=book_id,
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        system_prompt=prompt,
        prompt_version_value=prompt_version_value,
        response_schema=response_schema,
        request_schema=request_schema,
        payload_factory=lambda attempt: {
            "probe": "closure",
            "opening": submission_text[units[0]["start_char"] : units[0]["end_char"]],
            "body_function_summary": [
                {
                    "unit_id": unit["unit_id"],
                    "function": unit["function"],
                    "spine_contribution": unit["spine_contribution"],
                }
                for unit in units
            ],
            "ending": submission_text[units[-1]["start_char"] : units[-1]["end_char"]],
            "criteria": criteria,
        },
    )
    if response is None:
        return {"probe": "closure", "status": "unscorable", "score": None}, [
            {
                "probe": "closure",
                "probe_id": "CLOSURE",
                "status": "unscorable",
                "score": None,
                "reason": error,
            }
        ], events
    score = sum(float(response[name]) for name in criteria) / len(criteria)
    audit = {
        "probe": "closure",
        "probe_id": "CLOSURE",
        "status": "complete",
        "score": score,
        "verdict": {name: response[name] for name in criteria},
        "evidence": response["evidence"],
        "reason": response["reason"],
    }
    return {"probe": "closure", "status": "complete", "score": score}, [audit], events


def run_editorial(
    *,
    card: Mapping[str, Any],
    structure: Mapping[str, Any],
    book_id: str,
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompt: str,
    prompt_version_value: str,
    schemas: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    common = {
        "card": card,
        "book_id": book_id,
        "submission_text": submission_text,
        "submission_id": submission_id,
        "submission_sha256": submission_sha256,
        "provider_config": provider_config,
        "provider": provider,
        "prompt": prompt,
        "prompt_version_value": prompt_version_value,
        "request_schema": schemas["request"],
    }
    local = run_local_progression(response_schema=schemas["local"], **common)
    global_order = run_global_order(
        structure=structure, response_schema=schemas["global"], **common
    )
    spine = run_spine_connectivity(
        structure=structure, response_schema=schemas["spine"], **common
    )
    example = run_example_integration(
        structure=structure, response_schema=schemas["example"], **common
    )
    closure = run_closure(
        structure=structure, response_schema=schemas["closure"], **common
    )
    groups = [local, global_order, spine, example, closure]
    summaries = {group[0]["probe"]: group[0] for group in groups}
    audits = [audit for group in groups for audit in group[1]]
    events = [evt for group in groups for evt in group[2]]
    return summaries, audits, events


def run_pipeline(
    *,
    book_card: Mapping[str, Any],
    discourse_card: Mapping[str, Any],
    cognitive_aggregate: Mapping[str, Any],
    submission_text: str,
    submission_id: str,
    rollout_index: int,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    prompts: Mapping[str, str],
    prompt_versions: Mapping[str, str],
    schemas: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    submission_sha256 = sha256_bytes(submission_text.encode("utf-8"))
    panel = select_panel(discourse_card, rollout_index)
    relation_outcomes = read_relation_outcomes(cognitive_aggregate)
    edge_results, edge_events = run_authorial_panel(
        card=discourse_card,
        panel=panel,
        book_card=book_card,
        relation_outcomes=relation_outcomes,
        submission_text=submission_text,
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        prompts=prompts,
        prompt_versions=prompt_versions,
        schemas=schemas,
    )
    authorial_score, authorial_strata = aggregate_authorial_edges(edge_results, panel)

    structure, structure_events, structure_error = run_structure_extractor(
        card=discourse_card,
        book_id=book_card["book_id"],
        submission_text=submission_text,
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        provider_config=provider_config,
        provider=provider,
        prompt=prompts["structure"],
        prompt_version_value=prompt_versions["structure"],
        response_schema=schemas["structure"],
        request_schema=schemas["request"],
    )
    if structure is None:
        summaries = {
            name: {"probe": name, "status": "unscorable", "score": None}
            for name in (
                "local_progression",
                "global_order",
                "spine_connectivity",
                "example_integration",
                "closure",
            )
        }
        editorial_audits = [
            {
                "probe": "structure_extraction",
                "probe_id": "EDITORIAL-STRUCTURE",
                "status": "unscorable",
                "score": None,
                "reason": structure_error,
            }
        ]
        editorial_events: list[dict[str, Any]] = []
        structure_output: dict[str, Any] = {
            "status": "unscorable",
            "reason": structure_error,
        }
    else:
        summaries, editorial_audits, editorial_events = run_editorial(
            card=discourse_card,
            structure=structure,
            book_id=book_card["book_id"],
            submission_text=submission_text,
            submission_id=submission_id,
            submission_sha256=submission_sha256,
            provider_config=provider_config,
            provider=provider,
            prompt=prompts["editorial"],
            prompt_version_value=prompt_versions["editorial"],
            schemas=schemas,
        )
        structure_output = {"status": "complete", **structure}

    editorial = aggregate_editorial(
        summaries, discourse_card["editorial_probe_config"]["weights"]
    )
    aggregate = aggregate_discourse(
        book_id=book_card["book_id"],
        submission_id=submission_id,
        panel_id=panel["id"],
        authorial_score=authorial_score,
        authorial_strata=authorial_strata,
        editorial=editorial,
        dimension_weights=discourse_card["dimension_weights"],
    )
    aggregate_errors = schema_validation_errors(
        aggregate, schemas["aggregate"], "discourse_aggregate"
    )
    if aggregate_errors:
        raise RuntimeValidationError(aggregate_errors)
    return {
        "edge_results": edge_results,
        "structure": structure_output,
        "editorial_summaries": summaries,
        "editorial_audits": editorial_audits,
        "events": edge_events + structure_events + editorial_events,
        "aggregate": aggregate,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Authorial Edge and Editorial Coherence semantic evaluation."
    )
    parser.add_argument("--book-card", type=Path, required=True)
    parser.add_argument("--discourse-card", type=Path, required=True)
    parser.add_argument("--cognitive-aggregate", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--rollout-index", type=int, default=1)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-draft-card", action="store_true")
    parser.add_argument("--book-schema", type=Path, default=DEFAULT_BOOK_SCHEMA)
    parser.add_argument("--discourse-schema", type=Path, default=DEFAULT_DISCOURSE_SCHEMA)
    parser.add_argument("--provider-schema", type=Path, default=DEFAULT_PROVIDER_SCHEMA)
    parser.add_argument("--request-schema", type=Path, default=DEFAULT_REQUEST_SCHEMA)
    parser.add_argument("--locator-response-schema", type=Path, default=DEFAULT_LOCATOR_RESPONSE_SCHEMA)
    parser.add_argument("--edge-judge-schema", type=Path, default=DEFAULT_EDGE_JUDGE_SCHEMA)
    parser.add_argument("--structure-schema", type=Path, default=DEFAULT_STRUCTURE_SCHEMA)
    parser.add_argument("--local-schema", type=Path, default=DEFAULT_LOCAL_SCHEMA)
    parser.add_argument("--global-schema", type=Path, default=DEFAULT_GLOBAL_SCHEMA)
    parser.add_argument("--spine-schema", type=Path, default=DEFAULT_SPINE_SCHEMA)
    parser.add_argument("--example-schema", type=Path, default=DEFAULT_EXAMPLE_SCHEMA)
    parser.add_argument("--closure-schema", type=Path, default=DEFAULT_CLOSURE_SCHEMA)
    parser.add_argument("--aggregate-schema", type=Path, default=DEFAULT_AGGREGATE_SCHEMA)
    parser.add_argument("--edge-locator-prompt", type=Path, default=DEFAULT_EDGE_LOCATOR_PROMPT)
    parser.add_argument("--edge-judge-prompt", type=Path, default=DEFAULT_EDGE_JUDGE_PROMPT)
    parser.add_argument("--structure-prompt", type=Path, default=DEFAULT_STRUCTURE_PROMPT)
    parser.add_argument("--editorial-prompt", type=Path, default=DEFAULT_EDITORIAL_PROMPT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        book_card = load_json_object(args.book_card)
        discourse_card = load_json_object(args.discourse_card)
        cognitive = load_json_object(args.cognitive_aggregate)
        submission_text = read_text(args.submission)

        errors = schema_validation_errors(
            book_card, load_json_object(args.book_schema), "book_card"
        )
        errors.extend(validate_book_cross_references(book_card))
        errors.extend(
            schema_validation_errors(
                discourse_card,
                load_json_object(args.discourse_schema),
                "discourse_card",
            )
        )
        errors.extend(
            validate_discourse_cross_references(
                discourse_card, book_card, args.book_card
            )
        )
        if (
            book_card.get("status") == "draft" or discourse_card.get("status") == "draft"
        ) and not args.allow_draft_card:
            errors.append("draft Book/Discourse Card requires explicit --allow-draft-card")
        if cognitive.get("status") != "complete":
            errors.append("cognitive aggregate must be complete before discourse scoring")
        if cognitive.get("book_id") != book_card.get("book_id"):
            errors.append("cognitive aggregate book_id mismatch")
        if cognitive.get("submission_id") != args.submission_id:
            errors.append("cognitive aggregate submission_id mismatch")
        if errors:
            raise RuntimeValidationError(errors)

        provider_config = load_json_object(args.provider_config)
        config_errors = schema_validation_errors(
            provider_config,
            load_json_object(args.provider_schema),
            "provider_config",
        )
        if config_errors:
            raise RuntimeValidationError(config_errors)
        provider = CommandProvider(
            provider_config["command"],
            provider_config["model_id"],
            provider_config["timeout_seconds"],
        )
        prompts = {
            "edge_locator": read_text(args.edge_locator_prompt),
            "edge_judge": read_text(args.edge_judge_prompt),
            "structure": read_text(args.structure_prompt),
            "editorial": read_text(args.editorial_prompt),
        }
        versions = {
            "edge_locator": prompt_version("authorial-edge-locator-v1", args.edge_locator_prompt),
            "edge_judge": prompt_version("authorial-edge-judge-v1", args.edge_judge_prompt),
            "structure": prompt_version("structure-extractor-v1", args.structure_prompt),
            "editorial": prompt_version("editorial-probes-v1", args.editorial_prompt),
        }
        schemas = {
            "request": load_json_object(args.request_schema),
            "locator": load_json_object(args.locator_response_schema),
            "edge_judge": load_json_object(args.edge_judge_schema),
            "structure": load_json_object(args.structure_schema),
            "local": load_json_object(args.local_schema),
            "global": load_json_object(args.global_schema),
            "spine": load_json_object(args.spine_schema),
            "example": load_json_object(args.example_schema),
            "closure": load_json_object(args.closure_schema),
            "aggregate": load_json_object(args.aggregate_schema),
        }
        result = run_pipeline(
            book_card=book_card,
            discourse_card=discourse_card,
            cognitive_aggregate=cognitive,
            submission_text=submission_text,
            submission_id=args.submission_id,
            rollout_index=args.rollout_index,
            provider_config=provider_config,
            provider=provider,
            prompts=prompts,
            prompt_versions=versions,
            schemas=schemas,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(args.output_dir / "authorial-edge-results.jsonl", result["edge_results"])
        write_json(args.output_dir / "discourse-structure.json", result["structure"])
        write_jsonl(
            args.output_dir / "editorial-probe-results.jsonl",
            [*result["editorial_summaries"].values(), *result["editorial_audits"]],
        )
        write_jsonl(args.output_dir / "discourse-events.jsonl", result["events"])
        write_json(args.output_dir / "discourse-aggregate.json", result["aggregate"])
        write_json(
            args.output_dir / "discourse-runtime-status.json",
            {
                "schema_version": "1.0",
                "status": result["aggregate"]["status"],
                "book_id": book_card["book_id"],
                "submission_id": args.submission_id,
                "model_id": provider.model_id,
                "rollout_index": args.rollout_index,
                "source_context_mode": "book_card_summaries_development_only",
                "provider_config_sha256": hashlib.sha256(
                    args.provider_config.read_bytes()
                ).hexdigest(),
            },
        )
    except (OSError, UnicodeDecodeError, RuntimeValidationError) as exc:
        print("Discourse semantic runtime failed:", file=sys.stderr)
        if isinstance(exc, RuntimeValidationError):
            for error in exc.errors:
                print(f"- {error}", file=sys.stderr)
        else:
            print(f"- {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": result["aggregate"]["status"],
                "panel_id": result["aggregate"]["panel_id"],
                "output_dir": str(args.output_dir.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["aggregate"]["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
