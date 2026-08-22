#!/usr/bin/env python3

"""Native Harbor verifier for the development book-reconstruction task."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from count_submission_chars import build_result

DEFAULT_TESTS_ROOT = Path("/tests")
DEFAULT_SUBMISSION = Path("/app/submission.md")
DEFAULT_OUTPUT_DIR = Path("/logs/verifier")


class VerifierInfrastructureError(RuntimeError):
    """The verifier could not produce a trustworthy model score."""


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerifierInfrastructureError(f"cannot read JSON object {path}") from exc
    if not isinstance(value, dict):
        raise VerifierInfrastructureError(f"expected a JSON object in {path}")
    return value


DISCOURSE_METRICS = (
    "authorial_edge_recovery",
    "local_progression",
    "global_order",
    "spine_connectivity",
    "example_integration",
    "closure",
    "editorial_coherence",
    "discourse_reconstruction",
)


def development_reward(
    *,
    cognitive_relation_coverage: float,
    complete_core_path_rate: float,
    hard_constraints: float,
    discourse_metrics: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Build numeric-only Harbor output without freezing a final V1 scalar."""

    values: dict[str, float] = {
        "cognitive_relation_coverage": cognitive_relation_coverage,
        "complete_core_path_rate": complete_core_path_rate,
        "hard_constraints": hard_constraints,
    }
    if discourse_metrics is None:
        values.update({name: 0.0 for name in DISCOURSE_METRICS})
    else:
        missing = sorted(set(DISCOURSE_METRICS) - set(discourse_metrics))
        if missing:
            raise VerifierInfrastructureError(
                f"missing discourse reward metrics {missing!r}"
            )
        values.update({name: discourse_metrics[name] for name in DISCOURSE_METRICS})
    for label, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise VerifierInfrastructureError(f"{label} is not numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise VerifierInfrastructureError(f"{label} is outside [0, 1]")
    return {
        # Development compatibility field only. The cross-dimension leaderboard
        # scalar remains unfrozen until the discourse runtime is calibrated.
        "reward": float(cognitive_relation_coverage) * float(hard_constraints),
        "cognitive_relation_coverage": float(cognitive_relation_coverage),
        "complete_core_path_rate": float(complete_core_path_rate),
        "hard_constraints": float(hard_constraints),
        **{name: float(values[name]) for name in DISCOURSE_METRICS},
    }


def resolved_provider_config(
    template_path: Path,
    output_path: Path,
    model_environment_variable: str,
) -> dict[str, Any]:
    config = read_json_object(template_path)
    model_id = os.environ.get(model_environment_variable, "").strip()
    if not model_id and model_environment_variable == "BENCHMARK_JUDGE_MODEL":
        # Transitional compatibility for older local run commands.  The native
        # verifier is unchanged; only the misleading legacy variable name moves.
        model_id = os.environ.get("REWARDKIT_JUDGE", "").strip()
    if not model_id:
        raise VerifierInfrastructureError(
            f"missing verifier environment variable {model_environment_variable}"
        )
    config["model_id"] = model_id
    write_json(output_path, config)
    return config


def submission_id(submission_bytes: bytes) -> str:
    explicit = os.environ.get("HARBOR_TRIAL_ID", "").strip()
    if explicit:
        return explicit
    digest = hashlib.sha256(submission_bytes).hexdigest()
    return f"submission-{digest[:16]}"


def hard_constraint_failure(
    output_dir: Path,
    details: Mapping[str, Any],
) -> int:
    write_json(
        output_dir / "reward.json",
        development_reward(
            cognitive_relation_coverage=0.0,
            complete_core_path_rate=0.0,
            hard_constraints=0.0,
        ),
    )
    write_json(
        output_dir / "reward-details.json",
        {
            "schema_version": "development-book-reconstruction-v1",
            "status": "hard_constraint_failed",
            "development_scope": "cognitive_and_discourse",
            "details": dict(details),
        },
    )
    write_json(
        output_dir / "verifier-status.json",
        {
            "schema_version": "1.0",
            "status": "complete",
            "score_status": "hard_constraint_failed",
        },
    )
    return 0


def build_cognitive_runtime_command(
    args: argparse.Namespace, provider_config: Path
) -> list[str]:
    command = [
        sys.executable,
        str(args.runtime_script),
        "--book-card",
        str(args.book_card),
        "--criteria",
        str(args.criteria),
        "--criteria-manifest",
        str(args.criteria_manifest),
        "--submission",
        str(args.submission),
        "--submission-id",
        args.submission_id,
        "--provider-config",
        str(provider_config),
        "--output-dir",
        str(args.output_dir),
    ]
    if args.allow_draft_card:
        command.append("--allow-draft-card")
    return command


def build_discourse_runtime_command(
    args: argparse.Namespace, provider_config: Path
) -> list[str]:
    command = [
        sys.executable,
        str(args.discourse_runtime_script),
        "--book-card",
        str(args.book_card),
        "--discourse-card",
        str(args.discourse_card),
        "--cognitive-aggregate",
        str(args.output_dir / "cognitive-aggregate.json"),
        "--submission",
        str(args.submission),
        "--submission-id",
        args.submission_id,
        "--rollout-index",
        str(args.rollout_index),
        "--provider-config",
        str(provider_config),
        "--output-dir",
        str(args.output_dir),
    ]
    if args.allow_draft_card:
        command.append("--allow-draft-card")
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run cognitive and discourse pipelines as a native Harbor verifier."
    )
    parser.add_argument("--tests-root", type=Path, default=DEFAULT_TESTS_ROOT)
    parser.add_argument("--submission", type=Path, default=DEFAULT_SUBMISSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-chars", type=int, default=6000)
    parser.add_argument("--max-chars", type=int, default=8000)
    parser.add_argument("--allow-draft-card", action="store_true")
    parser.add_argument("--judge-model-env", default="BENCHMARK_JUDGE_MODEL")
    parser.add_argument("--rollout-index", type=int, default=1)
    args = parser.parse_args(argv)

    args.runtime_script = args.tests_root / "scripts/cognitive_semantic_runtime.py"
    args.discourse_runtime_script = (
        args.tests_root / "scripts/discourse_semantic_runtime.py"
    )
    args.book_card = args.tests_root / "gold/book_card.json"
    args.discourse_card = args.tests_root / "gold/discourse_card.json"
    args.criteria = args.tests_root / "gold/cognitive_criteria.jsonl"
    args.criteria_manifest = args.tests_root / "gold/cognitive_criteria.manifest.json"
    args.provider_template = args.tests_root / "cognitive-provider.json"
    if args.min_chars < 0 or args.max_chars < 0:
        parser.error("character bounds must be non-negative")
    if args.min_chars > args.max_chars:
        parser.error("--min-chars cannot exceed --max-chars")
    return args


def run_verifier(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        submission_bytes = args.submission.read_bytes()
    except OSError as exc:
        return hard_constraint_failure(
            args.output_dir,
            {
                "reason": "submission_missing_or_unreadable",
                "error_type": type(exc).__name__,
            },
        )
    try:
        submission_text = submission_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return hard_constraint_failure(
            args.output_dir,
            {"reason": "submission_not_utf8", "error_type": type(exc).__name__},
        )

    constraint_result = build_result(
        args.submission,
        submission_text,
        args.min_chars,
        args.max_chars,
    )
    write_json(args.output_dir / "hard-constraints.json", constraint_result)
    if constraint_result["within_bounds"] is False:
        return hard_constraint_failure(args.output_dir, constraint_result)

    args.submission_id = submission_id(submission_bytes)
    resolved_config_path = args.output_dir / "cognitive-provider.resolved.json"
    try:
        provider_config = resolved_provider_config(
            args.provider_template,
            resolved_config_path,
            args.judge_model_env,
        )
        command = build_cognitive_runtime_command(args, resolved_config_path)
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
        (args.output_dir / "cognitive-runtime.stdout.log").write_text(
            completed.stdout, encoding="utf-8"
        )
        (args.output_dir / "cognitive-runtime.stderr.log").write_text(
            completed.stderr, encoding="utf-8"
        )
        aggregate = read_json_object(args.output_dir / "cognitive-aggregate.json")
        if completed.returncode != 0 or aggregate.get("status") != "complete":
            raise VerifierInfrastructureError(
                "cognitive semantic runtime was unscorable or failed"
            )

        metrics = aggregate.get("metrics")
        if not isinstance(metrics, Mapping):
            raise VerifierInfrastructureError("aggregate metrics are missing")
        discourse_command = build_discourse_runtime_command(
            args, resolved_config_path
        )
        discourse_completed = subprocess.run(
            discourse_command,
            text=True,
            capture_output=True,
            check=False,
        )
        (args.output_dir / "discourse-runtime.stdout.log").write_text(
            discourse_completed.stdout, encoding="utf-8"
        )
        (args.output_dir / "discourse-runtime.stderr.log").write_text(
            discourse_completed.stderr, encoding="utf-8"
        )
        discourse_aggregate = read_json_object(
            args.output_dir / "discourse-aggregate.json"
        )
        if (
            discourse_completed.returncode != 0
            or discourse_aggregate.get("status") != "complete"
        ):
            raise VerifierInfrastructureError(
                "discourse semantic runtime was unscorable or failed"
            )
        editorial = discourse_aggregate.get("editorial")
        if not isinstance(editorial, Mapping):
            raise VerifierInfrastructureError("editorial metrics are missing")
        reward = development_reward(
            cognitive_relation_coverage=metrics.get("cognitive_relation_coverage"),
            complete_core_path_rate=metrics.get("complete_core_path_rate"),
            hard_constraints=1.0,
            discourse_metrics={
                "authorial_edge_recovery": discourse_aggregate.get(
                    "authorial_edge_recovery"
                ),
                "local_progression": editorial.get("local_progression"),
                "global_order": editorial.get("global_order"),
                "spine_connectivity": editorial.get("spine_connectivity"),
                "example_integration": editorial.get("example_integration"),
                "closure": editorial.get("closure"),
                "editorial_coherence": editorial.get("editorial_coherence"),
                "discourse_reconstruction": discourse_aggregate.get(
                    "discourse_reconstruction"
                ),
            },
        )
        write_json(args.output_dir / "reward.json", reward)
        write_json(
            args.output_dir / "reward-details.json",
            {
                "schema_version": "development-book-reconstruction-v1",
                "status": "complete",
                "development_scope": "cognitive_and_discourse",
                "discourse_runtime_status": "complete",
                "scalar_policy": (
                    "temporary reward = cognitive_relation_coverage; not a frozen "
                    "cross-dimension leaderboard formula"
                ),
                "judge_model": provider_config["model_id"],
                "book_card_status": "draft" if args.allow_draft_card else "frozen",
                "submission_id": args.submission_id,
                "aggregate": aggregate,
                "discourse_aggregate": discourse_aggregate,
            },
        )
        write_json(
            args.output_dir / "verifier-status.json",
            {
                "schema_version": "1.0",
                "status": "complete",
                "score_status": "development_full_runtime",
            },
        )
    except (OSError, VerifierInfrastructureError) as exc:
        write_json(
            args.output_dir / "verifier-status.json",
            {
                "schema_version": "1.0",
                "status": "unscorable",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )
        print(f"Verifier infrastructure failure: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_verifier(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
