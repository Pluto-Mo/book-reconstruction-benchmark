#!/usr/bin/env python3

"""Build the frozen five-model Harbor job without importing personal secrets.

The repository contains only non-sensitive Pi provider definitions and Harbor
secret names. Hosted runs select organization-scoped stored secrets. Local runs
require an explicit, repository-external secret file and never inspect the
user's Pi auth store or provider environment automatically.
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
    ("GPT-5.6 sol", "openai-benchmark", "gpt-5.6-sol", "OPENAI_BENCHMARK_API_KEY"),
    ("Opus 5", "openai-benchmark", "claude-opus-5", "OPENAI_BENCHMARK_API_KEY"),
    ("Qwen 3.8 Max", "qwen-benchmark", "qwen3.8-max", "QWEN_BENCHMARK_API_KEY"),
    ("K3", "kimi-benchmark", "kimi-k3", "KIMI_BENCHMARK_API_KEY"),
    ("DS V4 Pro", "deepseek", "deepseek-v4-pro", "DEEPSEEK_API_KEY"),
)
APPROVED_JUDGE_ROUTE = (
    "Qwen 3.8 Max",
    "qwen-benchmark",
    "qwen3.8-max",
    "QWEN_BENCHMARK_API_KEY",
)


class MatrixConfigError(ValueError):
    """The frozen matrix, provider config, or secret contract is invalid."""


@dataclass(frozen=True)
class ResolvedRoute:
    label: str
    provider: str
    model: str
    secret_name: str
    base_url: str
    provider_document: dict[str, Any]
    fingerprint: str
    graded_reasoning_effort: bool

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
    compat = provider_config.get("compat")
    explicitly_graded = (
        isinstance(compat, Mapping) and compat.get("supportsReasoningEffort") is True
    )
    deepseek_graded = provider == "deepseek" and urlparse(base_url).hostname == "api.deepseek.com"
    return ResolvedRoute(
        label=label,
        provider=provider,
        model=model,
        secret_name=secret_name,
        base_url=base_url,
        provider_document={"providers": {provider: selected_provider}},
        fingerprint=hashlib.sha256(public_bytes).hexdigest(),
        graded_reasoning_effort=explicitly_graded or deepseek_graded,
    )


def resolve_matrix(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], list[ResolvedRoute], ResolvedRoute, Path]:
    manifest = load_json_object(manifest_path)
    if manifest.get("schema_version") != "2.0":
        raise MatrixConfigError("Pi matrix schema_version must be 2.0")
    pi_config = manifest.get("pi")
    if not isinstance(pi_config, Mapping):
        raise MatrixConfigError("manifest pi must be an object")
    if pi_config.get("harbor_thinking") != "xhigh":
        raise MatrixConfigError("Harbor-native Pi must use its highest xhigh setting")
    if pi_config.get("thinking_policy") != "highest_available":
        raise MatrixConfigError("Pi thinking policy must be highest_available")
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
    )
    if actual_judge != APPROVED_JUDGE_ROUTE:
        raise MatrixConfigError("judge route must remain Qwen 3.8 Max")
    judge = resolve_route(judge_config, providers)
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
    hosted: bool = False,
    hosted_task_name: str | None = None,
    hosted_task_ref: str | None = None,
) -> dict[str, Any]:
    job_config = manifest.get("job")
    pi_config = manifest.get("pi")
    judge_config = manifest.get("judge")
    hosted_config = manifest.get("hosted")
    if not all(
        isinstance(value, Mapping)
        for value in (job_config, pi_config, judge_config, hosted_config)
    ):
        raise MatrixConfigError("manifest job, pi, judge, and hosted must be objects")

    version = _required_string(pi_config.get("version"), "Pi version")
    thinking = _required_string(pi_config.get("harbor_thinking"), "Pi thinking")
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
            "kwargs": {"version": version, "thinking": thinking},
            "env": {
                "PI_CODING_AGENT_DIR": config_dir,
                "PI_OFFLINE": "1",
                route.secret_name: "${" + route.secret_name + "}",
            },
            "extra_allowed_hosts": [route.host],
        }
        if hosted:
            # Every trial's separate verifier uses the fixed Qwen judge.
            agent["secrets"] = sorted({route.secret_name, judge.secret_name})
        agents.append(agent)

    if hosted:
        if not hosted_task_name or "/" not in hosted_task_name:
            raise MatrixConfigError(
                "hosted config requires a published task name in org/name form"
            )
        task: dict[str, Any] = {"name": hosted_task_name}
        if hosted_task_ref:
            task["ref"] = hosted_task_ref
    else:
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
            }
        },
    }
    if hosted:
        if hosted_config.get("credential_mode") != "direct":
            raise MatrixConfigError("hosted credential_mode must be direct")
        job["credential_mode"] = "direct"
    else:
        job["jobs_dir"] = str((repo_root / "jobs").resolve())
    return job


def sanitized_status(
    manifest: Mapping[str, Any],
    routes: list[ResolvedRoute],
    judge: ResolvedRoute,
    models_path: Path,
) -> dict[str, Any]:
    pi_config = manifest["pi"]
    return {
        "status": "configuration_ready",
        "paid_model_calls_started": False,
        "personal_pi_auth_read": False,
        "native_harbor_agent": "pi",
        "provider_config": str(models_path),
        "thinking": {
            "policy": pi_config["thinking_policy"],
            "harbor_native_flag": pi_config["harbor_thinking"],
            "deepseek_effective_effort": "max",
            "other_routes": "highest mode exposed by each frozen provider record",
        },
        "agents": [
            {
                "label": route.label,
                "model": f"{route.provider}/{route.model}",
                "endpoint_host": route.host,
                "secret_name": route.secret_name,
                "graded_reasoning_effort": route.graded_reasoning_effort,
                "route_fingerprint": route.fingerprint,
            }
            for route in routes
        ],
        "judge": {
            "model": f"{judge.provider}/{judge.model}",
            "endpoint_host": judge.host,
            "secret_name": judge.secret_name,
            "thinking_enabled": True,
        },
        "required_harbor_stored_secrets": list(required_secret_names(routes, judge)),
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
    mode.add_argument("--write-hosted-config", type=Path, metavar="PATH")
    mode.add_argument("--run", action="store_true", help="run locally with an external secret file")
    mode.add_argument("--launch", action="store_true", help="launch with Harbor stored secrets")
    parser.add_argument("--secrets-file", type=Path)
    parser.add_argument("--hosted-task", help="published Harbor task in org/name form")
    parser.add_argument("--hosted-task-ref", help="published task tag, revision, or digest")
    parser.add_argument("--org", help="Harbor organization for hosted launch")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest, routes, judge, models_path = resolve_matrix(
            manifest_path=args.manifest.resolve(), repo_root=REPO_ROOT
        )
        secret_names = required_secret_names(routes, judge)

        if not any(
            (args.print_config, args.write_config, args.write_hosted_config, args.run, args.launch)
        ):
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

        if args.write_hosted_config or args.launch:
            hosted_job = build_job(
                manifest=manifest,
                routes=routes,
                judge=judge,
                hosted=True,
                hosted_task_name=args.hosted_task,
                hosted_task_ref=args.hosted_task_ref,
            )
            if args.write_hosted_config:
                _write_json(args.write_hosted_config.resolve(), hosted_job)
                return 0
            if not args.org:
                raise MatrixConfigError("--launch requires --org")
            with tempfile.TemporaryDirectory(prefix="brb-pi-hosted-") as temporary_dir:
                config_path = Path(temporary_dir) / "job.json"
                _write_json(config_path, hosted_job)
                completed = subprocess.run(
                    [
                        "harbor",
                        "job",
                        "start",
                        "--config",
                        str(config_path),
                        "--launch",
                        "--org",
                        args.org,
                    ],
                    cwd=REPO_ROOT,
                    check=False,
                )
                return completed.returncode

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
