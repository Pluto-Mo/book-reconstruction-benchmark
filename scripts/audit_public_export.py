#!/usr/bin/env python3

"""Audit the GitHub-visible benchmark snapshot for private data and credentials."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_PATTERN = re.compile(r"^\$\{[A-Z][A-Z0-9_]*\}$")
TOKEN_PATTERNS = (
    ("provider-style secret", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{20,}\b", re.IGNORECASE)),
)
PRIVATE_FILENAMES = {
    ".env",
    "auth.json",
    "credentials.json",
    "benchmark-secrets.env",
}
PRIVATE_SUFFIXES = {".pdf", ".epub", ".mobi"}


def candidate_paths(repo_root: Path = REPO_ROOT) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("cannot enumerate GitHub-visible files")
    return [repo_root / raw.decode("utf-8") for raw in completed.stdout.split(b"\0") if raw]


def path_findings(path: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    relative = path.relative_to(repo_root)
    parts = relative.parts
    findings: list[str] = []
    if path.name in PRIVATE_FILENAMES or path.name.endswith(".secrets.env"):
        findings.append("private credential filename")
    if path.suffix.casefold() in PRIVATE_SUFFIXES:
        findings.append("book/archive file type is not public by default")
    if "jobs" in parts:
        findings.append("local Harbor job output")
    if parts and parts[0] == "results" and relative.as_posix() != "results/README.md":
        findings.append("local result output")
    if "environment" in parts and "source" in parts and path.name != "README.md":
        findings.append("private book source")
    return findings


def _walk_json(value: Any, location: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            yield child_location, child
            yield from _walk_json(child, child_location)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            child_location = f"{location}[{index}]"
            yield child_location, child
            yield from _walk_json(child, child_location)


def content_findings(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return ["cannot read candidate file"]
    if b"\0" in raw:
        return []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["non-UTF-8 public candidate requires manual review"]

    findings = [label for label, pattern in TOKEN_PATTERNS if pattern.search(text)]
    if path.suffix.casefold() == ".json":
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            return findings
        for location, value in _walk_json(document):
            key = location.rsplit(".", 1)[-1].casefold()
            if key in {"apikey", "api_key"} and isinstance(value, str):
                if PLACEHOLDER_PATTERN.fullmatch(value) is None:
                    findings.append(f"literal API key at {location}")
    return findings


def audit(repo_root: Path = REPO_ROOT) -> tuple[list[Path], dict[str, list[str]]]:
    paths = candidate_paths(repo_root)
    findings: dict[str, list[str]] = {}
    for path in paths:
        reasons = path_findings(path, repo_root) + content_findings(path)
        if reasons:
            findings[path.relative_to(repo_root).as_posix()] = sorted(set(reasons))
    return paths, findings


def main() -> int:
    try:
        paths, findings = audit()
    except RuntimeError as exc:
        print(f"public export audit failed: {exc}", file=sys.stderr)
        return 2
    result = {
        "status": "pass" if not findings else "fail",
        "github_visible_file_count": len(paths),
        "findings": findings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
