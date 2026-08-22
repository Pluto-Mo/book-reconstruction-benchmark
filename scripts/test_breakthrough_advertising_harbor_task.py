from __future__ import annotations

import hashlib
import json
import os
import unittest

import tomllib
from jsonschema import Draft202012Validator
from runtime_scoring import REPO_ROOT

TASK_ROOT = REPO_ROOT / "tasks/breakthrough-advertising-dev"
TESTS_ROOT = TASK_ROOT / "tests"


class BreakthroughAdvertisingHarborTaskTests(unittest.TestCase):
    def test_native_harbor_isolation_and_artifact_contract(self) -> None:
        config = tomllib.loads((TASK_ROOT / "task.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["artifacts"], ["/app/submission.md"])
        self.assertEqual(config["environment"]["network_mode"], "no-network")
        self.assertEqual(config["verifier"]["environment_mode"], "separate")
        self.assertEqual(config["verifier"]["environment"]["network_mode"], "public")
        self.assertEqual(
            config["verifier"]["env"]["BENCHMARK_JUDGE_MODEL"],
            "openai/qwen3.8-max",
        )
        self.assertEqual(
            config["verifier"]["env"]["BENCHMARK_JUDGE_API_KEY"],
            "${QWEN_BENCHMARK_API_KEY}",
        )
        self.assertEqual(
            config["verifier"]["env"]["BENCHMARK_JUDGE_BASE_URL"],
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(
            config["verifier"]["env"]["BENCHMARK_JUDGE_ENABLE_THINKING"],
            "true",
        )
        self.assertNotIn("ANTHROPIC_API_KEY", config["verifier"]["env"])
        self.assertNotIn("OPENAI_API_KEY", config["verifier"]["env"])
        self.assertEqual(config["metadata"]["instruction_variant"], "natural")

    def test_task_runtime_bundle_matches_repository_sources(self) -> None:
        pairs = [
            (
                REPO_ROOT / "scripts/cognitive_semantic_runtime.py",
                TESTS_ROOT / "scripts/cognitive_semantic_runtime.py",
            ),
            (
                REPO_ROOT / "scripts/runtime_scoring.py",
                TESTS_ROOT / "scripts/runtime_scoring.py",
            ),
            (
                REPO_ROOT / "scripts/discourse_runtime_scoring.py",
                TESTS_ROOT / "scripts/discourse_runtime_scoring.py",
            ),
            (
                REPO_ROOT / "scripts/discourse_semantic_runtime.py",
                TESTS_ROOT / "scripts/discourse_semantic_runtime.py",
            ),
            (
                REPO_ROOT / "scripts/validate_book_card.py",
                TESTS_ROOT / "scripts/validate_book_card.py",
            ),
            (
                REPO_ROOT / "scripts/count_submission_chars.py",
                TESTS_ROOT / "scripts/count_submission_chars.py",
            ),
            (
                REPO_ROOT / "scripts/validate_discourse_card.py",
                TESTS_ROOT / "scripts/validate_discourse_card.py",
            ),
            (
                REPO_ROOT / "scripts/harbor_cognitive_verifier.py",
                TESTS_ROOT / "scripts/harbor_cognitive_verifier.py",
            ),
            (
                REPO_ROOT / "scripts/litellm_provider_adapter.py",
                TESTS_ROOT / "provider_adapter.py",
            ),
            (
                REPO_ROOT / "workbench/breakthrough-advertising/book_card.draft.json",
                TESTS_ROOT / "gold/book_card.json",
            ),
            (
                REPO_ROOT
                / "workbench/breakthrough-advertising/discourse_card.draft.json",
                TESTS_ROOT / "gold/discourse_card.json",
            ),
            (
                REPO_ROOT / "workbench/breakthrough-advertising/runtime/"
                "cognitive_criteria.draft.jsonl",
                TESTS_ROOT / "gold/cognitive_criteria.jsonl",
            ),
            (
                REPO_ROOT / "workbench/breakthrough-advertising/runtime/"
                "cognitive_criteria.manifest.draft.json",
                TESTS_ROOT / "gold/cognitive_criteria.manifest.json",
            ),
            (
                REPO_ROOT
                / "workbench/breakthrough-advertising/oracle_unconstrained.draft.md",
                TASK_ROOT / "solution/reference_submission.md",
            ),
        ]
        pairs.extend(
            (source, TESTS_ROOT / "schemas" / source.name)
            for source in sorted((REPO_ROOT / "schemas").glob("*.json"))
        )
        pairs.extend(
            (source, TESTS_ROOT / "prompts/cognitive" / source.name)
            for source in sorted((REPO_ROOT / "prompts/cognitive").glob("*.md"))
        )
        pairs.extend(
            (source, TESTS_ROOT / "prompts/discourse" / source.name)
            for source in sorted((REPO_ROOT / "prompts/discourse").glob("*.md"))
        )
        for source, bundled in pairs:
            with self.subTest(path=str(bundled.relative_to(REPO_ROOT))):
                self.assertEqual(source.read_bytes(), bundled.read_bytes())

    def test_provider_config_and_private_source_hash(self) -> None:
        provider_schema = json.loads(
            (TESTS_ROOT / "schemas/cognitive-provider-config.schema.json").read_text(
                encoding="utf-8"
            )
        )
        provider_config = json.loads(
            (TESTS_ROOT / "cognitive-provider.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(provider_schema).validate(provider_config)

        card = json.loads(
            (TESTS_ROOT / "gold/book_card.json").read_text(encoding="utf-8")
        )
        private_source = TASK_ROOT / "environment/source/突破性广告中英文合订本.md"
        if private_source.is_file():
            self.assertEqual(
                hashlib.sha256(private_source.read_bytes()).hexdigest(),
                card["source"]["document_sha256"],
            )

    def test_entrypoints_are_executable_and_instruction_is_instantiated(self) -> None:
        for path in (
            TASK_ROOT / "solution/solve.sh",
            TESTS_ROOT / "test.sh",
            TESTS_ROOT / "provider_adapter.py",
            TESTS_ROOT / "scripts/harbor_cognitive_verifier.py",
            TESTS_ROOT / "scripts/discourse_semantic_runtime.py",
        ):
            self.assertTrue(os.access(path, os.X_OK), str(path))
        instruction = (TASK_ROOT / "instruction.md").read_text(encoding="utf-8")
        self.assertNotIn("{{MIN_CHARS}}", instruction)
        self.assertNotIn("{{MAX_CHARS}}", instruction)
        self.assertIn("6000–8000", instruction)
        self.assertIn("压缩共读", instruction)


if __name__ == "__main__":
    unittest.main()
