#!/usr/bin/env python3
"""Validate PROJECT_STATE.json and report read-only Git synchronization."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "goal_version",
    "project_goal",
    "canonical_repository",
    "expected_remote",
    "expected_branch",
    "openmohaa_reference",
    "checkpoint_id",
    "checkpoint_updated_utc",
    "current_phase",
    "active_map",
    "active_revision",
    "accepted_baseline",
    "latest_candidate",
    "next_action",
    "stopping_condition",
    "open_questions",
    "blockers",
    "known_dirty_paths",
    "map_statuses",
    "evidence_pending",
    "user_approval_required",
}

REQUIRED_MAP_FIELDS = {
    "status",
    "current_revision",
    "accepted_revision",
    "reason",
    "known_defects",
    "evidence_paths",
    "last_tested_revision_or_external_evidence",
    "user_approval_evidence",
    "next_action",
}

ALLOWED_STATUSES = {
    "accepted",
    "candidate",
    "experimental",
    "rejected",
    "unknown",
    "archived",
}

REQUIRED_PROJECT_FILES = (
    "AGENTS.md",
    "PROJECT.md",
    "PROJECT_STATE.json",
    "DECISIONS.md",
    "REJECTIONS.md",
    "VALIDATION.md",
    ".agents/skills/mohaa-map-builder/SKILL.md",
    ".agents/skills/mohaa-map-builder/agents/openai.yaml",
    ".agents/skills/mohaa-map-builder/references/resume-protocol.md",
    ".agents/skills/mohaa-map-builder/references/verification-protocol.md",
    ".agents/skills/mohaa-map-builder/references/geometry-and-visual-quality.md",
    ".agents/skills/mohaa-map-builder/references/bot-and-runtime-validation.md",
    ".agents/skills/mohaa-map-builder/references/autonomous-evidence-loop.md",
    ".agents/skills/mohaa-map-builder/references/openmohaa-source-guide.md",
    ".agents/skills/mohaa-map-builder/assets/evidence-loop.template.json",
    ".agents/skills/mohaa-map-builder/scripts/validate_state.py",
    ".agents/skills/mohaa-map-builder/scripts/checkpoint.py",
    ".agents/skills/mohaa-map-builder/scripts/evidence_loop.py",
    ".agents/skills/mohaa-map-builder/tests/test_evidence_loop.py",
)

SELF_REFERENTIAL_COMMIT_KEYS = {
    "commit",
    "commit_hash",
    "containing_commit",
    "checkpoint_commit",
    "head_commit",
}

REQUIRED_OPENMOHAA_FIELDS = {
    "canonical_repository",
    "inspected_branch",
    "inspected_commit",
    "local_reference_path",
    "inspection_date_utc",
    "source_guide",
}


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalized_repo_slug(url: str) -> str | None:
    """Return lower-case host/owner/repository for common Git URL forms."""
    text = url.strip().replace("\\", "/")
    if text.startswith("git@") and ":" in text:
        host, path = text[4:].split(":", 1)
    elif text.startswith("ssh://") or text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lstrip("/")
    else:
        return None
    path = path.removesuffix(".git").strip("/").lower()
    return f"{host}/{path}" if host and path else None


def parse_utc_timestamp(value: Any, field: str, errors: list[str]) -> None:
    if not nonempty_string(value):
        errors.append(f"{field} must be a non-empty UTC timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not ISO-8601: {value!r}")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{field} must include a UTC offset")
    elif parsed.utcoffset().total_seconds() != 0:
        errors.append(f"{field} must be UTC")


def validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    for index, item in enumerate(value):
        if not nonempty_string(item):
            errors.append(f"{field}[{index}] must be a non-empty string")


def validate_state_data(
    data: Any,
    repo_root: Path | None = None,
    *,
    verify_project_files: bool = False,
) -> list[str]:
    """Return all schema and repository-reference errors without modifying files."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["state root must be a JSON object"]

    missing = sorted(REQUIRED_TOP_LEVEL - data.keys())
    if missing:
        errors.append("missing required top-level fields: " + ", ".join(missing))

    forbidden = sorted(SELF_REFERENTIAL_COMMIT_KEYS & data.keys())
    if forbidden:
        errors.append(
            "state must not record the hash of its containing commit: "
            + ", ".join(forbidden)
        )

    if not isinstance(data.get("schema_version"), int) or data.get("schema_version", 0) < 1:
        errors.append("schema_version must be a positive integer")
    if not isinstance(data.get("goal_version"), int) or data.get("goal_version", 0) < 1:
        errors.append("goal_version must be a positive integer")

    for field in (
        "project_goal",
        "canonical_repository",
        "expected_remote",
        "expected_branch",
        "checkpoint_id",
        "current_phase",
        "next_action",
        "stopping_condition",
    ):
        if not nonempty_string(data.get(field)):
            errors.append(f"{field} must be a non-empty string")

    parse_utc_timestamp(data.get("checkpoint_updated_utc"), "checkpoint_updated_utc", errors)

    for field in (
        "open_questions",
        "blockers",
        "known_dirty_paths",
        "evidence_pending",
    ):
        validate_string_list(data.get(field), field, errors)

    if not isinstance(data.get("user_approval_required"), bool):
        errors.append("user_approval_required must be a boolean")

    canonical_slug = normalized_repo_slug(str(data.get("canonical_repository", "")))
    remote_slug = normalized_repo_slug(str(data.get("expected_remote", "")))
    if canonical_slug != "github.com/pstngh/moh-maps":
        errors.append("canonical_repository must identify github.com/pstngh/moh-maps")
    if remote_slug != "github.com/pstngh/moh-maps":
        errors.append("expected_remote must identify github.com/pstngh/moh-maps")

    openmohaa = data.get("openmohaa_reference")
    if not isinstance(openmohaa, dict):
        errors.append("openmohaa_reference must be an object")
    else:
        reference_missing = sorted(REQUIRED_OPENMOHAA_FIELDS - openmohaa.keys())
        if reference_missing:
            errors.append(
                "openmohaa_reference missing fields: " + ", ".join(reference_missing)
            )
        source_slug = normalized_repo_slug(
            str(openmohaa.get("canonical_repository", ""))
        )
        if source_slug != "github.com/openmoh/openmohaa":
            errors.append(
                "openmohaa_reference.canonical_repository must identify "
                "github.com/openmoh/openmohaa"
            )
        for field in ("inspected_branch", "local_reference_path", "source_guide"):
            if not nonempty_string(openmohaa.get(field)):
                errors.append(f"openmohaa_reference.{field} must be a non-empty string")
        commit = openmohaa.get("inspected_commit")
        if not isinstance(commit, str) or re.fullmatch(r"[0-9a-fA-F]{40}", commit) is None:
            errors.append(
                "openmohaa_reference.inspected_commit must be a full 40-character Git hash"
            )
        inspection_date = openmohaa.get("inspection_date_utc")
        try:
            date.fromisoformat(inspection_date)
        except (TypeError, ValueError):
            errors.append(
                "openmohaa_reference.inspection_date_utc must be an ISO-8601 date"
            )
        guide = openmohaa.get("source_guide")
        expected_guide = (
            ".agents/skills/mohaa-map-builder/references/openmohaa-source-guide.md"
        )
        if guide != expected_guide:
            errors.append(
                f"openmohaa_reference.source_guide must be {expected_guide!r}"
            )
        elif repo_root is not None and not (repo_root / guide).is_file():
            errors.append(f"openmohaa_reference.source_guide does not exist: {guide}")

    statuses = data.get("map_statuses")
    if not isinstance(statuses, dict) or not statuses:
        errors.append("map_statuses must be a non-empty object")
        statuses = {}

    for map_name, entry in statuses.items():
        prefix = f"map_statuses.{map_name}"
        if not nonempty_string(map_name):
            errors.append("map_statuses keys must be non-empty strings")
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        entry_missing = sorted(REQUIRED_MAP_FIELDS - entry.keys())
        if entry_missing:
            errors.append(f"{prefix} missing fields: {', '.join(entry_missing)}")
        status = entry.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(ALLOWED_STATUSES)}")
        if not nonempty_string(str(entry.get("current_revision", ""))):
            errors.append(f"{prefix}.current_revision must be non-empty")
        if not nonempty_string(entry.get("reason")):
            errors.append(f"{prefix}.reason must be a non-empty string")
        if not nonempty_string(entry.get("last_tested_revision_or_external_evidence")):
            errors.append(
                f"{prefix}.last_tested_revision_or_external_evidence must be non-empty"
            )
        if not nonempty_string(entry.get("next_action")):
            errors.append(f"{prefix}.next_action must be a non-empty string")
        validate_string_list(entry.get("known_defects"), f"{prefix}.known_defects", errors)
        validate_string_list(entry.get("evidence_paths"), f"{prefix}.evidence_paths", errors)

        accepted_revision = entry.get("accepted_revision")
        approval = entry.get("user_approval_evidence")
        if accepted_revision is not None and not nonempty_string(str(accepted_revision)):
            errors.append(f"{prefix}.accepted_revision must be null or non-empty")
        if approval is not None and not nonempty_string(approval):
            errors.append(f"{prefix}.user_approval_evidence must be null or non-empty")
        if status == "accepted":
            if accepted_revision is None:
                errors.append(f"{prefix}: accepted status requires accepted_revision")
            if approval is None:
                errors.append(f"{prefix}: accepted status requires explicit approval evidence")
        elif accepted_revision is not None:
            errors.append(f"{prefix}: non-accepted status cannot have accepted_revision")
        if status == "rejected" and approval is not None:
            errors.append(f"{prefix}: rejected status cannot retain approval evidence")

        if repo_root is not None and isinstance(entry.get("evidence_paths"), list):
            for evidence in entry["evidence_paths"]:
                if not nonempty_string(evidence):
                    continue
                evidence_path = Path(evidence)
                if evidence_path.is_absolute() or ".." in evidence_path.parts:
                    errors.append(f"{prefix}.evidence_paths contains unsafe path: {evidence}")
                elif not (repo_root / evidence_path).exists():
                    errors.append(f"{prefix}.evidence_paths does not exist: {evidence}")

    active_map = data.get("active_map")
    active_revision = data.get("active_revision")
    if active_map is not None:
        if not nonempty_string(active_map) or active_map not in statuses:
            errors.append("active_map must be null or name an entry in map_statuses")
        if active_revision is None or not nonempty_string(str(active_revision)):
            errors.append("active_revision must be non-empty when active_map is set")
    elif active_revision is not None:
        errors.append("active_revision must be null when active_map is null")

    accepted_baseline = data.get("accepted_baseline")
    latest_candidate = data.get("latest_candidate")
    if accepted_baseline is not None:
        if accepted_baseline not in statuses:
            errors.append("accepted_baseline must be null or name a map status")
        elif statuses[accepted_baseline].get("status") != "accepted":
            errors.append("accepted_baseline must reference a map with accepted status")
    if latest_candidate is not None:
        if latest_candidate not in statuses:
            errors.append("latest_candidate must be null or name a map status")
        elif statuses[latest_candidate].get("status") != "candidate":
            errors.append("latest_candidate must reference a map with candidate status")
    if accepted_baseline is not None and accepted_baseline == latest_candidate:
        errors.append("accepted_baseline and latest_candidate must remain distinct")

    if repo_root is not None:
        generated_root = repo_root / "generated"
        if generated_root.is_dir():
            generated_maps = {p.name for p in generated_root.iterdir() if p.is_dir()}
            missing_statuses = sorted(generated_maps - set(statuses))
            extra_statuses = sorted(set(statuses) - generated_maps)
            if missing_statuses:
                errors.append("generated maps missing status entries: " + ", ".join(missing_statuses))
            if extra_statuses:
                errors.append("map status entries without generated directories: " + ", ".join(extra_statuses))

    if verify_project_files and repo_root is not None:
        for relative in REQUIRED_PROJECT_FILES:
            if not (repo_root / relative).is_file():
                errors.append(f"required project file is missing: {relative}")

    return errors


def run_git(repo_root: Path, *args: str, check: bool = True) -> str:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.rstrip()


def discover_git_root(start: Path) -> Path:
    root = run_git(start.resolve(), "rev-parse", "--show-toplevel")
    return Path(root).resolve()


def git_report(repo_root: Path, state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    report: dict[str, Any] = {}
    branch = run_git(repo_root, "branch", "--show-current")
    origin = run_git(repo_root, "remote", "get-url", "origin", check=False)
    local_head = run_git(repo_root, "rev-parse", "HEAD")
    upstream = run_git(
        repo_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        check=False,
    )
    upstream_head = run_git(repo_root, "rev-parse", upstream, check=False) if upstream else ""

    ahead = behind = None
    synchronization = "no-upstream"
    if upstream and upstream_head:
        counts = run_git(repo_root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        left, right = counts.split()
        ahead, behind = int(left), int(right)
        if ahead == 0 and behind == 0:
            synchronization = "synchronized"
        elif ahead and behind:
            synchronization = "diverged"
        elif ahead:
            synchronization = "local-ahead"
        else:
            synchronization = "upstream-ahead"

    dirty_lines = run_git(repo_root, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    dirty_paths = [line[3:] for line in dirty_lines if len(line) >= 4]
    recorded_dirty = set(state.get("known_dirty_paths", []))

    report.update(
        {
            "repo_root": str(repo_root),
            "branch": branch,
            "origin": origin,
            "upstream": upstream or None,
            "local_head": local_head,
            "upstream_head": upstream_head or None,
            "ahead": ahead,
            "behind": behind,
            "synchronization": synchronization,
            "dirty_paths": dirty_paths,
            "recorded_dirty_paths_not_currently_dirty": sorted(recorded_dirty - set(dirty_paths)),
        }
    )

    if branch != state.get("expected_branch"):
        errors.append(f"current branch {branch!r} does not match expected_branch")
    if normalized_repo_slug(origin) != normalized_repo_slug(str(state.get("expected_remote", ""))):
        errors.append("origin does not match expected_remote")
    if not upstream:
        errors.append("current branch has no configured upstream")
    elif synchronization in {"diverged", "upstream-ahead"}:
        errors.append(f"unsafe Git synchronization state: {synchronization}")

    return report, errors


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"state file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("state root must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, help="State file; defaults to <repo>/PROJECT_STATE.json")
    parser.add_argument("--repo-root", type=Path, help="Git root; defaults to discovery from cwd")
    parser.add_argument("--json", action="store_true", help="Emit one JSON report")
    args = parser.parse_args()

    try:
        if args.repo_root:
            repo_root = discover_git_root(args.repo_root)
        else:
            try:
                repo_root = discover_git_root(Path.cwd())
            except RuntimeError:
                repo_root = discover_git_root(Path(__file__).resolve().parent)
        state_path = args.state.resolve() if args.state else repo_root / "PROJECT_STATE.json"
        state = load_state(state_path)
        errors = validate_state_data(
            state,
            repo_root,
            verify_project_files=True,
        )
        git, git_errors = git_report(repo_root, state)
        errors.extend(git_errors)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = {
        "valid": not errors,
        "state": str(state_path),
        "checkpoint_id": state.get("checkpoint_id"),
        "goal_version": state.get("goal_version"),
        "active_map": state.get("active_map"),
        "active_revision": state.get("active_revision"),
        "accepted_baseline": state.get("accepted_baseline"),
        "latest_candidate": state.get("latest_candidate"),
        "next_action": state.get("next_action"),
        "stopping_condition": state.get("stopping_condition"),
        "git": git,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"state: {state_path}")
        print(f"valid: {report['valid']}")
        print(f"checkpoint: {report['checkpoint_id']}")
        print(f"active: {report['active_map']} revision {report['active_revision']}")
        print(f"accepted baseline: {report['accepted_baseline']}")
        print(f"latest candidate: {report['latest_candidate']}")
        print(f"next action: {report['next_action']}")
        print(f"stopping condition: {report['stopping_condition']}")
        print(
            "git: "
            f"{git['branch']} -> {git['upstream']} / {git['synchronization']} / "
            f"HEAD {git['local_head']} / upstream {git['upstream_head']}"
        )
        print("dirty paths:")
        for path in git["dirty_paths"]:
            print(f"  - {path}")
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
