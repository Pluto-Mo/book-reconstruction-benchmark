#!/usr/bin/env python3

"""Build and run the frozen five-model benchmark on local Harbor.

The GitHub-safe repository contains only non-sensitive Pi provider definitions
and runtime credential names. A paid local run requires an explicit secret file
outside the repository and never inspects the user's Pi auth store or provider
environment automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "configs/pi-five-models.json"
NATIVE_PI_IMPORT_PATH = "harbor.agents.installed.pi:Pi"
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
SENSITIVE_ENV_PATTERN = re.compile(
    r"(?:API_KEY|(?:^|_)KEY(?:_|$)|TOKEN|SECRET|OAUTH|PASSWORD|PASSWD|CREDENTIAL|(?:^|_)PAT(?:_|$))",
    re.IGNORECASE,
)
PREFLIGHT_SECRET = "__HARBOR_CONFIG_PREFLIGHT_ONLY__"

APPROVED_AGENT_ROUTES = (
    (
        "GPT-5.6 sol",
        "openai-benchmark",
        "gpt-5.6-sol",
        "OPENAI_BENCHMARK_API_KEY",
        "high",
        "provider_managed",
    ),
    (
        "Opus 5",
        "openai-benchmark",
        "claude-opus-5",
        "OPENAI_BENCHMARK_API_KEY",
        "high",
        "provider_managed",
    ),
    (
        "Qwen 3.8 Max",
        "qwen-benchmark",
        "qwen3.8-max",
        "QWEN_BENCHMARK_API_KEY",
        "high",
        "boolean_plus_reasoning_effort_high",
    ),
    (
        "K3",
        "kimi-benchmark",
        "kimi-k3",
        "KIMI_BENCHMARK_API_KEY",
        "high",
        "provider_managed",
    ),
    (
        "DS V4 Pro",
        "deepseek",
        "deepseek-v4-pro",
        "DEEPSEEK_API_KEY",
        "xhigh",
        "graded_reasoning_effort_max",
    ),
)
APPROVED_JUDGE_ROUTE = (
    "Qwen 3.8 Max",
    "qwen-benchmark",
    "qwen3.8-max",
    "QWEN_BENCHMARK_API_KEY",
    "boolean_plus_reasoning_effort_high",
)


class MatrixConfigError(ValueError):
    """The frozen matrix, provider config, or secret contract is invalid."""


@dataclass(frozen=True)
class ResolvedRoute:
    label: str
    provider: str
    model: str
    secret_name: str
    pi_thinking: str
    thinking_control: str
    base_url: str
    provider_document: dict[str, Any]
    fingerprint: str

    @property
    def host(self) -> str:
        return urlparse(self.base_url).hostname or ""


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MatrixConfigError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise MatrixConfigError(f"expected JSON object: {path}")
    return value


def _inside_repository(path: Path, *, repo_root: Path = REPO_ROOT) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MatrixConfigError(f"{label} must be a non-empty string")
    return value.strip()


def _selected_model(models: Any, model_id: str) -> dict[str, Any]:
    if not isinstance(models, list):
        raise MatrixConfigError("provider models must be an array")
    matches = [
        dict(model)
        for model in models
        if isinstance(model, Mapping) and model.get("id") == model_id
    ]
    if len(matches) != 1:
        raise MatrixConfigError(f"expected exactly one model named {model_id}")
    return matches[0]


def resolve_route(
    route_config: Mapping[str, Any],
    providers: Mapping[str, Any],
) -> ResolvedRoute:
    label = _required_string(route_config.get("label"), "route label")
    provider = _required_string(route_config.get("provider"), f"route {label} provider")
    model = _required_string(route_config.get("model"), f"route {label} model")
    secret_name = _required_string(
        route_config.get("secret_name"), f"route {label} secret_name"
    )
    pi_thinking = _required_string(
        route_config.get("pi_thinking"), f"route {label} pi_thinking"
    )
    thinking_control = _required_string(
        route_config.get("thinking_control"), f"route {label} thinking_control"
    )
    if ENV_NAME_PATTERN.fullmatch(secret_name) is None:
        raise MatrixConfigError(f"route {label} has invalid secret name {secret_name}")

    raw_provider = providers.get(provider)
    if not isinstance(raw_provider, Mapping):
        raise MatrixConfigError(f"provider {provider} is absent from frozen models.json")
    provider_config = dict(raw_provider)
    base_url = _required_string(provider_config.get("baseUrl"), f"provider {provider} baseUrl")
    if not base_url.startswith(("https://", "http://")) or not urlparse(base_url).hostname:
        raise MatrixConfigError(f"provider {provider} has no usable base URL")
    if "todo" in base_url.casefold() or "placeholder" in base_url.casefold():
        raise MatrixConfigError(f"provider {provider} still uses a placeholder base URL")
    if provider_config.get("api") != "openai-completions":
        raise MatrixConfigError(f"provider {provider} must use Pi openai-completions")

    expected_reference = "${" + secret_name + "}"
    if provider_config.get("apiKey") != expected_reference:
        raise MatrixConfigError(
            f"provider {provider} apiKey must be the Harbor secret reference "
            f"{expected_reference}"
        )
    if any(key.casefold() in {"oauth", "token", "auth"} for key in provider_config):
        raise MatrixConfigError(f"provider {provider} contains a forbidden auth field")

    selected_model = _selected_model(provider_config.get("models"), model)
    if selected_model.get("reasoning") is not True:
        raise MatrixConfigError(f"model {provider}/{model} must enable reasoning")
    selected_provider = dict(provider_config)
    selected_provider["models"] = [selected_model]
    public_bytes = json.dumps(
        selected_provider, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    provider_compat = provider_config.get("compat")
    model_compat = selected_model.get("compat")
    compat = {
        **(dict(provider_compat) if isinstance(provider_compat, Mapping) else {}),
        **(dict(model_compat) if isinstance(model_compat, Mapping) else {}),
    }
    thinking_format = compat.get("thinkingFormat")
    supports_effort = compat.get("supportsReasoningEffort")
    if thinking_control == "provider_managed":
        if pi_thinking != "high" or supports_effort is not False:
            raise MatrixConfigError(
                f"route {label} provider-managed thinking requires high and "
                "supportsReasoningEffort=false"
            )
    elif thinking_control == "boolean_plus_reasoning_effort_high":
        if (
            pi_thinking != "high"
            or thinking_format != "qwen"
            or supports_effort is False
        ):
            raise MatrixConfigError(
                f"route {label} Qwen thinking requires Pi high, thinkingFormat=qwen, "
                "and reasoning-effort support"
            )
    elif thinking_control == "graded_reasoning_effort_max":
        thinking_map = selected_model.get("thinkingLevelMap")
        if (
            pi_thinking != "xhigh"
            or provider != "deepseek"
            or urlparse(base_url).hostname != "api.deepseek.com"
            or thinking_format != "deepseek"
            or not isinstance(thinking_map, Mapping)
            or thinking_map.get("max") != "max"
        ):
            raise MatrixConfigError(
                f"route {label} graded max thinking does not match the official DeepSeek contract"
            )
    else:
        raise MatrixConfigError(f"route {label} has unsupported thinking_control")
    return ResolvedRoute(
        label=label,
        provider=provider,
        model=model,
        secret_name=secret_name,
        pi_thinking=pi_thinking,
        thinking_control=thinking_control,
        base_url=base_url,
        provider_document={"providers": {provider: selected_provider}},
        fingerprint=hashlib.sha256(public_bytes).hexdigest(),
    )


def resolve_matrix(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], list[ResolvedRoute], ResolvedRoute, Path]:
    manifest = load_json_object(manifest_path)
    if manifest.get("schema_version") != "2.1":
        raise MatrixConfigError("Pi matrix schema_version must be 2.1")
    pi_config = manifest.get("pi")
    if not isinstance(pi_config, Mapping):
        raise MatrixConfigError("manifest pi must be an object")
    _required_string(pi_config.get("version"), "Pi version")
    models_relative = _required_string(pi_config.get("models_path"), "Pi models_path")
    models_path = (repo_root / models_relative).resolve()
    if not _inside_repository(models_path, repo_root=repo_root):
        raise MatrixConfigError("Pi models_path must remain inside the repository")
    models_document = load_json_object(models_path)
    providers = models_document.get("providers")
    if not isinstance(providers, Mapping):
        raise MatrixConfigError("frozen models.json has no providers object")

    route_configs = manifest.get("agents")
    if not isinstance(route_configs, list) or len(route_configs) != 5:
        raise MatrixConfigError("manifest must define exactly five agent routes")
    if not all(isinstance(route, Mapping) for route in route_configs):
        raise MatrixConfigError("every agent route must be an object")
    actual_routes = tuple(
        (
            route.get("label"),
            route.get("provider"),
            route.get("model"),
            route.get("secret_name"),
            route.get("pi_thinking"),
            route.get("thinking_control"),
        )
        for route in route_configs
    )
    if actual_routes != APPROVED_AGENT_ROUTES:
        raise MatrixConfigError("manifest agent routes differ from the approved five-model matrix")
    routes = [resolve_route(route, providers) for route in route_configs]

    judge_config = manifest.get("judge")
    if not isinstance(judge_config, Mapping):
        raise MatrixConfigError("manifest judge must be an object")
    actual_judge = (
        judge_config.get("label"),
        judge_config.get("provider"),
        judge_config.get("model"),
        judge_config.get("secret_name"),
        judge_config.get("thinking_control"),
    )
    if actual_judge != APPROVED_JUDGE_ROUTE:
        raise MatrixConfigError("judge route must remain Qwen 3.8 Max")
    judge_route_config = dict(judge_config)
    judge_route_config["pi_thinking"] = "high"
    judge = resolve_route(judge_route_config, providers)
    if judge_config.get("enable_thinking") is not True:
        raise MatrixConfigError("Qwen judge thinking must be enabled")
    _required_string(judge_config.get("litellm_model"), "judge LiteLLM model")
    return manifest, routes, judge, models_path


def required_secret_names(
    routes: list[ResolvedRoute], judge: ResolvedRoute
) -> tuple[str, ...]:
    return tuple(sorted({judge.secret_name, *(route.secret_name for route in routes)}))


def build_job(
    *,
    manifest: Mapping[str, Any],
    routes: list[ResolvedRoute],
    judge: ResolvedRoute,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    job_config = manifest.get("job")
    pi_config = manifest.get("pi")
    judge_config = manifest.get("judge")
    if not all(
        isinstance(value, Mapping)
        for value in (job_config, pi_config, judge_config)
    ):
        raise MatrixConfigError("manifest job, pi, and judge must be objects")

    version = _required_string(pi_config.get("version"), "Pi version")
    config_dir = _required_string(
        pi_config.get("container_config_dir"), "Pi container_config_dir"
    )
    if not config_dir.startswith("/"):
        raise MatrixConfigError("Pi container_config_dir must be absolute")

    agents: list[dict[str, Any]] = []
    for route in routes:
        agent: dict[str, Any] = {
            "import_path": NATIVE_PI_IMPORT_PATH,
            "model_name": f"{route.provider}/{route.model}",
            "kwargs": {"version": version, "thinking": route.pi_thinking},
            "env": {
                "PI_CODING_AGENT_DIR": config_dir,
                "PI_OFFLINE": "1",
                route.secret_name: "${" + route.secret_name + "}",
            },
            "extra_allowed_hosts": [route.host],
        }
        agents.append(agent)

    task_path_value = _required_string(job_config.get("task_path"), "job task_path")
    task_path = (repo_root / task_path_value).resolve()
    if not _inside_repository(task_path, repo_root=repo_root):
        raise MatrixConfigError("local task path must remain inside the repository")
    task = {"path": str(task_path)}

    setup_hosts = manifest.get("setup_allowed_hosts")
    if not isinstance(setup_hosts, list) or not all(
        isinstance(host, str) and host for host in setup_hosts
    ):
        raise MatrixConfigError("setup_allowed_hosts must be a non-empty string array")
    litellm_model = _required_string(
        judge_config.get("litellm_model"), "judge LiteLLM model"
    )
    job: dict[str, Any] = {
        "job_name": job_config.get("name"),
        "n_attempts": job_config.get("n_attempts", 1),
        "n_concurrent_trials": job_config.get("n_concurrent_trials", 1),
        "environment": {"extra_allowed_hosts": sorted(set(setup_hosts))},
        "agents": agents,
        "tasks": [task],
        "verifier": {
            "env": {
                "BENCHMARK_JUDGE_MODEL": litellm_model,
                "BENCHMARK_JUDGE_API_KEY": "${" + judge.secret_name + "}",
                "BENCHMARK_JUDGE_BASE_URL": judge.base_url,
                "BENCHMARK_JUDGE_ENABLE_THINKING": "true",
                "BENCHMARK_JUDGE_REASONING_EFFORT": "high",
            }
        },
        "jobs_dir": str((repo_root / "jobs").resolve()),
    }
    return job


def sanitized_status(
    manifest: Mapping[str, Any],
    routes: list[ResolvedRoute],
    judge: ResolvedRoute,
    models_path: Path,
) -> dict[str, Any]:
    effects = {
        "provider_managed": "Pi emits no thinking/effort field; provider default applies",
        "boolean_plus_reasoning_effort_high": (
            "Pi emits enable_thinking=true + reasoning_effort=high"
        ),
        "graded_reasoning_effort_max": (
            "Pi clamps xhigh to model max and emits thinking enabled + reasoning_effort=max"
        ),
    }
    return {
        "status": "configuration_ready",
        "paid_model_calls_started": False,
        "personal_pi_auth_read": False,
        "native_harbor_agent": "pi",
        "provider_config": str(models_path),
        "thinking_policy": "declared_per_route_and_translated_by_pi",
        "agents": [
            {
                "label": route.label,
                "model": f"{route.provider}/{route.model}",
                "endpoint_host": route.host,
                "secret_name": route.secret_name,
                "pi_thinking": route.pi_thinking,
                "thinking_control": route.thinking_control,
                "effective_request": effects[route.thinking_control],
                "route_fingerprint": route.fingerprint,
            }
            for route in routes
        ],
        "judge": {
            "model": f"{judge.provider}/{judge.model}",
            "endpoint_host": judge.host,
            "secret_name": judge.secret_name,
            "thinking_enabled": True,
            "thinking_control": judge.thinking_control,
            "effective_request": (
                "adapter emits enable_thinking=true + reasoning_effort=high"
            ),
        },
        "required_local_runtime_credentials": list(required_secret_names(routes, judge)),
    }


def read_external_secret_file(
    path: Path,
    required_names: tuple[str, ...],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, str]:
    resolved = path.expanduser().resolve()
    if _inside_repository(resolved, repo_root=repo_root):
        raise MatrixConfigError("local secret file must be outside the repository")
    try:
        file_mode = resolved.stat().st_mode
    except OSError as exc:
        raise MatrixConfigError(f"cannot stat local secret file: {resolved}") from exc
    if file_mode & 0o077:
        raise MatrixConfigError("local secret file permissions must be 0600 or stricter")
    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise MatrixConfigError(f"cannot read local secret file: {resolved}") from exc

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MatrixConfigError(f"invalid secret assignment on line {line_number}")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name not in required_names:
            raise MatrixConfigError(f"unexpected secret name {name} on line {line_number}")
        if name in values:
            raise MatrixConfigError(f"duplicate secret name {name}")
        if not value:
            raise MatrixConfigError(f"secret {name} is empty")
        values[name] = value
    missing = sorted(set(required_names) - set(values))
    if missing:
        raise MatrixConfigError("local secret file is missing: " + ", ".join(missing))
    return values


def isolated_local_environment(secret_values: Mapping[str, str]) -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if SENSITIVE_ENV_PATTERN.search(name) is None
    }
    environment.update(secret_values)
    return environment


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--print-config", action="store_true")
    mode.add_argument("--write-config", type=Path, metavar="PATH")
    mode.add_argument("--run", action="store_true", help="run locally with an external secret file")
    parser.add_argument("--secrets-file", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest, routes, judge, models_path = resolve_matrix(
            manifest_path=args.manifest.resolve(), repo_root=REPO_ROOT
        )
        secret_names = required_secret_names(routes, judge)

        if not any((args.print_config, args.write_config, args.run)):
            print(
                json.dumps(
                    sanitized_status(manifest, routes, judge, models_path),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        if args.secrets_file is not None and not args.run:
            raise MatrixConfigError("--secrets-file is accepted only with --run")

        local_job = build_job(manifest=manifest, routes=routes, judge=judge)
        if args.write_config:
            _write_json(args.write_config.resolve(), local_job)
            return 0

        if args.run:
            if args.secrets_file is None:
                raise MatrixConfigError(
                    "--run requires --secrets-file outside the repository; personal Pi auth is never used"
                )
            secret_values = read_external_secret_file(args.secrets_file, secret_names)
            child_env = isolated_local_environment(secret_values)
        else:
            child_env = isolated_local_environment(
                {name: PREFLIGHT_SECRET for name in secret_names}
            )

        with tempfile.TemporaryDirectory(prefix="brb-pi-local-") as temporary_dir:
            config_path = Path(temporary_dir) / "job.json"
            _write_json(config_path, local_job)
            command = ["harbor", "run", "--config", str(config_path)]
            if args.print_config:
                command.append("--print-config")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                env=child_env,
                check=False,
            )
            return completed.returncode
    except MatrixConfigError as exc:
        print(f"Pi benchmark preflight failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
