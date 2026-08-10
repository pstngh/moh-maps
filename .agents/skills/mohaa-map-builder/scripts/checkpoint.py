#!/usr/bin/env python3
"""Atomically update an existing PROJECT_STATE.json checkpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_state import discover_git_root, load_state, validate_state_data


PROTECTED_FIELDS = {
    "schema_version",
    "goal_version",
    "project_goal",
    "canonical_repository",
    "expected_remote",
    "expected_branch",
    "next_action",
    "stopping_condition",
    "checkpoint_id",
    "checkpoint_updated_utc",
}


def parse_set_json(values: list[str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"--set-json requires FIELD=JSON, got {item!r}")
        field, raw_value = item.split("=", 1)
        field = field.strip()
        if not field:
            raise ValueError("--set-json field must not be empty")
        if field in PROTECTED_FIELDS:
            raise ValueError(f"use a dedicated workflow for protected field {field!r}")
        if field in updates:
            raise ValueError(f"duplicate --set-json field: {field}")
        try:
            updates[field] = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON for {field}: {exc}") from exc
    return updates


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path = path.resolve()
    if not path.parent.is_dir():
        raise ValueError(f"state parent directory does not exist: {path.parent}")
    original_mode = path.stat().st_mode if path.exists() else None
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if original_mode is not None:
            os.chmod(temporary, original_mode)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, help="State file; defaults to <repo>/PROJECT_STATE.json")
    parser.add_argument("--repo-root", type=Path, help="Git root; defaults to discovery from cwd")
    parser.add_argument("--next-action", required=True, help="One exact action for the next task")
    parser.add_argument("--stopping-condition", help="Exact stop condition; preserves current value if omitted")
    parser.add_argument("--checkpoint-id", help="New checkpoint identifier; preserves current value if omitted")
    parser.add_argument("--current-phase", help="New current phase; preserves current value if omitted")
    parser.add_argument(
        "--updated-utc",
        help="Explicit UTC ISO-8601 timestamp; defaults to current UTC",
    )
    parser.add_argument(
        "--set-json",
        action="append",
        default=[],
        metavar="FIELD=JSON",
        help="Intentionally replace another top-level field with a JSON value",
    )
    args = parser.parse_args()

    try:
        if not args.next_action.strip():
            raise ValueError("--next-action must be non-empty")
        if args.stopping_condition is not None and not args.stopping_condition.strip():
            raise ValueError("--stopping-condition must be non-empty")
        repo_root = discover_git_root(args.repo_root or Path.cwd())
        state_path = args.state.resolve() if args.state else repo_root / "PROJECT_STATE.json"
        state = load_state(state_path)

        pre_errors = validate_state_data(state, repo_root, verify_project_files=True)
        if pre_errors:
            raise ValueError("refusing malformed state before update:\n- " + "\n- ".join(pre_errors))

        state["next_action"] = args.next_action.strip()
        if args.stopping_condition is not None:
            state["stopping_condition"] = args.stopping_condition.strip()
        if args.checkpoint_id is not None:
            if not args.checkpoint_id.strip():
                raise ValueError("--checkpoint-id must be non-empty")
            state["checkpoint_id"] = args.checkpoint_id.strip()
        if args.current_phase is not None:
            if not args.current_phase.strip():
                raise ValueError("--current-phase must be non-empty")
            state["current_phase"] = args.current_phase.strip()

        for field, value in parse_set_json(args.set_json).items():
            state[field] = value

        state["checkpoint_updated_utc"] = args.updated_utc or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        post_errors = validate_state_data(state, repo_root, verify_project_files=True)
        if post_errors:
            raise ValueError("refusing malformed state after update:\n- " + "\n- ".join(post_errors))

        atomic_write_json(state_path, state)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"updated: {state_path}")
    print(f"checkpoint: {state['checkpoint_id']}")
    print(f"updated UTC: {state['checkpoint_updated_utc']}")
    print(f"next action: {state['next_action']}")
    print(f"stopping condition: {state['stopping_condition']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
