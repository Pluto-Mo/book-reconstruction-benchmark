# /// script
# dependencies = []
# ///
# To add a dependency: uv add --script metric.py <dependency>

import argparse
import json
from pathlib import Path


def main(input_path: Path, output_path: Path):
    rows: list[dict[str, float]] = []

    for line in input_path.read_text().splitlines():
        reward = json.loads(line)
        if reward is None:
            rows.append({"reward": 0.0})
            continue

        numeric = {
            key: float(value)
            for key, value in reward.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if not numeric:
            raise ValueError("Expected at least one numeric reward value")
        rows.append(numeric)

    keys = sorted({key for row in rows for key in row})
    metrics = {
        f"mean_{key}": sum(row.get(key, 0.0) for row in rows) / len(rows)
        for key in keys
    } if rows else {}
    metrics["task_count"] = len(rows)
    if "mean_reward" in metrics:
        metrics["mean"] = metrics["mean_reward"]

    output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input-path",
        type=Path,
        required=True,
        help="Path to a jsonl file containing rewards, one json object per line.",
    )
    parser.add_argument(
        "-o",
        "--output-path",
        type=Path,
        required=True,
        help="Path to a json file where the metric will be written as a json object.",
    )
    args = parser.parse_args()
    main(args.input_path, args.output_path)
