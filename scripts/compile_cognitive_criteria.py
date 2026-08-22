# /// script
# dependencies = ["jsonschema>=4.22,<5"]
# ///

"""Compile one verifier-only criterion per Book Card relation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from validate_book_card import validate_cross_references

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOK_SCHEMA = REPO_ROOT / "schemas/book-card.schema.json"
DEFAULT_CRITERION_SCHEMA = REPO_ROOT / "schemas/cognitive-criterion.schema.json"
DEFAULT_LOCATOR_PROMPT = REPO_ROOT / "prompts/cognitive/locator-v1.md"
DEFAULT_JUDGE_PROMPT = REPO_ROOT / "prompts/cognitive/judge-v1.md"

FORBIDDEN_CRITERION_KEYS = {
    "source_anchor_ids",
    "weight",
    "critical",
    "paths",
    "genericity_traps",
    "source",
    "compression",
}
RISK_ORDER = (
    "direction",
    "condition_or_boundary",
    "stance_or_epistemic",
    "case_identity",
    "constitutive_case",
    "dense_facets",
)


class CriteriaCompilationError(ValueError):
    def __init__(self, errors: str | list[str]):
        self.errors = [errors] if isinstance(errors, str) else errors
        super().__init__("; ".join(self.errors))


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CriteriaCompilationError(f"file not found: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CriteriaCompilationError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriteriaCompilationError(f"expected a JSON object in {path}")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prompt_version(label: str, path: Path) -> str:
    return f"{label}-{sha256_bytes(path.read_bytes())[:12]}"


def schema_errors(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    found = sorted(
        validator.iter_errors(instance),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    errors: list[str] = []
    for error in found:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label}.{location}: {error.message}")
    return errors


def criterion_node(node: dict[str, Any]) -> dict[str, Any]:
    result = {
        "statement": node["statement"],
        "role": node["role"],
        "stance_owner": node["stance_owner"],
        "epistemic_status": node["epistemic_status"],
    }
    if "case_profile" in node:
        result["case_profile"] = dict(node["case_profile"])
    return result


def risk_flags(
    relation: dict[str, Any],
    source_nodes: list[dict[str, Any]],
    target_nodes: list[dict[str, Any]],
) -> list[str]:
    facets = set(relation["required_facets"])
    nodes = source_nodes + target_nodes
    flags: set[str] = set()
    if "direction" in facets:
        flags.add("direction")
    if facets.intersection({"condition", "boundary"}):
        flags.add("condition_or_boundary")
    if facets.intersection({"stance_owner", "epistemic_status"}):
        flags.add("stance_or_epistemic")
    if "case_identity" in facets or any(
        node.get("role") in {"case", "counterexample"} for node in nodes
    ):
        flags.add("case_identity")
    if any(
        node.get("case_profile", {}).get("function") == "constitutive"
        and node.get("case_profile", {}).get("preservation") == "required"
        for node in nodes
    ):
        flags.add("constitutive_case")
    if len(facets) >= 5:
        flags.add("dense_facets")
    return [flag for flag in RISK_ORDER if flag in flags]


def compile_criteria(
    book_card: dict[str, Any],
    locator_prompt_path: Path = DEFAULT_LOCATOR_PROMPT,
    judge_prompt_path: Path = DEFAULT_JUDGE_PROMPT,
) -> list[dict[str, Any]]:
    locator_version = prompt_version("locator-v1", locator_prompt_path)
    judge_version = prompt_version("judge-v1", judge_prompt_path)
    criteria: list[dict[str, Any]] = []

    for structure in book_card["cognitive_structures"]:
        node_by_id = {node["id"]: node for node in structure["nodes"]}
        for relation in structure["relations"]:
            source_nodes = [
                criterion_node(node_by_id[node_id])
                for node_id in relation["source_node_ids"]
            ]
            target_nodes = [
                criterion_node(node_by_id[node_id])
                for node_id in relation["target_node_ids"]
            ]
            flags = risk_flags(relation, source_nodes, target_nodes)
            criteria.append(
                {
                    "schema_version": "1.0",
                    "visibility": "verifier_only",
                    "book_id": book_card["book_id"],
                    "criterion_id": relation["id"],
                    "relation": {
                        "relation_type": relation["relation_type"],
                        "requirement": relation["requirement"],
                        "required_facets": list(relation["required_facets"]),
                        "source_nodes": source_nodes,
                        "target_nodes": target_nodes,
                        "acceptable_paraphrases": list(
                            relation["acceptable_paraphrases"]
                        ),
                        "pass_if": list(relation["pass_if"]),
                        "fail_if": list(relation["fail_if"]),
                        "common_false_positives": list(
                            relation["common_false_positives"]
                        ),
                        "contradiction_patterns": list(
                            relation["contradiction_patterns"]
                        ),
                    },
                    "review_policy": {
                        "recommended": bool(flags),
                        "risk_flags": flags,
                    },
                    "prompt_versions": {
                        "locator": locator_version,
                        "judge": judge_version,
                    },
                }
            )
    return criteria


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


def audit_criteria(
    criteria: list[dict[str, Any]],
    book_card: dict[str, Any],
    criterion_schema: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    anchor_ids = {anchor["id"] for anchor in book_card.get("source_anchors", [])}

    for index, criterion in enumerate(criteria):
        criterion_id = criterion.get("criterion_id", f"<index-{index}>")
        errors.extend(
            schema_errors(criterion, criterion_schema, f"criterion {criterion_id}")
        )
        if criterion_id in seen_ids:
            errors.append(f"duplicate criterion_id {criterion_id}")
        seen_ids.add(str(criterion_id))

        leaked_keys = all_keys(criterion).intersection(FORBIDDEN_CRITERION_KEYS)
        if leaked_keys:
            errors.append(
                f"criterion {criterion_id}: forbidden keys leaked "
                f"{sorted(leaked_keys)!r}"
            )
        serialized = json.dumps(criterion, ensure_ascii=False, sort_keys=True)
        leaked_anchors = sorted(
            anchor_id for anchor_id in anchor_ids if anchor_id in serialized
        )
        if leaked_anchors:
            errors.append(
                f"criterion {criterion_id}: source anchor IDs leaked {leaked_anchors!r}"
            )
    return errors


def serialize_jsonl(records: list[dict[str, Any]]) -> bytes:
    lines = [
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for record in records
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_manifest(
    book_card_path: Path,
    book_card: dict[str, Any],
    criterion_schema_path: Path,
    locator_prompt_path: Path,
    judge_prompt_path: Path,
    criteria_bytes: bytes,
    criteria: list[dict[str, Any]],
) -> dict[str, Any]:
    relation_ids = sorted(criterion["criterion_id"] for criterion in criteria)
    relation_id_bytes = ("\n".join(relation_ids) + "\n").encode("utf-8")
    return {
        "schema_version": "1.0",
        "visibility": "verifier_only",
        "book_id": book_card["book_id"],
        "book_card_status": book_card["status"],
        "book_card_sha256": sha256_bytes(book_card_path.read_bytes()),
        "criterion_schema_sha256": sha256_bytes(criterion_schema_path.read_bytes()),
        "prompt_versions": {
            "locator": prompt_version("locator-v1", locator_prompt_path),
            "judge": prompt_version("judge-v1", judge_prompt_path),
        },
        "criterion_count": len(criteria),
        "relation_ids_sha256": sha256_bytes(relation_id_bytes),
        "criteria_sha256": sha256_bytes(criteria_bytes),
        "leakage_audit": {
            "status": "passed",
            "forbidden_keys": sorted(FORBIDDEN_CRITERION_KEYS),
            "source_anchor_ids_absent": True,
        },
    }


def render_manifest(manifest: dict[str, Any]) -> bytes:
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile verifier-only narrow criteria from a validated Book Card."
        )
    )
    parser.add_argument("--book-card", type=Path, required=True)
    parser.add_argument("--book-schema", type=Path, default=DEFAULT_BOOK_SCHEMA)
    parser.add_argument(
        "--criterion-schema", type=Path, default=DEFAULT_CRITERION_SCHEMA
    )
    parser.add_argument("--locator-prompt", type=Path, default=DEFAULT_LOCATOR_PROMPT)
    parser.add_argument("--judge-prompt", type=Path, default=DEFAULT_JUDGE_PROMPT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--allow-draft-card", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        book_card = load_json_object(args.book_card)
        book_schema = load_json_object(args.book_schema)
        criterion_schema = load_json_object(args.criterion_schema)
        errors = schema_errors(book_card, book_schema, "book_card")
        errors.extend(validate_cross_references(book_card))
        if book_card.get("status") == "draft" and not args.allow_draft_card:
            errors.append("draft Book Card requires explicit --allow-draft-card")
        if errors:
            raise CriteriaCompilationError(errors)

        criteria = compile_criteria(book_card, args.locator_prompt, args.judge_prompt)
        errors = audit_criteria(criteria, book_card, criterion_schema)
        if errors:
            raise CriteriaCompilationError(errors)
        criteria_bytes = serialize_jsonl(criteria)
        manifest = build_manifest(
            args.book_card,
            book_card,
            args.criterion_schema,
            args.locator_prompt,
            args.judge_prompt,
            criteria_bytes,
            criteria,
        )
        manifest_bytes = render_manifest(manifest)

        if args.check:
            check_errors: list[str] = []
            try:
                existing_criteria = args.output.read_bytes()
            except FileNotFoundError:
                check_errors.append(f"criteria output not found: {args.output}")
            else:
                if existing_criteria != criteria_bytes:
                    check_errors.append(
                        f"criteria output differs from compiled bytes: {args.output}"
                    )
            try:
                existing_manifest = args.manifest.read_bytes()
            except FileNotFoundError:
                check_errors.append(f"manifest not found: {args.manifest}")
            else:
                if existing_manifest != manifest_bytes:
                    check_errors.append(
                        f"manifest differs from compiled bytes: {args.manifest}"
                    )
            if check_errors:
                raise CriteriaCompilationError(check_errors)
            mode = "check"
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(criteria_bytes)
            args.manifest.write_bytes(manifest_bytes)
            mode = "write"
    except (OSError, UnicodeDecodeError, CriteriaCompilationError) as exc:
        print("Cognitive criteria compilation failed:", file=sys.stderr)
        if isinstance(exc, CriteriaCompilationError):
            for error in exc.errors:
                print(f"- {error}", file=sys.stderr)
        else:
            print(f"- {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "valid": True,
                "mode": mode,
                "criterion_count": len(criteria),
                "criteria_sha256": manifest["criteria_sha256"],
                "output": str(args.output.resolve()),
                "manifest": str(args.manifest.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
