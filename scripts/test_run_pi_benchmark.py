from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from run_pi_benchmark import (
    APPROVED_AGENT_ROUTES,
    DEFAULT_MANIFEST,
    MatrixConfigError,
    NATIVE_PI_IMPORT_PATH,
    REPO_ROOT,
    build_job,
    isolated_local_environment,
    read_external_secret_file,
    required_secret_names,
    resolve_matrix,
    resolve_route,
    sanitized_status,
)


class RunPiBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest, self.routes, self.judge, self.models_path = resolve_matrix(
            manifest_path=DEFAULT_MANIFEST,
            repo_root=REPO_ROOT,
        )

    def test_resolves_only_the_approved_routes_without_personal_auth(self) -> None:
        actual = tuple(
            (route.label, route.provider, route.model, route.secret_name)
            for route in self.routes
        )
        self.assertEqual(actual, APPROVED_AGENT_ROUTES)
        self.assertEqual(self.routes[-1].base_url, "https://api.deepseek.com")
        self.assertEqual(self.routes[-1].host, "api.deepseek.com")
        self.assertTrue(self.routes[-1].graded_reasoning_effort)
        status = sanitized_status(
            self.manifest, self.routes, self.judge, self.models_path
        )
        self.assertFalse(status["personal_pi_auth_read"])
        self.assertFalse(status["paid_model_calls_started"])

    def test_frozen_models_contain_only_named_secret_references(self) -> None:
        document = json.loads(self.models_path.read_text(encoding="utf-8"))
        providers = document["providers"]
        expected = {
            "openai-benchmark": "${OPENAI_BENCHMARK_API_KEY}",
            "qwen-benchmark": "${QWEN_BENCHMARK_API_KEY}",
            "kimi-benchmark": "${KIMI_BENCHMARK_API_KEY}",
            "deepseek": "${DEEPSEEK_API_KEY}",
        }
        self.assertEqual(
            {name: provider["apiKey"] for name, provider in providers.items()},
            expected,
        )
        serialized = json.dumps(document, ensure_ascii=False).casefold()
        self.assertNotIn("opencode-go", serialized)
        self.assertNotIn('"oauth"', serialized)
        self.assertNotIn('"auth"', serialized)

    def test_rejects_raw_key_or_oauth_field_in_provider_config(self) -> None:
        providers = {
            "openai-benchmark": {
                "baseUrl": "https://benchmark.example/v1",
                "api": "openai-completions",
                "apiKey": "raw-secret",
                "oauth": "forbidden",
                "models": [{"id": "gpt-5.6-sol", "reasoning": True}],
            }
        }
        route = {
            "label": "GPT-5.6 sol",
            "provider": "openai-benchmark",
            "model": "gpt-5.6-sol",
            "secret_name": "OPENAI_BENCHMARK_API_KEY",
        }
        with self.assertRaises(MatrixConfigError):
            resolve_route(route, providers)

    def test_local_job_uses_native_pi_and_contains_no_secret_values(self) -> None:
        job = build_job(
            manifest=self.manifest,
            routes=self.routes,
            judge=self.judge,
        )
        serialized = json.dumps(job, ensure_ascii=False)
        self.assertEqual(len(job["agents"]), 5)
        self.assertTrue(
            all(agent["import_path"] == NATIVE_PI_IMPORT_PATH for agent in job["agents"])
        )
        self.assertTrue(
            all(agent["kwargs"]["thinking"] == "xhigh" for agent in job["agents"])
        )
        self.assertTrue(all("secrets" not in agent for agent in job["agents"]))
        self.assertNotIn("PI_HARBOR_AUTH_CONFIG", serialized)
        self.assertNotIn("auth.json", serialized)
        self.assertNotIn("opencode-go", serialized)
        self.assertNotIn("oauth", serialized.casefold())
        for value in ("personal-key", "personal-token", "personal-oauth"):
            self.assertNotIn(value, serialized)

    def test_hosted_job_selects_least_privilege_stored_secrets(self) -> None:
        job = build_job(
            manifest=self.manifest,
            routes=self.routes,
            judge=self.judge,
            hosted=True,
            hosted_task_name="benchmark-org/breakthrough-advertising",
            hosted_task_ref="0.4.0",
        )
        self.assertEqual(job["credential_mode"], "direct")
        self.assertEqual(
            job["tasks"],
            [{"name": "benchmark-org/breakthrough-advertising", "ref": "0.4.0"}],
        )
        self.assertEqual(
            [agent["secrets"] for agent in job["agents"]],
            [
                ["OPENAI_BENCHMARK_API_KEY", "QWEN_BENCHMARK_API_KEY"],
                ["OPENAI_BENCHMARK_API_KEY", "QWEN_BENCHMARK_API_KEY"],
                ["QWEN_BENCHMARK_API_KEY"],
                ["KIMI_BENCHMARK_API_KEY", "QWEN_BENCHMARK_API_KEY"],
                ["DEEPSEEK_API_KEY", "QWEN_BENCHMARK_API_KEY"],
            ],
        )
        self.assertNotIn("job_secrets", job)

    def test_local_run_requires_external_private_secret_file(self) -> None:
        required = required_secret_names(self.routes, self.judge)
        with self.assertRaisesRegex(MatrixConfigError, "outside the repository"):
            read_external_secret_file(DEFAULT_MANIFEST, required)

        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "benchmark-secrets.env"
            path.write_text(
                "\n".join(f"{name}=dedicated-{index}" for index, name in enumerate(required))
                + "\n",
                encoding="utf-8",
            )
            path.chmod(0o600)
            values = read_external_secret_file(path, required)
        self.assertEqual(set(values), set(required))

    def test_local_child_environment_drops_personal_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PATH": "/usr/bin",
                "OPENAI_API_KEY": "personal-key",
                "GITHUB_TOKEN": "personal-token",
                "ANTHROPIC_OAUTH_TOKEN": "personal-oauth",
                "AWS_ACCESS_KEY_ID": "personal-aws-key",
            },
            clear=True,
        ):
            environment = isolated_local_environment(
                {"QWEN_BENCHMARK_API_KEY": "dedicated-qwen"}
            )
        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(environment["QWEN_BENCHMARK_API_KEY"], "dedicated-qwen")
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("ANTHROPIC_OAUTH_TOKEN", environment)
        self.assertNotIn("AWS_ACCESS_KEY_ID", environment)


if __name__ == "__main__":
    unittest.main()
