#!/usr/bin/env python3

"""LiteLLM bridge for the benchmark's provider-neutral semantic protocol.

The adapter reads one provider-neutral model request from stdin and writes one
parsed JSON object to stdout. It deliberately owns no retries and no scoring;
those remain frozen in the task-specific cognitive/discourse runtimes.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any


class AdapterProtocolError(ValueError):
    """The command input or provider response violated the adapter protocol."""


def _required_mapping(
    value: Mapping[str, Any], key: str, label: str
) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise AdapterProtocolError(f"{label}.{key} must be an object")
    return item


def _enabled(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"1", "true", "yes", "on"}


def build_completion_kwargs(
    request: Mapping[str, Any],
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Map one frozen model request to LiteLLM completion arguments."""

    model_id = request.get("model_id")
    stage = request.get("stage")
    messages = request.get("messages")
    if not isinstance(model_id, str) or not model_id:
        raise AdapterProtocolError("model_id must be a non-empty string")
    if not isinstance(stage, str) or not stage:
        raise AdapterProtocolError("stage must be a non-empty string")
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        raise AdapterProtocolError("messages must be an array")
    if not all(isinstance(message, Mapping) for message in messages):
        raise AdapterProtocolError("every message must be an object")

    generation = _required_mapping(request, "generation_parameters", "request")
    response_schema = _required_mapping(request, "response_schema", "request")
    max_output_tokens = generation.get("max_output_tokens")
    if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool):
        raise AdapterProtocolError(
            "generation_parameters.max_output_tokens must be an integer"
        )

    schema_name = f"book_reconstruction_{stage}"
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": [dict(message) for message in messages],
        "temperature": generation.get("temperature"),
        "top_p": generation.get("top_p"),
        "max_tokens": max_output_tokens,
        "seed": generation.get("seed"),
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": dict(response_schema),
            },
        },
        # The semantic runtime owns the exactly-two-attempt policy.
        "num_retries": 0,
        # LiteLLM may remove parameters unsupported by a selected provider while
        # preserving the structured-output request when that provider supports it.
        "drop_params": True,
    }
    runtime_env = os.environ if environment is None else environment
    api_key = runtime_env.get("BENCHMARK_JUDGE_API_KEY", "").strip()
    api_base = runtime_env.get("BENCHMARK_JUDGE_BASE_URL", "").strip()
    if bool(api_key) != bool(api_base):
        raise AdapterProtocolError(
            "BENCHMARK_JUDGE_API_KEY and BENCHMARK_JUDGE_BASE_URL must be set together"
        )
    if api_key:
        kwargs["api_key"] = api_key
        kwargs["api_base"] = api_base
    thinking_enabled = _enabled(runtime_env.get("BENCHMARK_JUDGE_ENABLE_THINKING"))
    reasoning_effort = runtime_env.get(
        "BENCHMARK_JUDGE_REASONING_EFFORT", ""
    ).strip()
    if reasoning_effort and reasoning_effort not in {"high", "max"}:
        raise AdapterProtocolError(
            "BENCHMARK_JUDGE_REASONING_EFFORT must be high or max"
        )
    if reasoning_effort and not thinking_enabled:
        raise AdapterProtocolError(
            "BENCHMARK_JUDGE_REASONING_EFFORT requires thinking to be enabled"
        )
    if thinking_enabled:
        # The Qwen OpenAI-compatible protocol uses a boolean thinking switch;
        kwargs["extra_body"] = {"enable_thinking": True}
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
    return kwargs


def _response_content(response: Any) -> Any:
    if isinstance(response, Mapping):
        choices = response.get("choices")
    else:
        choices = getattr(response, "choices", None)
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        raise AdapterProtocolError("provider response has no choices array")
    if not choices:
        raise AdapterProtocolError("provider response choices array is empty")

    choice = choices[0]
    message = (
        choice.get("message")
        if isinstance(choice, Mapping)
        else getattr(choice, "message", None)
    )
    if isinstance(message, Mapping):
        return message.get("content")
    return getattr(message, "content", None)


def parse_response_object(response: Any) -> dict[str, Any]:
    """Extract exactly one JSON object from a LiteLLM response."""

    content = _response_content(response)
    if isinstance(content, Mapping):
        return dict(content)
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        text_blocks: list[str] = []
        for block in content:
            if not isinstance(block, Mapping):
                continue
            text = block.get("text")
            if isinstance(text, str):
                text_blocks.append(text)
        content = "".join(text_blocks)
    if not isinstance(content, str) or not content.strip():
        raise AdapterProtocolError("provider response has no textual JSON content")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AdapterProtocolError("provider content is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise AdapterProtocolError("provider content must decode to one JSON object")
    return parsed


def call_litellm(request: Mapping[str, Any]) -> dict[str, Any]:
    """Call the provider selected by the frozen LiteLLM model identifier."""

    try:
        import litellm
    except ImportError as exc:  # pragma: no cover - exercised in verifier image
        raise RuntimeError("litellm is not installed") from exc

    litellm.suppress_debug_info = True
    response = litellm.completion(**build_completion_kwargs(request))
    return parse_response_object(response)


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise AdapterProtocolError("stdin must contain one JSON object")
        response = call_litellm(request)
    except AdapterProtocolError as exc:
        print(f"adapter protocol error: {exc}", file=sys.stderr)
        return 2
    # Provider exception classes differ across LiteLLM backends. The adapter is
    # a process boundary, so every provider failure must become a nonzero exit.
    except Exception as exc:  # noqa: BLE001
        print(f"provider call failed: {type(exc).__name__}", file=sys.stderr)
        return 3

    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
