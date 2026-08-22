# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

"""Provider-neutral semantic Locator and relation Judge runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

from runtime_scoring import (
    REPO_ROOT,
    RuntimeValidationError,
    load_json_object,
    load_jsonl_objects,
    schema_validation_errors,
    score_adjudication_bundle,
    validate_cognitive_aggregate,
    validate_judge_result,
)
from validate_book_card import validate_cross_references

DEFAULT_BOOK_SCHEMA = REPO_ROOT / "schemas/book-card.schema.json"
DEFAULT_CRITERION_SCHEMA = REPO_ROOT / "schemas/cognitive-criterion.schema.json"
DEFAULT_REQUEST_SCHEMA = REPO_ROOT / "schemas/model-request.schema.json"
DEFAULT_LOCATOR_RESPONSE_SCHEMA = (
    REPO_ROOT / "schemas/locator-model-response.schema.json"
)
DEFAULT_JUDGE_RESPONSE_SCHEMA = REPO_ROOT / "schemas/judge-model-response.schema.json"
DEFAULT_PROVIDER_CONFIG_SCHEMA = (
    REPO_ROOT / "schemas/cognitive-provider-config.schema.json"
)
DEFAULT_LOCATOR_PROMPT = REPO_ROOT / "prompts/cognitive/locator-v1.md"
DEFAULT_JUDGE_PROMPT = REPO_ROOT / "prompts/cognitive/judge-v1.md"

LOCATOR_FORBIDDEN_KEYS = {
    "pass_if",
    "fail_if",
    "common_false_positives",
    "contradiction_patterns",
    "review_policy",
    "prompt_versions",
    "weight",
    "critical",
    "source_anchor_ids",
    "paths",
}


class ProviderError(RuntimeError):
    """The adapter failed before returning a valid response object."""


class StructuredProvider(Protocol):
    model_id: str

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Return one parsed response object for one structured request."""


class CommandProvider:
    """One-shot JSON stdin/stdout adapter.

    The configured command receives exactly one model request as JSON on stdin
    and must emit exactly one JSON object on stdout. Provider logs belong on
    stderr. The command is executed without a shell and inherits verifier
    environment variables, including credentials.
    """

    def __init__(
        self, command: Sequence[str], model_id: str, timeout_seconds: float
    ) -> None:
        self.command = list(command)
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        try:
            completed = subprocess.run(
                self.command,
                input=payload,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(
                f"provider timed out after {self.timeout_seconds} seconds"
            ) from exc
        except OSError as exc:
            raise ProviderError(f"provider command could not start: {exc}") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stderr_digest = sha256_bytes(stderr.encode()) if stderr else "none"
            raise ProviderError(
                f"provider exited {completed.returncode}; "
                f"stderr_sha256={stderr_digest}; stderr_chars={len(stderr)}"
            )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"provider stdout is not one JSON object: {exc.msg}"
            ) from exc
        if not isinstance(response, dict):
            raise ProviderError("provider stdout must decode to a JSON object")
        return response


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeValidationError(f"file not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise RuntimeValidationError(f"invalid UTF-8 {path}: {exc}") from exc


def all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key)
            keys.update(all_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(all_keys(item))
    return keys


def locator_relation_view(criterion: Mapping[str, Any]) -> dict[str, Any]:
    relation = criterion["relation"]
    view = {
        "relation_type": relation["relation_type"],
        "requirement": relation["requirement"],
        "required_facets": relation["required_facets"],
        "source_nodes": relation["source_nodes"],
        "target_nodes": relation["target_nodes"],
        "acceptable_paraphrases": relation["acceptable_paraphrases"],
    }
    leaked = all_keys(view).intersection(LOCATOR_FORBIDDEN_KEYS)
    if leaked:
        raise RuntimeValidationError(
            f"locator relation view leaked forbidden keys {sorted(leaked)!r}"
        )
    return view


def make_request(
    *,
    stage: str,
    attempt: int,
    model_id: str,
    generation_parameters: Mapping[str, Any],
    system_prompt: str,
    user_payload: Mapping[str, Any],
    response_schema: Mapping[str, Any],
    book_id: str,
    submission_id: str,
    submission_sha256: str,
    criterion_id: str,
    prompt_version: str,
    request_schema: Mapping[str, Any],
) -> dict[str, Any]:
    request_without_id = {
        "schema_version": "1.0",
        "stage": stage,
        "attempt": attempt,
        "model_id": model_id,
        "generation_parameters": dict(generation_parameters),
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    user_payload, ensure_ascii=False, indent=2, sort_keys=True
                ),
            },
        ],
        "response_schema": dict(response_schema),
        "metadata": {
            "book_id": book_id,
            "submission_id": submission_id,
            "submission_sha256": submission_sha256,
            "criterion_id": criterion_id,
            "prompt_version": prompt_version,
        },
    }
    request = {
        **request_without_id,
        "request_id": sha256_bytes(stable_json_bytes(request_without_id)),
    }
    errors = schema_validation_errors(request, request_schema, "model_request")
    if errors:
        raise RuntimeValidationError(errors)
    return request


def locator_request(
    criterion: Mapping[str, Any],
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    attempt: int,
    provider_config: Mapping[str, Any],
    system_prompt: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> dict[str, Any]:
    mode = "initial" if attempt == 1 else "full_text_review"
    payload = {
        "mode": mode,
        "relation": locator_relation_view(criterion),
        "submission_text": submission_text,
    }
    return make_request(
        stage="evidence_locator",
        attempt=attempt,
        model_id=provider_config["model_id"],
        generation_parameters=provider_config["generation_parameters"][
            "evidence_locator"
        ],
        system_prompt=system_prompt,
        user_payload=payload,
        response_schema=response_schema,
        book_id=criterion["book_id"],
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        criterion_id=criterion["criterion_id"],
        prompt_version=criterion["prompt_versions"]["locator"],
        request_schema=request_schema,
    )


def judge_request(
    criterion: Mapping[str, Any],
    evidence: Mapping[str, Any],
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    attempt: int,
    provider_config: Mapping[str, Any],
    system_prompt: str,
    response_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "mode": "initial" if attempt == 1 else "protocol_retry",
        "relation": criterion["relation"],
        "evidence_candidates": evidence["candidates"],
        "submission_text": submission_text,
    }
    return make_request(
        stage="relation_adjudicator",
        attempt=attempt,
        model_id=provider_config["model_id"],
        generation_parameters=provider_config["generation_parameters"][
            "relation_adjudicator"
        ],
        system_prompt=system_prompt,
        user_payload=payload,
        response_schema=response_schema,
        book_id=criterion["book_id"],
        submission_id=submission_id,
        submission_sha256=submission_sha256,
        criterion_id=criterion["criterion_id"],
        prompt_version=criterion["prompt_versions"]["judge"],
        request_schema=request_schema,
    )


def response_errors(
    response: Mapping[str, Any],
    response_schema: Mapping[str, Any],
    label: str,
) -> list[str]:
    return schema_validation_errors(response, response_schema, label)


def quote_occurrences(text: str, quote: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = text.find(quote, start)
        if position < 0:
            break
        positions.append(position)
        start = position + 1
    return positions


def resolve_locator_quotes(
    response: Mapping[str, Any],
    submission_text: str,
    criterion_id: str,
    context_chars: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()
    errors: list[str] = []

    for index, item in enumerate(response["quotes"], start=1):
        quote = item["quote"]
        positions = quote_occurrences(submission_text, quote)
        context_before = item.get("context_before")
        context_after = item.get("context_after")

        if context_before is not None:
            positions = [
                position
                for position in positions
                if position >= len(context_before)
                and submission_text[position - len(context_before) : position]
                == context_before
            ]
        if context_after is not None:
            positions = [
                position
                for position in positions
                if submission_text[
                    position + len(quote) : position + len(quote) + len(context_after)
                ]
                == context_after
            ]

        if not positions:
            errors.append(
                f"quote {index} is not an exact substring with the supplied context"
            )
            continue
        if len(positions) > 1:
            errors.append(
                f"quote {index} is ambiguous at {len(positions)} positions; "
                "supply adjacent context"
            )
            continue

        start = positions[0]
        end = start + len(quote)
        span = (start, end)
        if span in seen_spans:
            errors.append(f"quote {index} duplicates an earlier candidate span")
            continue
        seen_spans.add(span)
        candidate_hash = sha256_bytes(
            f"{criterion_id}\0{start}\0{end}\0{quote}".encode()
        )[:16]
        candidates.append(
            {
                "candidate_id": f"C-{candidate_hash}",
                "quote": quote,
                "start_char": start,
                "end_char": end,
                "context_before": submission_text[
                    max(0, start - context_chars) : start
                ],
                "context_after": submission_text[end : end + context_chars],
            }
        )

    if errors:
        raise RuntimeValidationError(errors)
    return candidates


def evidence_result_id(book_id: str, submission_id: str, criterion_id: str) -> str:
    digest = sha256_bytes(f"{book_id}\0{submission_id}\0{criterion_id}".encode())[:20]
    return f"E-{digest}"


def event(
    request: Mapping[str, Any],
    status: str,
    *,
    detail: str | None = None,
) -> dict[str, Any]:
    result = {
        "schema_version": "1.0",
        "request_id": request["request_id"],
        "stage": request["stage"],
        "criterion_id": request["metadata"]["criterion_id"],
        "attempt": request["attempt"],
        "status": status,
    }
    if detail:
        result["detail"] = detail
    return result


def run_locator(
    criterion: Mapping[str, Any],
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    system_prompt: str,
    request_schema: Mapping[str, Any],
    response_schema: Mapping[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    last_error = ""
    max_attempts = provider_config["max_protocol_attempts"]
    for attempt in range(1, max_attempts + 1):
        request = locator_request(
            criterion,
            submission_text,
            submission_id,
            submission_sha256,
            attempt,
            provider_config,
            system_prompt,
            response_schema,
            request_schema,
        )
        try:
            response = provider.complete(request)
        except ProviderError as exc:
            last_error = str(exc)
            events.append(event(request, "provider_error", detail=last_error))
            continue

        errors = response_errors(
            response,
            response_schema,
            f"locator response {criterion['criterion_id']}",
        )
        if errors:
            last_error = "; ".join(errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue
        if response["status"] == "none":
            events.append(event(request, "none"))
            if attempt < max_attempts:
                continue
            return {
                "schema_version": "1.0",
                "evidence_result_id": evidence_result_id(
                    criterion["book_id"],
                    submission_id,
                    criterion["criterion_id"],
                ),
                "book_id": criterion["book_id"],
                "submission_id": submission_id,
                "criterion_id": criterion["criterion_id"],
                "status": "none",
                "candidates": [],
                "attempts": attempt,
                "locator_model": provider.model_id,
                "prompt_version": criterion["prompt_versions"]["locator"],
                "notes": response.get(
                    "notes", "No evidence after frozen full-text review."
                ),
            }

        try:
            candidates = resolve_locator_quotes(
                response,
                submission_text,
                criterion["criterion_id"],
                provider_config["locator_context_chars"],
            )
        except RuntimeValidationError as exc:
            last_error = "; ".join(exc.errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue
        events.append(event(request, "found"))
        return {
            "schema_version": "1.0",
            "evidence_result_id": evidence_result_id(
                criterion["book_id"],
                submission_id,
                criterion["criterion_id"],
            ),
            "book_id": criterion["book_id"],
            "submission_id": submission_id,
            "criterion_id": criterion["criterion_id"],
            "status": "found",
            "candidates": candidates,
            "attempts": attempt,
            "locator_model": provider.model_id,
            "prompt_version": criterion["prompt_versions"]["locator"],
            "notes": response.get("notes", f"Evidence resolved on attempt {attempt}."),
        }

    return {
        "schema_version": "1.0",
        "evidence_result_id": evidence_result_id(
            criterion["book_id"], submission_id, criterion["criterion_id"]
        ),
        "book_id": criterion["book_id"],
        "submission_id": submission_id,
        "criterion_id": criterion["criterion_id"],
        "status": "locator_error",
        "candidates": [],
        "attempts": max_attempts,
        "locator_model": provider.model_id,
        "prompt_version": criterion["prompt_versions"]["locator"],
        "notes": f"Locator provider/protocol failure: {last_error or 'unknown error'}",
    }


def none_evidence_judgment(
    criterion: Mapping[str, Any],
    evidence: Mapping[str, Any],
    submission_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "book_id": criterion["book_id"],
        "submission_id": submission_id,
        "criterion_id": criterion["criterion_id"],
        "evidence_result_id": evidence["evidence_result_id"],
        "selected_candidate_ids": [],
        "decision": "fail",
        "support_found": False,
        "contradiction_found": False,
        "missing_facets": list(criterion["relation"]["required_facets"]),
        "reason": (
            "Frozen retry and full-text review found no submission evidence for "
            "this relation."
        ),
        "confidence": 1.0,
        "judge_model": "deterministic-none-policy",
        "prompt_version": "none-after-two-attempts-v1",
    }


def abstain_judgment(
    criterion: Mapping[str, Any],
    evidence: Mapping[str, Any],
    submission_id: str,
    provider: StructuredProvider,
    detail: str,
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "book_id": criterion["book_id"],
        "submission_id": submission_id,
        "criterion_id": criterion["criterion_id"],
        "evidence_result_id": evidence["evidence_result_id"],
        "selected_candidate_ids": [],
        "decision": "abstain",
        "support_found": False,
        "contradiction_found": False,
        "missing_facets": [],
        "reason": f"Judge provider/protocol failure: {detail}",
        "confidence": 0.0,
        "judge_model": provider.model_id,
        "prompt_version": criterion["prompt_versions"]["judge"],
    }


def normalize_judge_response(
    response: Mapping[str, Any],
    criterion: Mapping[str, Any],
    evidence: Mapping[str, Any],
    submission_id: str,
    provider: StructuredProvider,
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "book_id": criterion["book_id"],
        "submission_id": submission_id,
        "criterion_id": criterion["criterion_id"],
        "evidence_result_id": evidence["evidence_result_id"],
        "selected_candidate_ids": list(response["selected_candidate_ids"]),
        "decision": response["decision"],
        "support_found": response["support_found"],
        "contradiction_found": response["contradiction_found"],
        "missing_facets": list(response["missing_facets"]),
        "reason": response["reason"],
        "confidence": response["confidence"],
        "judge_model": provider.model_id,
        "prompt_version": criterion["prompt_versions"]["judge"],
    }


def run_judge(
    criterion: Mapping[str, Any],
    evidence: Mapping[str, Any],
    submission_text: str,
    submission_id: str,
    submission_sha256: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    system_prompt: str,
    request_schema: Mapping[str, Any],
    response_schema: Mapping[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if evidence["status"] == "locator_error":
        return None
    if evidence["status"] == "none":
        return none_evidence_judgment(criterion, evidence, submission_id)

    last_error = ""
    max_attempts = provider_config["max_protocol_attempts"]
    for attempt in range(1, max_attempts + 1):
        request = judge_request(
            criterion,
            evidence,
            submission_text,
            submission_id,
            submission_sha256,
            attempt,
            provider_config,
            system_prompt,
            response_schema,
            request_schema,
        )
        try:
            response = provider.complete(request)
        except ProviderError as exc:
            last_error = str(exc)
            events.append(event(request, "provider_error", detail=last_error))
            continue

        errors = response_errors(
            response,
            response_schema,
            f"judge response {criterion['criterion_id']}",
        )
        if errors:
            last_error = "; ".join(errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue

        normalized = normalize_judge_response(
            response, criterion, evidence, submission_id, provider
        )
        relation_stub = {
            "id": criterion["criterion_id"],
            "required_facets": criterion["relation"]["required_facets"],
        }
        try:
            validate_judge_result(normalized, evidence, relation_stub)
        except RuntimeValidationError as exc:
            last_error = "; ".join(exc.errors)
            events.append(event(request, "protocol_error", detail=last_error))
            continue
        events.append(event(request, normalized["decision"]))
        return normalized

    return abstain_judgment(
        criterion,
        evidence,
        submission_id,
        provider,
        last_error or "unknown error",
    )


def validate_criteria_set(
    criteria: Sequence[Mapping[str, Any]],
    book_card: Mapping[str, Any],
    criterion_schema: Mapping[str, Any],
) -> None:
    errors: list[str] = []
    criteria_by_id: dict[str, Mapping[str, Any]] = {}
    for criterion in criteria:
        criterion_id = criterion.get("criterion_id", "<missing>")
        errors.extend(
            schema_validation_errors(
                criterion, criterion_schema, f"criterion {criterion_id}"
            )
        )
        if criterion_id in criteria_by_id:
            errors.append(f"duplicate criterion_id {criterion_id!r}")
        criteria_by_id[str(criterion_id)] = criterion
        if criterion.get("book_id") != book_card.get("book_id"):
            errors.append(f"criterion {criterion_id}: book_id mismatch")

    relation_ids = {
        relation["id"]
        for structure in book_card["cognitive_structures"]
        for relation in structure["relations"]
    }
    criterion_ids = set(criteria_by_id)
    if missing := relation_ids - criterion_ids:
        errors.append(f"criteria missing relation IDs {sorted(missing)!r}")
    if extra := criterion_ids - relation_ids:
        errors.append(f"criteria contain unknown relation IDs {sorted(extra)!r}")
    if errors:
        raise RuntimeValidationError(errors)


def run_semantic_pipeline(
    *,
    book_card: Mapping[str, Any],
    criteria: Sequence[Mapping[str, Any]],
    submission_text: str,
    submission_id: str,
    provider_config: Mapping[str, Any],
    provider: StructuredProvider,
    locator_prompt_text: str,
    judge_prompt_text: str,
    criterion_schema: Mapping[str, Any],
    request_schema: Mapping[str, Any],
    locator_response_schema: Mapping[str, Any],
    judge_response_schema: Mapping[str, Any],
) -> dict[str, Any]:
    validate_criteria_set(criteria, book_card, criterion_schema)
    submission_sha256 = sha256_bytes(submission_text.encode("utf-8"))

    def process_criterion(
        criterion: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
        local_events: list[dict[str, Any]] = []
        evidence = run_locator(
            criterion,
            submission_text,
            submission_id,
            submission_sha256,
            provider_config,
            provider,
            locator_prompt_text,
            request_schema,
            locator_response_schema,
            local_events,
        )
        judge = run_judge(
            criterion,
            evidence,
            submission_text,
            submission_id,
            submission_sha256,
            provider_config,
            provider,
            judge_prompt_text,
            request_schema,
            judge_response_schema,
            local_events,
        )
        return evidence, judge, local_events

    max_workers = provider_config["max_concurrency"]
    if max_workers == 1:
        processed = [process_criterion(criterion) for criterion in criteria]
    else:
        with ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cognitive-semantic"
        ) as executor:
            processed = list(executor.map(process_criterion, criteria))

    evidence_results = [item[0] for item in processed]
    judge_results = [item[1] for item in processed if item[1] is not None]
    events = [event_item for item in processed for event_item in item[2]]

    aggregate = score_adjudication_bundle(
        book_card,
        submission_text,
        submission_id,
        evidence_results,
        judge_results,
    )
    validate_cognitive_aggregate(aggregate)
    return {
        "evidence_results": evidence_results,
        "judge_results": judge_results,
        "events": events,
        "aggregate": aggregate,
    }


def verify_manifest(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    criteria_path: Path,
    book_card_path: Path,
    criterion_schema_path: Path,
    locator_prompt_path: Path,
    judge_prompt_path: Path,
    criteria: Sequence[Mapping[str, Any]],
) -> None:
    errors: list[str] = []
    if manifest.get("book_card_sha256") != sha256_bytes(book_card_path.read_bytes()):
        errors.append(f"{manifest_path}: book_card_sha256 mismatch")
    if manifest.get("criteria_sha256") != sha256_bytes(criteria_path.read_bytes()):
        errors.append(f"{manifest_path}: criteria_sha256 mismatch")
    if manifest.get("criterion_count") != len(criteria):
        errors.append(f"{manifest_path}: criterion_count mismatch")
    if manifest.get("criterion_schema_sha256") != sha256_bytes(
        criterion_schema_path.read_bytes()
    ):
        errors.append(f"{manifest_path}: criterion_schema_sha256 mismatch")
    expected_prompt_versions = {
        "locator": (
            f"locator-v1-{sha256_bytes(locator_prompt_path.read_bytes())[:12]}"
        ),
        "judge": f"judge-v1-{sha256_bytes(judge_prompt_path.read_bytes())[:12]}",
    }
    if manifest.get("prompt_versions") != expected_prompt_versions:
        errors.append(f"{manifest_path}: prompt_versions mismatch")
    for criterion in criteria:
        if criterion.get("prompt_versions") != expected_prompt_versions:
            errors.append(
                f"criterion {criterion.get('criterion_id')}: prompt_versions "
                "do not match current prompt files"
            )
    if errors:
        raise RuntimeValidationError(errors)


def write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    rendered = "\n".join(
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for record in records
    )
    path.write_text(rendered + ("\n" if records else ""), encoding="utf-8")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run provider-neutral semantic evidence location and narrow relation "
            "judging, then invoke the deterministic cognitive aggregator."
        )
    )
    parser.add_argument("--book-card", type=Path, required=True)
    parser.add_argument("--book-schema", type=Path, default=DEFAULT_BOOK_SCHEMA)
    parser.add_argument("--criteria", type=Path, required=True)
    parser.add_argument("--criteria-manifest", type=Path, required=True)
    parser.add_argument(
        "--criterion-schema", type=Path, default=DEFAULT_CRITERION_SCHEMA
    )
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument(
        "--provider-config-schema",
        type=Path,
        default=DEFAULT_PROVIDER_CONFIG_SCHEMA,
    )
    parser.add_argument("--request-schema", type=Path, default=DEFAULT_REQUEST_SCHEMA)
    parser.add_argument(
        "--locator-response-schema",
        type=Path,
        default=DEFAULT_LOCATOR_RESPONSE_SCHEMA,
    )
    parser.add_argument(
        "--judge-response-schema",
        type=Path,
        default=DEFAULT_JUDGE_RESPONSE_SCHEMA,
    )
    parser.add_argument("--locator-prompt", type=Path, default=DEFAULT_LOCATOR_PROMPT)
    parser.add_argument("--judge-prompt", type=Path, default=DEFAULT_JUDGE_PROMPT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-draft-card", action="store_true")
    args = parser.parse_args()

    try:
        book_card = load_json_object(args.book_card)
        book_errors = schema_validation_errors(
            book_card, load_json_object(args.book_schema), "book_card"
        )
        book_errors.extend(validate_cross_references(book_card))
        if book_card.get("status") == "draft" and not args.allow_draft_card:
            book_errors.append("draft Book Card requires explicit --allow-draft-card")
        if book_errors:
            raise RuntimeValidationError(book_errors)

        criteria = load_jsonl_objects(args.criteria)
        criterion_schema = load_json_object(args.criterion_schema)
        validate_criteria_set(criteria, book_card, criterion_schema)
        manifest = load_json_object(args.criteria_manifest)
        verify_manifest(
            manifest,
            args.criteria_manifest,
            args.criteria,
            args.book_card,
            args.criterion_schema,
            args.locator_prompt,
            args.judge_prompt,
            criteria,
        )

        provider_config = load_json_object(args.provider_config)
        config_errors = schema_validation_errors(
            provider_config,
            load_json_object(args.provider_config_schema),
            "provider_config",
        )
        if config_errors:
            raise RuntimeValidationError(config_errors)
        provider = CommandProvider(
            provider_config["command"],
            provider_config["model_id"],
            provider_config["timeout_seconds"],
        )

        result = run_semantic_pipeline(
            book_card=book_card,
            criteria=criteria,
            submission_text=read_text(args.submission),
            submission_id=args.submission_id,
            provider_config=provider_config,
            provider=provider,
            locator_prompt_text=read_text(args.locator_prompt),
            judge_prompt_text=read_text(args.judge_prompt),
            criterion_schema=criterion_schema,
            request_schema=load_json_object(args.request_schema),
            locator_response_schema=load_json_object(args.locator_response_schema),
            judge_response_schema=load_json_object(args.judge_response_schema),
        )

        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(
            args.output_dir / "evidence-results.jsonl",
            result["evidence_results"],
        )
        write_jsonl(args.output_dir / "judge-results.jsonl", result["judge_results"])
        write_jsonl(args.output_dir / "semantic-events.jsonl", result["events"])
        write_json(args.output_dir / "cognitive-aggregate.json", result["aggregate"])
        status = {
            "schema_version": "1.0",
            "status": result["aggregate"]["status"],
            "book_id": book_card["book_id"],
            "submission_id": args.submission_id,
            "provider_type": provider_config["provider_type"],
            "model_id": provider_config["model_id"],
            "provider_config_sha256": sha256_bytes(args.provider_config.read_bytes()),
            "criteria_sha256": sha256_bytes(args.criteria.read_bytes()),
        }
        write_json(args.output_dir / "semantic-runtime-status.json", status)
    except (OSError, UnicodeDecodeError, RuntimeValidationError) as exc:
        print("Cognitive semantic runtime failed:", file=sys.stderr)
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
                "relations": result["aggregate"]["relation_counts"]["total"],
                "output_dir": str(args.output_dir.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["aggregate"]["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
