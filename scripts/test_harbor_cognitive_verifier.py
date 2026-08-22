from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harbor_cognitive_verifier import parse_args, run_verifier


class HarborCognitiveVerifierTests(unittest.TestCase):
    def test_hard_constraint_failure_emits_numeric_zero_without_judge(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            submission = root / "submission.md"
            output = root / "logs"
            submission.write_text("太短", encoding="utf-8")
            args = parse_args(
                [
                    "--tests-root",
                    str(root / "tests"),
                    "--submission",
                    str(submission),
                    "--output-dir",
                    str(output),
                    "--min-chars",
                    "10",
                    "--max-chars",
                    "20",
                ]
            )

            self.assertEqual(run_verifier(args), 0)
            reward = json.loads((output / "reward.json").read_text(encoding="utf-8"))
            self.assertEqual(reward["reward"], 0.0)
            self.assertEqual(reward["cognitive_relation_coverage"], 0.0)
            self.assertEqual(reward["complete_core_path_rate"], 0.0)
            self.assertEqual(reward["hard_constraints"], 0.0)
            self.assertEqual(reward["discourse_reconstruction"], 0.0)
            self.assertEqual(reward["editorial_coherence"], 0.0)
            self.assertFalse((output / "cognitive-provider.resolved.json").exists())

    def test_complete_runtime_emits_temporary_cognitive_reward(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            tests_root = root / "tests"
            scripts_dir = tests_root / "scripts"
            scripts_dir.mkdir(parents=True)
            submission = root / "submission.md"
            output = root / "logs"
            submission.write_text("足够长度的文章", encoding="utf-8")
            (tests_root / "cognitive-provider.json").write_text(
                json.dumps({"model_id": "runtime-placeholder"}),
                encoding="utf-8",
            )
            fake_runtime = scripts_dir / "cognitive_semantic_runtime.py"
            fake_runtime.write_text(
                """\
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', type=Path, required=True)
args, _ = parser.parse_known_args()
args.output_dir.mkdir(parents=True, exist_ok=True)
aggregate = {
    'status': 'complete',
    'metrics': {
        'cognitive_relation_coverage': 0.75,
        'complete_core_path_rate': 0.5,
    },
}
(args.output_dir / 'cognitive-aggregate.json').write_text(
    json.dumps(aggregate), encoding='utf-8'
)
""",
                encoding="utf-8",
            )
            fake_discourse_runtime = scripts_dir / "discourse_semantic_runtime.py"
            fake_discourse_runtime.write_text(
                """\
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--output-dir', type=Path, required=True)
args, _ = parser.parse_known_args()
aggregate = {
    'status': 'complete',
    'authorial_edge_recovery': 0.8,
    'editorial': {
        'local_progression': 0.7,
        'global_order': 0.6,
        'spine_connectivity': 0.9,
        'example_integration': 1.0,
        'closure': 0.5,
        'editorial_coherence': 0.72,
    },
    'discourse_reconstruction': 0.76,
}
(args.output_dir / 'discourse-aggregate.json').write_text(
    json.dumps(aggregate), encoding='utf-8'
)
""",
                encoding="utf-8",
            )
            args = parse_args(
                [
                    "--tests-root",
                    str(tests_root),
                    "--submission",
                    str(submission),
                    "--output-dir",
                    str(output),
                    "--min-chars",
                    "1",
                    "--max-chars",
                    "100",
                    "--allow-draft-card",
                ]
            )

            with patch.dict(
                "os.environ", {"BENCHMARK_JUDGE_MODEL": "anthropic/frozen-model"}
            ):
                self.assertEqual(run_verifier(args), 0)

            reward = json.loads((output / "reward.json").read_text(encoding="utf-8"))
            self.assertEqual(reward["reward"], 0.75)
            self.assertEqual(reward["complete_core_path_rate"], 0.5)
            self.assertEqual(reward["hard_constraints"], 1.0)
            self.assertEqual(reward["authorial_edge_recovery"], 0.8)
            self.assertEqual(reward["editorial_coherence"], 0.72)
            self.assertEqual(reward["discourse_reconstruction"], 0.76)
            resolved = json.loads(
                (output / "cognitive-provider.resolved.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(resolved["model_id"], "anthropic/frozen-model")


if __name__ == "__main__":
    unittest.main()
