#!/usr/bin/env python3
"""Audit, bundle, verify, and compare exact-hash evidence without accepting maps."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FIXED_PERSPECTIVE = "fixed"
ROUTE_METHODS = {"instrumented_positions", "controlled_route_probe"}
REQUIRED_LIFECYCLE_EVENTS = {"spawn", "movement", "combat", "death", "respawn"}
DIAGNOSTIC_RE = re.compile(
    r"script error|not properly loaded|could(?:n't| not)|can(?:'t| not)|"
    r"failed|missing|not found|\bwarning\b|\binvalid\b|"
    r"corrupt(?:ed|ion)?|invalid.{0,40}cvar|unknown command|\berror\b",
    re.IGNORECASE,
)
SEVERE_DIAGNOSTIC_RE = re.compile(
    r"script error|not properly loaded|invalid.{0,40}cvar",
    re.IGNORECASE,
)
DIAGNOSTIC_DISPOSITIONS = {"blocking", "proven_nonblocking"}
BOT_ENTRY_RE = re.compile(r"(bot\d+) has entered the battle", re.IGNORECASE)
BOT_COMBAT_RE = re.compile(
    r"bot\d+.*(?:rifled|machine-gunned|hunted down|perforated|buckshot|rocket|"
    r"blew (?:himself|herself) up|was .* by bot\d+)",
    re.IGNORECASE,
)
BSP_PARSE_RE = re.compile(r"BSP file loaded and parsed in", re.IGNORECASE)
RECAST_GENERATION_RE = re.compile(
    r"Recast navigation mesh\(es\) generated in", re.IGNORECASE
)

RUNTIME_LOG_TIMESTAMP_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}\s+[^\]]+\]\s*")


def normalize_diagnostic_line(line: str) -> str:
    return RUNTIME_LOG_TIMESTAMP_RE.sub("", line).strip()


def group_diagnostic_lines(lines: list[str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for line in lines:
        literal = normalize_diagnostic_line(line)
        counts[literal] = counts.get(literal, 0) + 1
    return [
        {"literal": literal, "count": count}
        for literal, count in counts.items()
    ]


def summarize_labeled_diagnostics(items: list[tuple[str, str]]) -> list[str]:
    counts: dict[tuple[str, str], int] = {}
    for label, line in items:
        key = (label, normalize_diagnostic_line(line))
        counts[key] = counts.get(key, 0) + 1
    return [
        f"{label}: {literal}"
        + (f" ({count} occurrences)" if count > 1 else "")
        for (label, literal), count in counts.items()
    ]


class EvidenceError(ValueError):
    """Raised when evidence input is malformed or cannot be read."""


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceError(f"{label} does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"malformed JSON in {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must contain a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise EvidenceError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def normalized_sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    return lowered if SHA256_RE.fullmatch(lowered) else None


def gate(status: str, detail: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {"status": status, "detail": detail, "evidence": evidence or []}


def percent(passed: int, total: int) -> int:
    return 0 if total <= 0 else round(100 * passed / total)


def inspect_pk3(path: Path, expected_bsp_member: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not path.is_file():
        raise EvidenceError(f"candidate PK3 does not exist: {path}")
    package_sha = sha256_file(path)
    members: list[dict[str, Any]] = []
    names: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                names.append(info.filename)
                digest = hashlib.sha256()
                with archive.open(info, "r") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                members.append(
                    {
                        "path": info.filename,
                        "bytes": info.file_size,
                        "sha256": digest.hexdigest(),
                    }
                )
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise EvidenceError(f"cannot inspect candidate PK3 {path}: {exc}") from exc

    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        errors.append("duplicate PK3 members: " + ", ".join(duplicate_names))
    bsp_members = [member for member in members if member["path"].lower().endswith(".bsp")]
    expected = [member for member in members if member["path"] == expected_bsp_member]
    case_only = [
        member for member in members
        if member["path"].lower() == expected_bsp_member.lower()
        and member["path"] != expected_bsp_member
    ]
    if case_only:
        errors.append(
            "expected BSP member has wrong case: "
            + ", ".join(member["path"] for member in case_only)
        )
    if len(expected) != 1:
        errors.append(
            f"expected exactly one {expected_bsp_member!r} member, found {len(expected)}"
        )
    if len(bsp_members) != 1:
        errors.append(f"expected exactly one BSP member in candidate, found {len(bsp_members)}")
    if not expected_bsp_member.lower().endswith(".bsp"):
        errors.append("expected BSP member path must end with .bsp")
    if (
        len(bsp_members) == 1
        and bsp_members[0]["path"] != expected_bsp_member
    ):
        errors.append(
            f"sole BSP member {bsp_members[0]['path']!r} does not match expected path"
        )

    return (
        {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": package_sha,
            "expected_bsp_member": expected_bsp_member,
            "bsp_sha256": expected[0]["sha256"] if len(expected) == 1 else None,
            "member_count": len(members),
            "members": sorted(members, key=lambda member: member["path"]),
        },
        errors,
    )


def resolve_report_artifact_path(raw_path: Any, report_path: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise EvidenceError("report artifact path is missing")
    path = Path(raw_path)
    if path.is_absolute():
        return path
    resolved_report = report_path.resolve()
    for ancestor in resolved_report.parents:
        candidate = ancestor / path
        if candidate.is_file():
            return candidate.resolve()
    return (resolved_report.parent / path).resolve()


def runtime_copy_path(
    report: dict[str, Any],
    map_name: str,
    report_path: Path | None = None,
) -> Path | None:
    explicit = report.get("runtimePackage")
    if isinstance(explicit, str) and explicit.strip():
        if report_path is not None:
            return resolve_report_artifact_path(explicit, report_path)
        return Path(explicit)
    qa_root = report.get("qaRoot")
    if not isinstance(qa_root, str) or not qa_root.strip():
        return None
    return Path(qa_root) / "base" / "main" / f"zz_{map_name}.pk3"


def audit_runtime_identity(
    label: str,
    report: dict[str, Any],
    report_path: Path,
    map_name: str,
    candidate_sha: str,
    expected_bsp_member: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    issues: list[str] = []
    reported_sha = normalized_sha(report.get("candidateSha256"))
    if reported_sha != candidate_sha:
        issues.append("report candidateSha256 does not match the candidate")
    copy_path = runtime_copy_path(report, map_name, report_path)
    copy_sha: str | None = None
    inventory: list[dict[str, Any]] = []
    if copy_path is None:
        issues.append("report does not identify an isolated runtime package")
    elif not copy_path.is_file():
        issues.append(f"isolated runtime package is missing: {copy_path}")
    else:
        copy_sha = sha256_file(copy_path)
        if copy_sha != candidate_sha:
            issues.append("isolated runtime package hash does not match the candidate")
        base_main = copy_path.parent
        pk3s = sorted(
            (path for path in base_main.iterdir() if path.is_file() and path.suffix.lower() == ".pk3"),
            key=lambda path: path.name.lower(),
        )
        inventory = [
            {"name": path.name, "bytes": path.stat().st_size}
            for path in pk3s
        ]
        if len(pk3s) != 8:
            issues.append(
                f"isolated runtime contains {len(pk3s)} PK3 files instead of exactly eight"
            )
        if copy_path.resolve() not in {path.resolve() for path in pk3s}:
            issues.append("candidate runtime copy is absent from the PK3 inventory")
        qa_root = report.get("qaRoot")
        if isinstance(qa_root, str) and qa_root.strip():
            home_maps = Path(qa_root) / "home" / "main" / "maps"
            if home_maps.is_dir():
                loose_files = sorted(
                    path for path in home_maps.rglob("*") if path.is_file()
                )
                allowed_script = expected_bsp_member.removesuffix(".bsp") + ".scr"
                allowed = {allowed_script} if label == "visual" else set()
                unexpected = [
                    path.relative_to(home_maps.parent).as_posix()
                    for path in loose_files
                    if path.relative_to(home_maps.parent).as_posix() not in allowed
                ]
                if unexpected:
                    issues.append("unexpected loose runtime files: " + ", ".join(unexpected))
    if report.get("mapName") != map_name:
        issues.append("report mapName does not match the evidence plan")
    if report.get("exactPk3Count") != 8:
        issues.append("isolated runtime did not report exactly seven retail PK3s plus candidate")
    status = "pass" if not issues else "fail"
    detail = "exact candidate package was used" if not issues else "; ".join(issues)
    return (
        gate(status, detail, [str(copy_path)] if copy_path is not None else []),
        {
            "label": label,
            "reported_candidate_sha256": reported_sha,
            "runtime_package": str(copy_path) if copy_path is not None else None,
            "runtime_package_sha256": copy_sha,
            "pk3_inventory": inventory,
        },
    )


def audit_screenshots(
    report: dict[str, Any],
    report_path: Path,
    plan: dict[str, Any],
    candidate_sha: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    issues: list[str] = []
    open_items: list[str] = []
    requested = report.get("requestedViews")
    markers = report.get("viewMarkers")
    screenshots = report.get("screenshots")
    views = plan.get("views")
    required_categories = plan.get("required_view_categories")
    if not isinstance(requested, list) or not all(isinstance(item, str) for item in requested):
        requested = []
        issues.append("visual report requestedViews must be a string list")
    if not isinstance(markers, list) or not all(isinstance(item, str) for item in markers):
        markers = []
        issues.append("visual report viewMarkers must be a string list")
    if not isinstance(screenshots, list):
        screenshots = []
        issues.append("visual report screenshots must be a list")
    if not isinstance(views, list) or not views:
        views = []
        issues.append("evidence plan views must be a non-empty list")
    if not isinstance(required_categories, list) or not all(
        isinstance(item, str) and item.strip() for item in required_categories
    ):
        required_categories = []
        issues.append("required_view_categories must be a non-empty string list")

    view_ids: list[str] = []
    category_coverage: dict[str, list[str]] = {category: [] for category in required_categories}
    for index, view in enumerate(views):
        if not isinstance(view, dict):
            issues.append(f"views[{index}] must be an object")
            continue
        view_id = view.get("id")
        categories = view.get("categories")
        perspective = view.get("perspective")
        if not isinstance(view_id, str) or not view_id.strip():
            issues.append(f"views[{index}].id must be non-empty")
            continue
        if view_id in view_ids:
            issues.append(f"duplicate view id: {view_id}")
        view_ids.append(view_id)
        if not isinstance(categories, list) or not all(
            isinstance(category, str) and category.strip() for category in categories
        ):
            issues.append(f"view {view_id} categories must be a non-empty string list")
            categories = []
        if perspective != FIXED_PERSPECTIVE:
            open_items.append(
                f"view {view_id} uses {perspective!r}; dynamic/follow views do not prove fixed-view coverage"
            )
            continue
        for category in categories:
            if category in category_coverage:
                category_coverage[category].append(view_id)

    if requested != view_ids:
        issues.append("requestedViews do not exactly match evidence-plan view order")
    if len(markers) != len(view_ids):
        issues.append("view marker count does not match required view count")
    else:
        for view_id, marker in zip(view_ids, markers):
            if view_id not in marker:
                issues.append(f"view marker does not identify {view_id}")
    if report.get("screenshotCount") != len(screenshots):
        issues.append("screenshotCount does not match screenshots array")
    if len(screenshots) != len(view_ids):
        issues.append("screenshot count does not exactly match required view count")
    missing_categories = sorted(
        category for category, covered_by in category_coverage.items() if not covered_by
    )
    if missing_categories:
        issues.append("fixed-view categories not covered: " + ", ".join(missing_categories))

    screenshot_records: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for index, item in enumerate(screenshots):
        view_id = view_ids[index] if index < len(view_ids) else None
        record: dict[str, Any] = {"view_id": view_id, "path": None, "sha256": None}
        if not isinstance(item, dict):
            issues.append(f"screenshots[{index}] must be an object")
            screenshot_records.append(record)
            continue
        raw_path = item.get("path")
        expected_sha = normalized_sha(item.get("sha256"))
        if not isinstance(raw_path, str) or not raw_path.strip():
            issues.append(f"screenshots[{index}].path is missing")
            screenshot_records.append(record)
            continue
        image_path = resolve_report_artifact_path(raw_path, report_path)
        record["path"] = str(image_path)
        if not image_path.is_file():
            issues.append(f"screenshot is missing: {image_path}")
            screenshot_records.append(record)
            continue
        actual_sha = sha256_file(image_path)
        record["sha256"] = actual_sha
        record["bytes"] = image_path.stat().st_size
        if expected_sha != actual_sha:
            issues.append(f"screenshot hash mismatch: {image_path}")
        if actual_sha in seen_hashes:
            issues.append(f"duplicate screenshot content: {image_path}")
        seen_hashes.add(actual_sha)
        if item.get("bytes") != image_path.stat().st_size:
            issues.append(f"screenshot byte count mismatch: {image_path}")
        screenshot_records.append(record)

    if normalized_sha(report.get("candidateSha256")) != candidate_sha:
        issues.append("visual report is not tied to the exact candidate hash")
    if report.get("scriptErrorCount") != 0:
        issues.append("visual capture reported script errors")

    total_checks = max(1, len(view_ids) + len(required_categories) + 4)
    passed_checks = max(0, total_checks - len(issues))
    status = "pass" if not issues else "fail"
    return (
        gate(status, "capture matrix is complete" if not issues else "; ".join(issues)),
        {
            "requested_views": view_ids,
            "category_coverage": category_coverage,
            "screenshots": screenshot_records,
            "integrity_score": percent(passed_checks, total_checks),
        },
        open_items,
    )


def audit_visual_review(
    plan: dict[str, Any],
    candidate_sha: str,
    capture: dict[str, Any],
) -> tuple[dict[str, Any], int | None, list[dict[str, Any]], list[str]]:
    review = plan.get("visual_review")
    required = capture.get("screenshots", [])
    if not isinstance(review, dict):
        return (
            gate("open", "full-resolution semantic review is not recorded"),
            None,
            [],
            ["inspect every queued screenshot at full resolution and record a hash-linked review"],
        )
    issues: list[str] = []
    open_items: list[str] = []
    defects: list[dict[str, Any]] = []
    if normalized_sha(review.get("candidate_sha256")) != candidate_sha:
        issues.append("visual review candidate_sha256 does not match the candidate")
    reviewer_kind = review.get("reviewer_kind")
    if reviewer_kind not in {"codex_visual", "human_visual"}:
        issues.append("visual review reviewer_kind must be codex_visual or human_visual")
    entries = review.get("views")
    if not isinstance(entries, list):
        entries = []
        issues.append("visual_review.views must be a list")
    by_id = {
        entry.get("id"): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    reviewed = 0
    for screenshot in required:
        view_id = screenshot.get("view_id")
        item = by_id.get(view_id)
        if not isinstance(item, dict) or item.get("reviewed") is not True:
            open_items.append(f"visual review remains open for view {view_id}")
            continue
        reviewed += 1
        if normalized_sha(item.get("screenshot_sha256")) != screenshot.get("sha256"):
            issues.append(f"visual review screenshot hash mismatch for {view_id}")
        blocking = item.get("blocking_defects")
        if not isinstance(blocking, list) or not all(
            isinstance(defect, str) and defect.strip() for defect in blocking
        ):
            issues.append(f"blocking_defects must be a string list for {view_id}")
            continue
        for defect in blocking:
            defects.append({"view_id": view_id, "defect": defect})

    completeness = percent(reviewed, len(required)) if required else 0
    if issues or defects:
        detail_parts = issues + [
            f"{item['view_id']}: {item['defect']}" for item in defects
        ]
        return gate("fail", "; ".join(detail_parts)), completeness, defects, open_items
    if open_items:
        return gate("open", "semantic review is incomplete"), completeness, defects, open_items
    return gate("pass", "all exact-hash screenshots were reviewed with no recorded blocking defect"), 100, defects, []


def audit_runtime(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    issues: list[str] = []
    if not isinstance(report.get("bspParse"), list) or not report["bspParse"]:
        issues.append("BSP parse completion was not observed")
    if not isinstance(report.get("recast"), list) or not report["recast"]:
        issues.append("Recast generation was not observed")
    for field in ("candidateDiagnostics", "stockAssetDiagnostics"):
        value = report.get(field)
        if not isinstance(value, list):
            issues.append(f"{field} must be a list")
        elif value:
            issues.append(f"{field} is non-empty")
    if report.get("scriptErrorCount") != 0:
        issues.append("runtime reported script errors")
    status = "pass" if not issues else "fail"
    return gate(status, "runtime load gates passed" if not issues else "; ".join(issues)), {
        "engine_sha256": normalized_sha(report.get("engineSha256")),
        "bsp_parse_observations": len(report.get("bspParse", [])) if isinstance(report.get("bspParse"), list) else 0,
        "recast_observations": len(report.get("recast", [])) if isinstance(report.get("recast"), list) else 0,
    }


def recount_bot_log_activity(path: Path) -> tuple[int, int, list[str], list[str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    entered = {
        match.group(1).casefold()
        for line in lines
        if (match := BOT_ENTRY_RE.search(line)) is not None
    }
    combat = sum(1 for line in lines if BOT_COMBAT_RE.search(line) is not None)
    bsp_parse = [line for line in lines if BSP_PARSE_RE.search(line) is not None]
    recast = [line for line in lines if RECAST_GENERATION_RE.search(line) is not None]
    return len(entered), combat, bsp_parse, recast


def audit_bot_activity(report: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    bot_plan = plan.get("bot_evidence")
    expected_bots = 8
    if isinstance(bot_plan, dict) and isinstance(bot_plan.get("expected_bot_count"), int):
        expected_bots = bot_plan["expected_bot_count"]
    entered = report.get("botsEntered")
    combat = report.get("combatEvents")
    minimum = report.get("minimumCombatEvents")
    issues: list[str] = []
    if not isinstance(entered, int) or entered != expected_bots:
        issues.append(f"expected {expected_bots} bots, observed {entered!r}")
    if not isinstance(combat, int) or not isinstance(minimum, int) or combat < minimum:
        issues.append(f"combat event threshold was not met: {combat!r}/{minimum!r}")
    status = "pass" if not issues else "fail"
    return gate(status, "bot entry and combat gates passed" if not issues else "; ".join(issues)), {
        "expected_bots": expected_bots,
        "bots_entered": entered,
        "combat_events": combat,
        "minimum_combat_events": minimum,
        "scope": "entry and combat only; this does not prove movement, death, respawn, or route coverage",
    }


def resolve_evidence_source(item: dict[str, Any], plan_path: Path) -> tuple[Path | None, str | None]:
    raw = item.get("source_path")
    expected = normalized_sha(item.get("source_sha256"))
    if not isinstance(raw, str) or not raw.strip() or expected is None:
        return None, "source_path and valid source_sha256 are required"
    path = Path(raw)
    if not path.is_absolute():
        path = plan_path.parent / path
    if not path.is_file():
        return None, f"evidence source is missing: {path}"
    if sha256_file(path) != expected:
        return None, f"evidence source hash mismatch: {path}"
    return path, None


def verify_source_needle(
    item: dict[str, Any], source: Path, declared_field: str
) -> str | None:
    needle = item.get("needle")
    declared = item.get(declared_field)
    if not isinstance(needle, str) or not needle:
        return "needle must be a non-empty literal string"
    if not isinstance(declared, int) or declared < 1:
        return f"{declared_field} must be positive"
    try:
        content = source.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"cannot read evidence source {source}: {exc}"
    actual = content.count(needle)
    if actual < declared:
        return (
            f"source contains needle {actual} time(s), below declared "
            f"{declared_field} {declared}"
        )
    return None


def audit_bot_depth(
    plan: dict[str, Any], plan_path: Path
) -> tuple[dict[str, Any], dict[str, Any], int | None, list[str]]:
    bot = plan.get("bot_evidence")
    if not isinstance(bot, dict):
        return (
            gate("open", "hash-linked bot lifecycle and route evidence is not recorded"),
            gate("open", "mapwide route coverage is not recorded"),
            None,
            ["record instrumented lifecycle and route observations; combat logs alone are insufficient"],
        )
    lifecycle_issues: list[str] = []
    route_issues: list[str] = []
    open_items: list[str] = []
    observed_events: set[str] = set()
    event_observations = bot.get("event_observations")
    if not isinstance(event_observations, list):
        event_observations = []
        lifecycle_issues.append("event_observations must be a list")
    for index, item in enumerate(event_observations):
        if not isinstance(item, dict):
            lifecycle_issues.append(f"event_observations[{index}] must be an object")
            continue
        event = item.get("event")
        if event not in REQUIRED_LIFECYCLE_EVENTS:
            lifecycle_issues.append(f"invalid lifecycle event: {event!r}")
            continue
        source, source_error = resolve_evidence_source(item, plan_path)
        if source_error:
            lifecycle_issues.append(f"{event}: {source_error}")
            continue
        assert source is not None
        content_error = verify_source_needle(item, source, "matches")
        if content_error:
            lifecycle_issues.append(f"{event}: {content_error}")
            continue
        observed_events.add(event)
    missing_events = sorted(REQUIRED_LIFECYCLE_EVENTS - observed_events)
    if missing_events:
        open_items.append("bot lifecycle events remain open: " + ", ".join(missing_events))

    required_routes = bot.get("required_routes")
    if not isinstance(required_routes, list) or not required_routes or not all(
        isinstance(route, str) and route.strip() for route in required_routes
    ):
        required_routes = []
        route_issues.append("required_routes must be a non-empty string list")
    route_observations = bot.get("route_observations")
    if not isinstance(route_observations, list):
        route_observations = []
        route_issues.append("route_observations must be a list")
    observed_routes: set[str] = set()
    for index, item in enumerate(route_observations):
        if not isinstance(item, dict):
            route_issues.append(f"route_observations[{index}] must be an object")
            continue
        route_id = item.get("route_id")
        if route_id not in required_routes:
            route_issues.append(f"unexpected route observation: {route_id!r}")
            continue
        if item.get("method") not in ROUTE_METHODS:
            route_issues.append(
                f"{route_id}: method must be instrumented_positions or controlled_route_probe"
            )
            continue
        source, source_error = resolve_evidence_source(item, plan_path)
        if source_error:
            route_issues.append(f"{route_id}: {source_error}")
            continue
        assert source is not None
        content_error = verify_source_needle(item, source, "sample_count")
        if content_error or item.get("sample_count", 0) < 2:
            route_issues.append(f"{route_id}: {content_error or 'sample_count must be at least 2'}")
            continue
        if not isinstance(item.get("unique_bots"), int) or item["unique_bots"] < 1:
            route_issues.append(f"{route_id}: unique_bots must be positive")
            continue
        observed_routes.add(route_id)
    missing_routes = sorted(set(required_routes) - observed_routes)
    if missing_routes:
        open_items.append("bot route observations remain open: " + ", ".join(missing_routes))

    lifecycle_status = "fail" if lifecycle_issues else ("open" if missing_events else "pass")
    route_status = "fail" if route_issues else ("open" if missing_routes else "pass")
    lifecycle_detail = "; ".join(lifecycle_issues) or (
        "all lifecycle event types are hash-linked" if not missing_events else open_items[0]
    )
    route_detail = "; ".join(route_issues) or (
        "all required routes have instrumented observations"
        if not missing_routes
        else next((item for item in open_items if item.startswith("bot route")), "route evidence is open")
    )
    completeness = percent(
        len(observed_events) + len(observed_routes),
        len(REQUIRED_LIFECYCLE_EVENTS) + len(required_routes),
    )
    return (
        gate(lifecycle_status, lifecycle_detail),
        gate(route_status, route_detail),
        completeness,
        open_items,
    )


def audit_build_provenance(
    plan: dict[str, Any], plan_path: Path, package: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], int | None, list[str]]:
    build = plan.get("build_provenance")
    if not isinstance(build, dict):
        return (
            gate("open", "source, design, compile, and packaged BSP hashes are not correlated"),
            {},
            None,
            ["record hash-linked source map, design report, compile log, and compiled BSP"],
        )
    issues: list[str] = []
    detail: dict[str, Any] = {}
    resolved: dict[str, Path] = {}
    actual_hashes: dict[str, str] = {}
    for label in ("source_map", "design_report", "compile_log", "compiled_bsp"):
        item = build.get(label)
        if not isinstance(item, dict):
            issues.append(f"build_provenance.{label} must be an object")
            continue
        raw_path = item.get("path")
        expected_sha = normalized_sha(item.get("sha256"))
        if not isinstance(raw_path, str) or not raw_path.strip() or expected_sha is None:
            issues.append(f"{label}: path and valid sha256 are required")
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = plan_path.parent / path
        if not path.is_file():
            issues.append(f"{label}: file is missing: {path}")
            continue
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            issues.append(f"{label}: file hash does not match build provenance")
        resolved[label] = path
        actual_hashes[label] = actual_sha
        detail[label] = {
            "path": str(path),
            "sha256": actual_sha,
            "bytes": path.stat().st_size,
        }
    compiled_sha = actual_hashes.get("compiled_bsp")
    if compiled_sha is not None and compiled_sha != package.get("bsp_sha256"):
        issues.append("compiled BSP hash does not match the packaged BSP member")
    design_path = resolved.get("design_report")
    source_sha = actual_hashes.get("source_map")
    if design_path is not None and source_sha is not None:
        try:
            design = load_object(design_path, "design report")
        except EvidenceError as exc:
            issues.append(str(exc))
        else:
            generated = design.get("generated")
            reported_map_sha = normalized_sha(
                generated.get("mapSha256") if isinstance(generated, dict) else None
            )
            if reported_map_sha != source_sha:
                issues.append("design report generated.mapSha256 does not match the source map")
            detail["design_report"]["reported_map_sha256"] = reported_map_sha
    compile_log = resolved.get("compile_log")
    if compile_log is not None and compile_log.stat().st_size == 0:
        issues.append("compile log is empty")
    status = "pass" if not issues and len(resolved) == 4 else "fail"
    return (
        gate(
            status,
            "source map, design report, compile log, compiled BSP, and package are hash-linked"
            if status == "pass"
            else "; ".join(issues),
        ),
        detail,
        100 if status == "pass" else 0,
        [],
    )


def audit_launch_provenance(
    plan: dict[str, Any],
    plan_path: Path,
    visual_report: dict[str, Any],
    runtime_report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], int | None, list[str]]:
    provenance = plan.get("launch_provenance")
    if not isinstance(provenance, dict):
        return (
            gate("open", "hash-linked visual and bot launch provenance is not recorded"),
            {},
            None,
            ["record exact visual and bot engine paths, hashes, arguments, and isolated paths"],
        )
    issues: list[str] = []
    detail: dict[str, Any] = {}
    passed = 0
    for label, report in (("visual", visual_report), ("bot", runtime_report)):
        item = provenance.get(label)
        if not isinstance(item, dict):
            issues.append(f"launch_provenance.{label} must be an object")
            continue
        raw_engine = item.get("engine_path")
        expected_sha = normalized_sha(item.get("engine_sha256"))
        arguments = item.get("arguments")
        fs_basepath = item.get("fs_basepath")
        fs_homepath = item.get("fs_homepath")
        entry_issues: list[str] = []
        actual_sha: str | None = None
        engine_path: Path | None = None
        if not isinstance(raw_engine, str) or not raw_engine.strip() or expected_sha is None:
            entry_issues.append("engine_path and valid engine_sha256 are required")
        else:
            engine_path = Path(raw_engine)
            if not engine_path.is_absolute():
                engine_path = plan_path.parent / engine_path
            if not engine_path.is_file():
                entry_issues.append(f"engine is missing: {engine_path}")
            else:
                actual_sha = sha256_file(engine_path)
                if actual_sha != expected_sha:
                    entry_issues.append("engine hash does not match launch provenance")
        if not isinstance(arguments, list) or not arguments or not all(
            isinstance(argument, str) and argument.strip() for argument in arguments
        ):
            entry_issues.append("arguments must be a non-empty string list")
        qa_root = report.get("qaRoot")
        if not isinstance(qa_root, str) or not qa_root.strip():
            entry_issues.append("QA report does not identify qaRoot")
        else:
            expected_base = (Path(qa_root) / "base").resolve()
            expected_home = (Path(qa_root) / "home").resolve()
            if not isinstance(fs_basepath, str) or Path(fs_basepath).resolve() != expected_base:
                entry_issues.append("fs_basepath does not match the report's isolated base")
            if not isinstance(fs_homepath, str) or Path(fs_homepath).resolve() != expected_home:
                entry_issues.append("fs_homepath does not match the report's isolated home")
        reported_engine_sha = normalized_sha(report.get("engineSha256"))
        if reported_engine_sha is not None and actual_sha is not None and reported_engine_sha != actual_sha:
            entry_issues.append("QA report engineSha256 does not match the launch engine")
        detail[label] = {
            "engine_path": str(engine_path) if engine_path is not None else None,
            "engine_sha256": actual_sha,
            "arguments": arguments if isinstance(arguments, list) else None,
            "fs_basepath": fs_basepath,
            "fs_homepath": fs_homepath,
        }
        if entry_issues:
            issues.extend(f"{label}: {issue}" for issue in entry_issues)
        else:
            passed += 1
    status = "pass" if not issues and passed == 2 else "fail"
    return (
        gate(status, "visual and bot launches are hash-linked" if status == "pass" else "; ".join(issues)),
        detail,
        percent(passed, 2),
        [],
    )


def audit_raw_runtime_logs(
    plan: dict[str, Any],
    visual_report: dict[str, Any],
    runtime_report: dict[str, Any],
    visual_path: Path,
    runtime_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], int | None, list[str]]:
    classifications = plan.get("runtime_diagnostic_classifications", [])
    issues: list[str] = []
    open_items: list[str] = []
    detail: dict[str, Any] = {}
    if not isinstance(classifications, list):
        classifications = []
        issues.append("runtime_diagnostic_classifications must be a list")
    valid_classifications: list[dict[str, str]] = []
    for index, item in enumerate(classifications):
        if not isinstance(item, dict):
            issues.append(f"runtime_diagnostic_classifications[{index}] must be an object")
            continue
        label = item.get("log")
        needle = item.get("needle")
        disposition = item.get("disposition")
        evidence = item.get("evidence")
        if label not in {"visual", "bot"}:
            issues.append(f"diagnostic classification {index} has invalid log")
        elif not isinstance(needle, str) or not needle:
            issues.append(f"diagnostic classification {index} has invalid needle")
        elif disposition not in DIAGNOSTIC_DISPOSITIONS:
            issues.append(f"diagnostic classification {index} has invalid disposition")
        elif not isinstance(evidence, str) or not evidence.strip():
            issues.append(f"diagnostic classification {index} requires evidence")
        else:
            valid_classifications.append(item)

    blocking: list[tuple[str, str]] = []
    severe_unclassified: list[tuple[str, str]] = []
    unclassified: list[tuple[str, str]] = []
    checked_logs = 0
    for label, report, report_path in (
        ("visual", visual_report, visual_path),
        ("bot", runtime_report, runtime_path),
    ):
        raw_path = report.get("log")
        if not isinstance(raw_path, str) or not raw_path.strip():
            issues.append(f"{label} QA report does not identify its raw log")
            continue
        log_path = resolve_report_artifact_path(raw_path, report_path)
        if not log_path.is_file():
            issues.append(f"{label} raw log is missing: {log_path}")
            continue
        checked_logs += 1
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            issues.append(f"cannot read {label} raw log {log_path}: {exc}")
            continue
        diagnostics = [line for line in lines if DIAGNOSTIC_RE.search(line)]
        classified_counts: dict[tuple[str, str, str], int] = {}
        for line in diagnostics:
            matches = [
                item for item in valid_classifications
                if item["log"] == label and item["needle"] in line
            ]
            if any(item["disposition"] == "blocking" for item in matches):
                blocking.append((label, line))
            elif any(item["disposition"] == "proven_nonblocking" for item in matches):
                selected = next(
                    item for item in matches if item["disposition"] == "proven_nonblocking"
                )
                key = (normalize_diagnostic_line(line), selected["disposition"], selected["evidence"])
                classified_counts[key] = classified_counts.get(key, 0) + 1
            elif SEVERE_DIAGNOSTIC_RE.search(line):
                severe_unclassified.append((label, line))
            else:
                unclassified.append((label, line))
        diagnostic_groups = group_diagnostic_lines(diagnostics)
        classified = [
            {
                "line": line,
                "count": count,
                "disposition": disposition,
                "evidence": evidence,
            }
            for (line, disposition, evidence), count in classified_counts.items()
        ]
        detail[label] = {
            "path": str(log_path),
            "sha256": sha256_file(log_path),
            "diagnostic_count": len(diagnostics),
            "unique_diagnostic_count": len(diagnostic_groups),
            "diagnostic_groups": diagnostic_groups,
            "classified_nonblocking": classified,
        }

    if checked_logs != 2:
        issues.append(f"expected two raw logs, verified {checked_logs}")
    if blocking:
        issues.append("blocking diagnostics: " + " | ".join(summarize_labeled_diagnostics(blocking)))
    if severe_unclassified:
        issues.append("severe unclassified diagnostics: " + " | ".join(summarize_labeled_diagnostics(severe_unclassified)))
    if issues:
        return gate("fail", "; ".join(issues)), detail, 0, open_items
    if unclassified:
        open_items.append("classify raw runtime diagnostics: " + " | ".join(summarize_labeled_diagnostics(unclassified)))
        return gate("open", open_items[-1]), detail, None, open_items
    return gate("pass", "raw visual and bot logs are hash-linked and diagnostics are classified"), detail, 100, []


def build_audit(
    candidate_path: Path,
    visual_path: Path,
    runtime_path: Path,
    plan_path: Path,
) -> dict[str, Any]:
    plan = load_object(plan_path, "evidence plan")
    visual = load_object(visual_path, "visual report")
    runtime = load_object(runtime_path, "runtime report")
    if plan.get("schema_version") != 1:
        raise EvidenceError("evidence plan schema_version must be 1")
    map_name = plan.get("map_name")
    bsp_member = plan.get("expected_bsp_member")
    if not isinstance(map_name, str) or not map_name.strip():
        raise EvidenceError("evidence plan map_name must be non-empty")
    if not isinstance(bsp_member, str) or not bsp_member.strip():
        raise EvidenceError("evidence plan expected_bsp_member must be non-empty")

    package, package_issues = inspect_pk3(candidate_path, bsp_member)
    package_gate = gate(
        "pass" if not package_issues else "fail",
        "candidate PK3 and BSP identity are unambiguous"
        if not package_issues
        else "; ".join(package_issues),
        [str(candidate_path.resolve()), bsp_member],
    )
    candidate_sha = package["sha256"]
    build_gate, build_detail, build_score, build_open = audit_build_provenance(
        plan, plan_path, package
    )
    visual_identity, visual_runtime = audit_runtime_identity(
        "visual", visual, visual_path, map_name, candidate_sha, bsp_member
    )
    runtime_identity, bot_runtime = audit_runtime_identity(
        "bot", runtime, runtime_path, map_name, candidate_sha, bsp_member
    )
    launch_gate, launch_detail, launch_score, launch_open = audit_launch_provenance(
        plan, plan_path, visual, runtime
    )
    diagnostic_gate, raw_logs, diagnostic_score, diagnostic_open = audit_raw_runtime_logs(
        plan, visual, runtime, visual_path, runtime_path
    )
    capture_gate, capture, capture_open = audit_screenshots(
        visual, visual_path, plan, candidate_sha
    )
    visual_gate, visual_score, defects, visual_open = audit_visual_review(
        plan, candidate_sha, capture
    )
    runtime_gate, runtime_detail = audit_runtime(runtime)
    bot_gate, bot_detail = audit_bot_activity(runtime, plan)
    if visual_identity["status"] != "pass":
        capture_gate = gate(
            "fail",
            "capture cannot be attributed to the candidate because visual runtime identity failed; "
            + capture_gate["detail"],
        )
    if runtime_identity["status"] != "pass":
        runtime_gate = gate(
            "fail",
            "runtime observations cannot be attributed to the candidate because bot runtime "
            "identity failed; " + runtime_gate["detail"],
        )
        bot_gate = gate(
            "fail",
            "bot observations cannot be attributed to the candidate because bot runtime "
            "identity failed; " + bot_gate["detail"],
        )
    if visual_identity["status"] != "pass" or runtime_identity["status"] != "pass":
        diagnostic_gate = gate(
            "fail",
            "raw logs cannot be attributed to the candidate because runtime identity failed; "
            + diagnostic_gate["detail"],
        )
    lifecycle_gate, route_gate, bot_depth_score, bot_open = audit_bot_depth(plan, plan_path)

    gates = {
        "candidate_package_identity": package_gate,
        "visual_runtime_package_identity": visual_identity,
        "build_provenance": build_gate,
        "bot_runtime_package_identity": runtime_identity,
        "launch_provenance": launch_gate,
        "raw_runtime_diagnostics": diagnostic_gate,
        "runtime_load": runtime_gate,
        "fixed_view_capture": capture_gate,
        "semantic_visual_review": visual_gate,
        "bot_entry_and_combat": bot_gate,
        "bot_lifecycle": lifecycle_gate,
        "bot_route_coverage": route_gate,
        "human_acceptance": gate(
            "open",
            "only explicit user approval of this exact tested candidate can satisfy acceptance",
        ),
    }
    identity_passes = sum(
        gates[name]["status"] == "pass"
        for name in (
            "candidate_package_identity",
            "visual_runtime_package_identity",
            "bot_runtime_package_identity",
        )
    )
    runtime_passes = sum(
        gates[name]["status"] == "pass"
        for name in ("runtime_load", "bot_entry_and_combat")
    )
    bot_score = None
    if bot_depth_score is not None:
        bot_score = round(0.4 * (100 if bot_gate["status"] == "pass" else 0) + 0.6 * bot_depth_score)
    required_for_handoff = [
        name for name in gates
        if name != "human_acceptance"
    ]
    technical_ready = all(gates[name]["status"] == "pass" for name in required_for_handoff)
    return {
        "schema_version": 1,
        "map_name": map_name,
        "candidate": package,
        "inputs": {
            "visual_report": {
                "path": str(visual_path.resolve()),
                "bytes": visual_path.stat().st_size,
                "sha256": sha256_file(visual_path),
            },
            "runtime_report": {
                "path": str(runtime_path.resolve()),
                "bytes": runtime_path.stat().st_size,
                "sha256": sha256_file(runtime_path),
            },
            "evidence_plan": {
                "path": str(plan_path.resolve()),
                "bytes": plan_path.stat().st_size,
                "sha256": sha256_file(plan_path),
            },
        },
        "launch_provenance": launch_detail,
        "build_provenance": build_detail,
        "raw_logs": raw_logs,
        "runtime_identity": [visual_runtime, bot_runtime],
        "runtime": runtime_detail,
        "capture": capture,
        "bot_activity": bot_detail,
        "gates": gates,
        "scores": {
            "exact_identity": percent(identity_passes, 3),
            "launch_provenance": launch_score,
            "build_provenance": build_score,
            "raw_runtime_diagnostics": diagnostic_score,
            "runtime_and_bot_activity": percent(runtime_passes, 2),
            "capture_integrity_and_coverage": capture["integrity_score"],
            "semantic_visual_review_completeness": visual_score,
            "bot_lifecycle_and_route_evidence": bot_score,
        },
        "blocking_visual_defects": defects,
        "open_items": build_open + launch_open + diagnostic_open + capture_open + visual_open + bot_open,
        "technical_ready_for_human_review": technical_ready,
        "promotion_allowed": False,
        "acceptance_status": "requires_explicit_user_approval",
        "scope_warning": (
            "Lane scores measure evidence completeness within this run. They are not an "
            "acceptance score and cannot promote PROJECT_STATE.json."
        ),
    }


def _resolve_artifact_path(raw: Any, label: str, base: Path | None = None) -> Path:
    if isinstance(raw, Path):
        path = raw
    elif not isinstance(raw, str) or not raw.strip():
        raise EvidenceError(f"{label} path is missing")
    else:
        path = Path(raw)
    if base is not None and not path.is_absolute():
        path = base / path
    if not path.is_file():
        raise EvidenceError(f"{label} is missing: {path}")
    return path.resolve()


def _optional_artifact_path(raw: Any, base: Path | None = None) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    if base is not None and not path.is_absolute():
        path = base / path
    return path.resolve() if path.is_file() else None


def _bundle_sources(
    candidate_path: Path,
    visual_path: Path,
    runtime_path: Path,
    plan_path: Path,
    visual: dict[str, Any],
    runtime: dict[str, Any],
    plan: dict[str, Any],
) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = [
        ("candidate", candidate_path),
        ("report:visual", visual_path),
        ("report:runtime", runtime_path),
        ("report:evidence_plan", plan_path),
        (
            "raw_log:visual",
            _resolve_artifact_path(
                resolve_report_artifact_path(visual.get("log"), visual_path),
                "visual raw log",
            ),
        ),
        (
            "raw_log:bot",
            _resolve_artifact_path(
                resolve_report_artifact_path(runtime.get("log"), runtime_path),
                "bot raw log",
            ),
        ),
    ]
    map_name = plan.get("map_name")
    if not isinstance(map_name, str) or not map_name.strip():
        raise EvidenceError("evidence plan map_name is required for materialization")
    for label, report, report_path in (
        ("visual", visual, visual_path),
        ("bot", runtime, runtime_path),
    ):
        runtime_copy = runtime_copy_path(report, map_name, report_path)
        if runtime_copy is None:
            raise EvidenceError(f"{label} runtime package path is missing")
        sources.append(
            (
                f"runtime_package:{label}",
                _resolve_artifact_path(runtime_copy, f"{label} runtime package"),
            )
        )

    views = plan.get("views") if isinstance(plan.get("views"), list) else []
    screenshots = visual.get("screenshots")
    if not isinstance(screenshots, list):
        raise EvidenceError("visual report screenshots must be a list")
    for index, item in enumerate(screenshots):
        if not isinstance(item, dict):
            raise EvidenceError(f"screenshots[{index}] must be an object")
        view = views[index] if index < len(views) and isinstance(views[index], dict) else {}
        view_id = view.get("id") if isinstance(view.get("id"), str) else "unknown"
        sources.append(
            (
                f"screenshot:{index:03d}:{view_id}",
                _resolve_artifact_path(
                    resolve_report_artifact_path(item.get("path"), visual_path),
                    f"screenshot {index}",
                ),
            )
        )

    build = plan.get("build_provenance")
    if isinstance(build, dict):
        for label in ("source_map", "design_report", "compile_log", "compiled_bsp"):
            item = build.get(label)
            raw = item.get("path") if isinstance(item, dict) else None
            path = _optional_artifact_path(raw, plan_path.parent)
            if path is not None:
                sources.append((f"build:{label}", path))

    launch = plan.get("launch_provenance")
    if isinstance(launch, dict):
        for label in ("visual", "bot"):
            item = launch.get(label)
            raw = item.get("engine_path") if isinstance(item, dict) else None
            path = _optional_artifact_path(raw, plan_path.parent)
            if path is not None:
                sources.append((f"engine:{label}", path))

    bot = plan.get("bot_evidence")
    if isinstance(bot, dict):
        for collection, identity_key in (
            ("event_observations", "event"),
            ("route_observations", "route_id"),
        ):
            items = bot.get(collection)
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                identity = item.get(identity_key)
                identity = identity if isinstance(identity, str) and identity else f"{index:03d}"
                path = _optional_artifact_path(item.get("source_path"), plan_path.parent)
                if path is not None:
                    sources.append((f"bot_source:{identity_key}:{identity}", path))
    return sources


def _store_bundle_path(staging: Path, role: str, source: Path) -> dict[str, Any]:
    digest = sha256_file(source)
    relative = f"objects/sha256/{digest}"
    destination = staging / Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(source, destination)
    if sha256_file(destination) != digest:
        raise EvidenceError(f"materialized object hash mismatch for {role}")
    return {
        "role": role,
        "original_name": source.name,
        "bytes": source.stat().st_size,
        "sha256": digest,
        "object": relative,
    }


def _store_bundle_bytes(
    staging: Path,
    role: str,
    original_name: str,
    payload: bytes,
) -> dict[str, Any]:
    digest = hashlib.sha256(payload).hexdigest()
    relative = f"objects/sha256/{digest}"
    destination = staging / Path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(payload)
    if sha256_file(destination) != digest:
        raise EvidenceError(f"materialized object hash mismatch for {role}")
    return {
        "role": role,
        "original_name": original_name,
        "bytes": len(payload),
        "sha256": digest,
        "object": relative,
    }


def materialize_evidence_bundle(
    candidate_path: Path,
    visual_path: Path,
    runtime_path: Path,
    plan_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    candidate_path = candidate_path.resolve()
    visual_path = visual_path.resolve()
    runtime_path = runtime_path.resolve()
    plan_path = plan_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise EvidenceError(f"bundle destination already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    audit_report = build_audit(candidate_path, visual_path, runtime_path, plan_path)
    visual = load_object(visual_path, "visual QA report")
    runtime = load_object(runtime_path, "bot runtime report")
    plan = load_object(plan_path, "evidence plan")
    sources = _bundle_sources(
        candidate_path,
        visual_path,
        runtime_path,
        plan_path,
        visual,
        runtime,
        plan,
    )

    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}.",
        dir=output_dir.parent,
    ) as temporary:
        staging = Path(temporary)
        artifacts = [
            _store_bundle_path(staging, role, source)
            for role, source in sources
        ]
        scorer = Path(__file__).resolve()
        scorer_entry = _store_bundle_path(staging, "scorer", scorer)
        artifacts.append(scorer_entry)
        audit_report["materialized_roles"] = [
            {
                "role": item["role"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
            }
            for item in sorted(
                artifacts,
                key=lambda item: (item["role"], item["sha256"]),
            )
        ]
        audit_payload = (
            json.dumps(audit_report, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        artifacts.append(
            _store_bundle_bytes(staging, "audit", "audit.json", audit_payload)
        )
        artifacts.sort(
            key=lambda item: (
                item["role"],
                item["sha256"],
                item["original_name"],
            )
        )
        audit_entry = next(item for item in artifacts if item["role"] == "audit")
        manifest = {
            "schema_version": 1,
            "bundle_kind": "openmohaa_exact_hash_evidence",
            "map_name": audit_report.get("map_name"),
            "candidate_sha256": audit_report.get("candidate", {}).get("sha256"),
            "expected_bsp_member": audit_report.get("candidate", {}).get(
                "expected_bsp_member"
            ),
            "audit_artifact_sha256": audit_entry["sha256"],
            "audit_scorer_sha256": scorer_entry["sha256"],
            "artifact_count": len(artifacts),
            "object_count": len({item["object"] for item in artifacts}),
            "artifacts": artifacts,
            "technical_ready_for_human_review": audit_report.get(
                "technical_ready_for_human_review"
            ),
            "promotion_allowed": False,
            "acceptance_status": "requires_explicit_user_approval",
        }
        manifest_payload = (
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        (staging / "manifest.json").write_bytes(manifest_payload)
        manifest_sha = hashlib.sha256(manifest_payload).hexdigest()
        (staging / "manifest.sha256").write_text(
            f"{manifest_sha}  manifest.json\n",
            encoding="ascii",
        )
        verification = verify_evidence_bundle(staging)
        if not verification["valid"]:
            raise EvidenceError(
                "materialized bundle failed self-verification: "
                + "; ".join(verification["issues"])
            )
        if output_dir.exists():
            raise EvidenceError(f"bundle destination appeared during write: {output_dir}")
        staging.replace(output_dir)
    return manifest


def verify_evidence_bundle(bundle_dir: Path) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    issues: list[str] = []
    manifest_path = bundle_dir / "manifest.json"
    checksum_path = bundle_dir / "manifest.sha256"
    try:
        manifest = load_object(manifest_path, "bundle manifest")
    except EvidenceError as exc:
        return {
            "valid": False,
            "artifact_count": 0,
            "object_count": 0,
            "issues": [str(exc)],
            "promotion_allowed": False,
        }

    manifest_sha = sha256_file(manifest_path)
    try:
        checksum = checksum_path.read_text(encoding="ascii").strip()
    except OSError as exc:
        issues.append(f"cannot read manifest checksum: {exc}")
    else:
        if checksum != f"{manifest_sha}  manifest.json":
            issues.append("manifest checksum mismatch")

    if manifest.get("schema_version") != 1:
        issues.append("bundle manifest must use schema_version 1")
    if manifest.get("bundle_kind") != "openmohaa_exact_hash_evidence":
        issues.append("bundle_kind is invalid")
    if manifest.get("promotion_allowed") is not False:
        issues.append("bundle must never permit promotion")
    if manifest.get("acceptance_status") != "requires_explicit_user_approval":
        issues.append("bundle acceptance status is invalid")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        artifacts = []
        issues.append("bundle artifacts must be a non-empty list")
    expected_files = {"manifest.json", "manifest.sha256"}
    roles: set[str] = set()
    valid_entries: list[dict[str, Any]] = []
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            issues.append(f"artifacts[{index}] must be an object")
            continue
        role = item.get("role")
        digest = normalized_sha(item.get("sha256"))
        relative = item.get("object")
        expected_bytes = item.get("bytes")
        if not isinstance(role, str) or not role:
            issues.append(f"artifacts[{index}].role is invalid")
            continue
        if role in roles:
            issues.append(f"duplicate artifact role: {role}")
        roles.add(role)
        if (
            digest is None
            or not isinstance(relative, str)
            or relative != f"objects/sha256/{digest}"
            or "\\" in relative
            or relative.startswith("/")
            or ".." in relative.split("/")
        ):
            issues.append(f"{role}: object path or sha256 is invalid")
            continue
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            issues.append(f"{role}: byte count is invalid")
            continue
        expected_files.add(relative)
        object_path = bundle_dir / Path(relative)
        if not object_path.is_file():
            issues.append(f"{role}: object is missing")
            continue
        if object_path.stat().st_size != expected_bytes:
            issues.append(f"{role}: byte count mismatch")
        if sha256_file(object_path) != digest:
            issues.append(f"{role}: hash mismatch")
        valid_entries.append(item)

    if manifest.get("artifact_count") != len(artifacts):
        issues.append("artifact_count does not match artifacts")
    object_count = len({item.get("object") for item in valid_entries})
    if manifest.get("object_count") != object_count:
        issues.append("object_count does not match materialized objects")

    actual_files = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(actual_files - expected_files)
    if unexpected:
        issues.append("unexpected bundle files: " + ", ".join(unexpected))
    missing = sorted(expected_files - actual_files)
    if missing:
        issues.append("missing bundle files: " + ", ".join(missing))

    by_role = {item.get("role"): item for item in valid_entries}
    candidate = by_role.get("candidate")
    scorer = by_role.get("scorer")
    audit = by_role.get("audit")
    executing_scorer_sha = sha256_file(Path(__file__).resolve())
    if candidate is None or candidate.get("sha256") != manifest.get("candidate_sha256"):
        issues.append("candidate artifact does not match manifest identity")
    if scorer is None or scorer.get("sha256") != manifest.get("audit_scorer_sha256"):
        issues.append("scorer artifact does not match audit_scorer_sha256")
    if scorer is None or scorer.get("sha256") != executing_scorer_sha:
        issues.append(
            "bundled scorer does not match the currently executing evidence verifier"
        )
    if audit is None or audit.get("sha256") != manifest.get("audit_artifact_sha256"):
        issues.append("audit artifact does not match audit_artifact_sha256")

    candidate_inspection: dict[str, Any] | None = None
    expected_bsp_member = manifest.get("expected_bsp_member")
    if not isinstance(expected_bsp_member, str) or not expected_bsp_member:
        issues.append("manifest expected_bsp_member is invalid")
    elif candidate is not None:
        try:
            candidate_inspection, candidate_issues = inspect_pk3(
                bundle_dir / Path(candidate["object"]),
                expected_bsp_member,
            )
        except (EvidenceError, KeyError) as exc:
            issues.append(f"cannot independently inspect bundled candidate: {exc}")
        else:
            issues.extend(
                f"bundled candidate: {issue}"
                for issue in candidate_issues
            )
    if audit is not None:
        try:
            audit_report = load_object(
                bundle_dir / Path(audit["object"]),
                "bundled audit",
            )
        except (EvidenceError, KeyError) as exc:
            issues.append(str(exc))
        else:
            audit_candidate = audit_report.get("candidate")
            if not isinstance(audit_candidate, dict):
                audit_candidate = {}
                issues.append("bundled audit candidate must be an object")
            if audit_candidate.get("sha256") != manifest.get("candidate_sha256"):
                issues.append("bundled audit candidate identity mismatch")
            if candidate_inspection is not None:
                for field in (
                    "bytes",
                    "sha256",
                    "expected_bsp_member",
                    "bsp_sha256",
                    "member_count",
                    "members",
                ):
                    if audit_candidate.get(field) != candidate_inspection.get(field):
                        issues.append(
                            f"bundled audit candidate {field} does not match "
                            "independent candidate inspection"
                        )
            if manifest.get("map_name") != audit_report.get("map_name"):
                issues.append("manifest map_name does not match bundled audit")
            if manifest.get("technical_ready_for_human_review") != audit_report.get(
                "technical_ready_for_human_review"
            ):
                issues.append(
                    "manifest technical_ready_for_human_review does not match "
                    "bundled audit"
                )
            if audit_report.get("promotion_allowed") is not False:
                issues.append("bundled audit must never permit promotion")
            if (
                audit_report.get("acceptance_status")
                != "requires_explicit_user_approval"
            ):
                issues.append("bundled audit acceptance status is invalid")

            def correlate_role(
                role: str,
                expected_sha: Any,
                source: str,
                expected_bytes: Any = None,
            ) -> None:
                digest = normalized_sha(expected_sha)
                if digest is None:
                    issues.append(f"{source} sha256 is missing or invalid")
                    return
                entry = by_role.get(role)
                if entry is None:
                    issues.append(f"required bundle role is missing: {role}")
                    return
                if entry.get("sha256") != digest:
                    issues.append(f"{role} hash does not match {source}")
                if expected_bytes is not None and entry.get("bytes") != expected_bytes:
                    issues.append(f"{role} byte count does not match {source}")

            materialized_roles = audit_report.get("materialized_roles")
            indexed_roles: set[str] = set()
            if not isinstance(materialized_roles, list):
                materialized_roles = []
                issues.append("bundled audit materialized_roles must be a list")
            for index, record in enumerate(materialized_roles):
                if not isinstance(record, dict):
                    issues.append(
                        f"bundled audit materialized_roles[{index}] must be an object"
                    )
                    continue
                role = record.get("role")
                if not isinstance(role, str) or not role:
                    issues.append(
                        f"bundled audit materialized_roles[{index}].role is invalid"
                    )
                    continue
                if role == "audit":
                    issues.append("bundled audit cannot self-index the audit role")
                    continue
                if role in indexed_roles:
                    issues.append(f"duplicate bundled audit materialized role: {role}")
                    continue
                indexed_roles.add(role)
                expected_bytes = record.get("bytes")
                if not isinstance(expected_bytes, int) or expected_bytes < 0:
                    issues.append(
                        f"bundled audit materialized role {role} byte count is invalid"
                    )
                    expected_bytes = None
                correlate_role(
                    role,
                    record.get("sha256"),
                    f"bundled audit materialized role {role}",
                    expected_bytes,
                )
            expected_indexed_roles = set(by_role) - {"audit"}
            missing_indexed_roles = sorted(expected_indexed_roles - indexed_roles)
            if missing_indexed_roles:
                issues.append(
                    "bundle roles missing from audit materialized_roles: "
                    + ", ".join(missing_indexed_roles)
                )
            extra_indexed_roles = sorted(indexed_roles - expected_indexed_roles)
            if extra_indexed_roles:
                issues.append(
                    "audit materialized_roles absent from bundle: "
                    + ", ".join(extra_indexed_roles)
                )

            inputs = audit_report.get("inputs")
            if not isinstance(inputs, dict):
                inputs = {}
                issues.append("bundled audit inputs must be an object")
            for key, role in (
                ("visual_report", "report:visual"),
                ("runtime_report", "report:runtime"),
                ("evidence_plan", "report:evidence_plan"),
            ):
                record = inputs.get(key)
                if not isinstance(record, dict):
                    issues.append(f"bundled audit input {key} must be hash-linked")
                    continue
                correlate_role(
                    role,
                    record.get("sha256"),
                    f"bundled audit input {key}",
                    record.get("bytes"),
                )

            visual_report: dict[str, Any] | None = None
            visual_entry = by_role.get("report:visual")
            if visual_entry is not None:
                try:
                    visual_report = load_object(
                        bundle_dir / Path(visual_entry["object"]),
                        "bundled visual report",
                    )
                except (EvidenceError, KeyError) as exc:
                    issues.append(str(exc))

            runtime_report: dict[str, Any] | None = None
            runtime_report_entry = by_role.get("report:runtime")
            if runtime_report_entry is not None:
                try:
                    runtime_report = load_object(
                        bundle_dir / Path(runtime_report_entry["object"]),
                        "bundled runtime report",
                    )
                except (EvidenceError, KeyError) as exc:
                    issues.append(str(exc))

            def claimed_name(value: Any) -> str | None:
                if isinstance(value, Path):
                    return value.name.casefold()
                if isinstance(value, str) and value:
                    return Path(value).name.casefold()
                return None

            def path_claim_matches(declared: Any, audited: Any) -> bool:
                if not isinstance(declared, (str, Path)) or not isinstance(
                    audited,
                    (str, Path),
                ):
                    return False
                declared_path = Path(declared)
                audited_parts = tuple(
                    part.casefold() for part in Path(audited).parts
                )
                declared_parts = tuple(
                    part.casefold() for part in declared_path.parts
                )
                if declared_path.is_absolute():
                    return declared_parts == audited_parts
                relative_parts = tuple(
                    part for part in declared_parts if part != ".."
                )
                return (
                    bool(relative_parts)
                    and audited_parts[-len(relative_parts):] == relative_parts
                )

            launch_provenance = audit_report.get("launch_provenance")
            if visual_report is not None:
                if visual_report.get("mapName") != manifest.get("map_name"):
                    issues.append(
                        "bundled visual report mapName does not match manifest"
                    )
                correlate_role(
                    "candidate",
                    visual_report.get("candidateSha256"),
                    "bundled visual report candidate",
                )
                if "engineSha256" in visual_report:
                    correlate_role(
                        "engine:visual",
                        visual_report.get("engineSha256"),
                        "bundled visual report engine",
                    )

                visual_launch = (
                    launch_provenance.get("visual")
                    if isinstance(launch_provenance, dict)
                    else None
                )
                launch_fields = (
                    "enginePath",
                    "arguments",
                    "fsBasepath",
                    "fsHomepath",
                )
                if any(field in visual_report for field in launch_fields):
                    if not isinstance(visual_launch, dict):
                        issues.append(
                            "bundled audit visual launch provenance must be an object"
                        )
                    else:
                        if "enginePath" in visual_report:
                            declared_engine = visual_report.get("enginePath")
                            if not path_claim_matches(
                                declared_engine, visual_launch.get("engine_path")
                            ):
                                issues.append(
                                    "engine:visual path does not match bundled visual "
                                    "launch provenance"
                                )
                            engine_entry = by_role.get("engine:visual")
                            expected_engine_name = (
                                engine_entry.get("original_name")
                                if engine_entry is not None
                                else None
                            )
                            if claimed_name(declared_engine) != claimed_name(
                                expected_engine_name
                            ):
                                issues.append(
                                    "engine:visual original name does not match "
                                    "bundled visual report enginePath"
                                )
                        if (
                            "arguments" in visual_report
                            and visual_report.get("arguments")
                            != visual_launch.get("arguments")
                        ):
                            issues.append(
                                "bundled visual report arguments do not match "
                                "audited visual launch provenance"
                            )
                        for report_field, audit_field in (
                            ("fsBasepath", "fs_basepath"),
                            ("fsHomepath", "fs_homepath"),
                        ):
                            if report_field in visual_report and not path_claim_matches(
                                visual_report.get(report_field),
                                visual_launch.get(audit_field),
                            ):
                                issues.append(
                                    f"bundled visual report {report_field} does not "
                                    "match audited visual launch provenance"
                                )

            if runtime_report is not None:
                if runtime_report.get("mapName") != manifest.get("map_name"):
                    issues.append(
                        "bundled runtime report mapName does not match manifest"
                    )
                correlate_role(
                    "candidate",
                    runtime_report.get("candidateSha256"),
                    "bundled runtime report candidate",
                )
                runtime_engine_sha = normalized_sha(
                    runtime_report.get("engineSha256")
                )
                correlate_role(
                    "engine:bot",
                    runtime_engine_sha,
                    "bundled runtime report engine",
                )
                bot_launch = (
                    launch_provenance.get("bot")
                    if isinstance(launch_provenance, dict)
                    else None
                )
                audited_launch_engine_sha = (
                    normalized_sha(bot_launch.get("engine_sha256"))
                    if isinstance(bot_launch, dict)
                    else None
                )
                if audited_launch_engine_sha is None:
                    issues.append(
                        "bundled audit bot launch engine sha256 is missing or invalid"
                    )
                elif runtime_engine_sha != audited_launch_engine_sha:
                    issues.append(
                        "bundled runtime report engine hash does not match audited "
                        "bot launch provenance"
                    )
                runtime_summary = audit_report.get("runtime")
                audited_runtime_engine_sha = (
                    normalized_sha(runtime_summary.get("engine_sha256"))
                    if isinstance(runtime_summary, dict)
                    else None
                )
                if audited_runtime_engine_sha is None:
                    issues.append(
                        "bundled audit runtime engine sha256 is missing or invalid"
                    )
                elif runtime_engine_sha != audited_runtime_engine_sha:
                    issues.append(
                        "bundled runtime report engine hash does not match audited "
                        "runtime summary"
                    )
                bot_activity = audit_report.get("bot_activity")
                if not isinstance(bot_activity, dict):
                    issues.append("bundled audit bot_activity must be an object")
                else:
                    for report_field, audit_field in (
                        ("botsEntered", "bots_entered"),
                        ("combatEvents", "combat_events"),
                        ("minimumCombatEvents", "minimum_combat_events"),
                    ):
                        if runtime_report.get(report_field) != bot_activity.get(
                            audit_field
                        ):
                            issues.append(
                                f"bundled runtime report {report_field} does not "
                                "match audited bot activity"
                            )
                replayed_runtime_gate, replayed_runtime_summary = audit_runtime(
                    runtime_report
                )
                audit_gates = audit_report.get("gates")
                audited_runtime_gate = (
                    audit_gates.get("runtime_load")
                    if isinstance(audit_gates, dict)
                    else None
                )
                if audited_runtime_gate != replayed_runtime_gate:
                    issues.append(
                        "bundled audit runtime_load gate does not match replayed "
                        "runtime report"
                    )
                if audit_report.get("runtime") != replayed_runtime_summary:
                    issues.append(
                        "bundled audit runtime summary does not match replayed "
                        "runtime report"
                    )
                raw_bot_entry = by_role.get("raw_log:bot")
                if raw_bot_entry is None:
                    issues.append("required bundle role is missing: raw_log:bot")
                else:
                    try:
                        (
                            recounted_entered,
                            recounted_combat,
                            recounted_bsp_lines,
                            recounted_recast_lines,
                        ) = (
                            recount_bot_log_activity(
                                bundle_dir / Path(raw_bot_entry["object"])
                            )
                        )
                    except (KeyError, OSError) as exc:
                        issues.append(f"could not recount raw_log:bot: {exc}")
                    else:
                        minimum_combat = runtime_report.get(
                            "minimumCombatEvents"
                        )
                        if (
                            isinstance(minimum_combat, bool)
                            or not isinstance(minimum_combat, int)
                            or minimum_combat < 1
                        ):
                            issues.append(
                                "bundled runtime report minimumCombatEvents must "
                                "be a positive integer"
                            )
                        elif recounted_combat < minimum_combat:
                            issues.append(
                                "raw_log:bot combat event recount does not meet "
                                "bundled runtime report minimumCombatEvents"
                            )
                        for report_field, audit_field, observed in (
                            ("botsEntered", "bots_entered", recounted_entered),
                            ("combatEvents", "combat_events", recounted_combat),
                        ):
                            if runtime_report.get(report_field) != observed:
                                issues.append(
                                    f"bundled runtime report {report_field} does "
                                    "not match raw_log:bot recount"
                                )
                            if (
                                isinstance(bot_activity, dict)
                                and bot_activity.get(audit_field) != observed
                            ):
                                issues.append(
                                    f"bundled audit bot_activity {audit_field} does "
                                    "not match raw_log:bot recount"
                                )
                        for report_field, audit_field, observed in (
                            (
                                "bspParse",
                                "bsp_parse_observations",
                                recounted_bsp_lines,
                            ),
                            (
                                "recast",
                                "recast_observations",
                                recounted_recast_lines,
                            ),
                        ):
                            observed_count = len(observed)
                            report_observations = runtime_report.get(report_field)
                            report_count = (
                                len(report_observations)
                                if isinstance(report_observations, list)
                                else None
                            )
                            if report_count != observed_count:
                                issues.append(
                                    f"bundled runtime report {report_field} count "
                                    "does not match raw_log:bot recount"
                                )
                            if (
                                isinstance(runtime_summary, dict)
                                and runtime_summary.get(audit_field) != observed_count
                            ):
                                issues.append(
                                    f"bundled audit runtime {audit_field} does not "
                                    "match raw_log:bot recount"
                                )
                            if isinstance(report_observations, list):
                                for index, observation in enumerate(
                                    report_observations
                                ):
                                    if (
                                        not isinstance(observation, str)
                                        or observation not in observed
                                    ):
                                        issues.append(
                                            f"bundled runtime report {report_field}"
                                            f"[{index}] does not exist exactly in "
                                            "raw_log:bot"
                                        )

            raw_logs = audit_report.get("raw_logs")
            if not isinstance(raw_logs, dict):
                raw_logs = {}
                issues.append("bundled audit raw_logs must be an object")
            for label in ("visual", "bot"):
                record = raw_logs.get(label)
                if not isinstance(record, dict):
                    issues.append(f"bundled audit raw log {label} is missing")
                    continue
                correlate_role(
                    f"raw_log:{label}",
                    record.get("sha256"),
                    f"bundled audit raw log {label}",
                )

                if label == "visual" and visual_report is not None:
                    declared_log = visual_report.get("log")
                    raw_log_entry = by_role.get("raw_log:visual")
                    expected_name = (
                        raw_log_entry.get("original_name")
                        if raw_log_entry is not None
                        else None
                    )
                    if not path_claim_matches(declared_log, record.get("path")):
                        issues.append(
                            "raw_log:visual path does not match bundled audit raw log"
                        )
                    if claimed_name(declared_log) != claimed_name(expected_name):
                        issues.append(
                            "raw_log:visual original name does not match "
                            "bundled visual report log"
                        )

                    if "runtimeLog" in visual_report:
                        declared_runtime_log = visual_report.get("runtimeLog")
                        if not path_claim_matches(
                            declared_runtime_log, record.get("path")
                        ):
                            issues.append(
                                "raw_log:visual runtimeLog path does not match "
                                "bundled audit raw log"
                            )
                        if claimed_name(declared_runtime_log) != claimed_name(
                            expected_name
                        ):
                            issues.append(
                                "raw_log:visual original name does not match "
                                "bundled visual report runtimeLog"
                            )

                if label == "bot" and runtime_report is not None:
                    declared_log = runtime_report.get("log")
                    raw_log_entry = by_role.get("raw_log:bot")
                    expected_name = (
                        raw_log_entry.get("original_name")
                        if raw_log_entry is not None
                        else None
                    )
                    if not path_claim_matches(declared_log, record.get("path")):
                        issues.append(
                            "raw_log:bot path does not match bundled audit raw log"
                        )
                    if claimed_name(declared_log) != claimed_name(expected_name):
                        issues.append(
                            "raw_log:bot original name does not match "
                            "bundled runtime report log"
                        )

            runtime_identity = audit_report.get("runtime_identity")
            runtime_by_label: dict[str, dict[str, Any]] = {}
            if isinstance(runtime_identity, list):
                for record in runtime_identity:
                    if not isinstance(record, dict):
                        continue
                    label = record.get("label")
                    if isinstance(label, str) and label not in runtime_by_label:
                        runtime_by_label[label] = record
            else:
                issues.append("bundled audit runtime_identity must be a list")
            for label in ("visual", "bot"):
                record = runtime_by_label.get(label)
                if record is None:
                    issues.append(f"bundled audit runtime identity {label} is missing")
                    continue
                correlate_role(
                    f"runtime_package:{label}",
                    record.get("runtime_package_sha256"),
                    f"bundled audit runtime identity {label}",
                )

                if label == "visual" and visual_report is not None:
                    if "runtimePackageSha256" in visual_report:
                        correlate_role(
                            "runtime_package:visual",
                            visual_report.get("runtimePackageSha256"),
                            "bundled visual report runtime package",
                        )
                    report_map_name = manifest.get("map_name")
                    declared_package = (
                        runtime_copy_path(visual_report, report_map_name)
                        if isinstance(report_map_name, str)
                        else None
                    )
                    runtime_entry = by_role.get("runtime_package:visual")
                    expected_name = (
                        runtime_entry.get("original_name")
                        if runtime_entry is not None
                        else None
                    )
                    if not path_claim_matches(
                        declared_package, record.get("runtime_package")
                    ):
                        issues.append(
                            "runtime_package:visual path does not match bundled audit"
                        )
                    if claimed_name(declared_package) != claimed_name(expected_name):
                        issues.append(
                            "runtime_package:visual original name does not match "
                            "bundled visual report runtime package"
                        )

                if label == "bot" and runtime_report is not None:
                    if "runtimePackageSha256" in runtime_report:
                        correlate_role(
                            "runtime_package:bot",
                            runtime_report.get("runtimePackageSha256"),
                            "bundled runtime report runtime package",
                        )
                    report_map_name = manifest.get("map_name")
                    declared_package = (
                        runtime_copy_path(runtime_report, report_map_name)
                        if isinstance(report_map_name, str)
                        else None
                    )
                    runtime_entry = by_role.get("runtime_package:bot")
                    expected_name = (
                        runtime_entry.get("original_name")
                        if runtime_entry is not None
                        else None
                    )
                    if not path_claim_matches(
                        declared_package, record.get("runtime_package")
                    ):
                        issues.append(
                            "runtime_package:bot path does not match bundled audit"
                        )
                    if claimed_name(declared_package) != claimed_name(expected_name):
                        issues.append(
                            "runtime_package:bot original name does not match "
                            "bundled runtime report runtime package"
                        )

            capture = audit_report.get("capture")
            screenshots = capture.get("screenshots") if isinstance(capture, dict) else None
            expected_screenshot_roles: set[str] = set()
            report_screenshots: list[Any] = []
            if visual_report is not None:
                raw_report_screenshots = visual_report.get("screenshots")
                if not isinstance(raw_report_screenshots, list):
                    issues.append("bundled visual report screenshots must be a list")
                else:
                    report_screenshots = raw_report_screenshots
                    if visual_report.get("screenshotCount") != len(report_screenshots):
                        issues.append(
                            "bundled visual report screenshotCount does not match "
                            "screenshots array"
                        )
            if not isinstance(screenshots, list):
                screenshots = []
                issues.append("bundled audit capture screenshots must be a list")
            if visual_report is not None and len(report_screenshots) != len(screenshots):
                issues.append(
                    "bundled visual report screenshot count does not match bundled audit"
                )
            for index, record in enumerate(screenshots):
                if not isinstance(record, dict):
                    issues.append(f"bundled audit screenshot {index} must be an object")
                    continue
                view_id = record.get("view_id")
                if not isinstance(view_id, str) or not view_id:
                    issues.append(f"bundled audit screenshot {index} view_id is invalid")
                    continue
                role = f"screenshot:{index:03d}:{view_id}"
                expected_screenshot_roles.add(role)
                correlate_role(
                    role,
                    record.get("sha256"),
                    f"bundled audit screenshot {index}",
                    record.get("bytes"),
                )
                if visual_report is not None and index < len(report_screenshots):
                    declared = report_screenshots[index]
                    if not isinstance(declared, dict):
                        issues.append(
                            f"bundled visual report screenshot {index} must be an object"
                        )
                    else:
                        correlate_role(
                            role,
                            declared.get("sha256"),
                            f"bundled visual report screenshot {index}",
                            declared.get("bytes"),
                        )
                        screenshot_entry = by_role.get(role)
                        expected_name = (
                            screenshot_entry.get("original_name")
                            if screenshot_entry is not None
                            else None
                        )
                        if not path_claim_matches(
                            declared.get("path"), record.get("path")
                        ):
                            issues.append(
                                f"{role} path does not match bundled audit screenshot"
                            )
                        if claimed_name(declared.get("path")) != claimed_name(
                            expected_name
                        ):
                            issues.append(
                                f"{role} original name does not match bundled visual "
                                f"report screenshot {index}"
                            )
            actual_screenshot_roles = {
                role for role in by_role if isinstance(role, str) and role.startswith("screenshot:")
            }
            extra_screenshot_roles = sorted(actual_screenshot_roles - expected_screenshot_roles)
            if extra_screenshot_roles:
                issues.append(
                    "screenshot roles absent from bundled audit: "
                    + ", ".join(extra_screenshot_roles)
                )

    return {
        "valid": not issues,
        "artifact_count": len(artifacts),
        "object_count": object_count,
        "manifest_sha256": manifest_sha,
        "candidate_sha256": manifest.get("candidate_sha256"),
        "audit_scorer_sha256": manifest.get("audit_scorer_sha256"),
        "executing_scorer_sha256": executing_scorer_sha,
        "issues": issues,
        "promotion_allowed": False,
    }


def compare_reports(before_path: Path, after_path: Path) -> dict[str, Any]:
    before = load_object(before_path, "before audit")
    after = load_object(after_path, "after audit")
    if before.get("schema_version") != 1 or after.get("schema_version") != 1:
        raise EvidenceError("audit reports must use schema_version 1")
    if before.get("map_name") != after.get("map_name"):
        raise EvidenceError("cannot compare audit reports for different maps")
    before_scores = before.get("scores") if isinstance(before.get("scores"), dict) else {}
    after_scores = after.get("scores") if isinstance(after.get("scores"), dict) else {}
    deltas: dict[str, int | None] = {}
    for lane in sorted(set(before_scores) | set(after_scores)):
        old = before_scores.get(lane)
        new = after_scores.get(lane)
        deltas[lane] = new - old if isinstance(old, int) and isinstance(new, int) else None
    before_gates = before.get("gates") if isinstance(before.get("gates"), dict) else {}
    after_gates = after.get("gates") if isinstance(after.get("gates"), dict) else {}
    transitions = {
        name: {
            "before": before_gates.get(name, {}).get("status"),
            "after": after_gates.get(name, {}).get("status"),
        }
        for name in sorted(set(before_gates) | set(after_gates))
    }
    regressed = [
        name for name, item in transitions.items()
        if item["before"] == "pass" and item["after"] != "pass"
    ]
    improved = [
        name for name, item in transitions.items()
        if item["before"] != "pass" and item["after"] == "pass"
    ]
    old_defects = {
        (item.get("view_id"), item.get("defect"))
        for item in before.get("blocking_visual_defects", [])
        if isinstance(item, dict)
    }
    new_defects = {
        (item.get("view_id"), item.get("defect"))
        for item in after.get("blocking_visual_defects", [])
        if isinstance(item, dict)
    }
    numeric_deltas = [value for value in deltas.values() if isinstance(value, int)]
    bounded_improvement = bool(
        not regressed
        and (improved or any(value > 0 for value in numeric_deltas))
        and all(value >= 0 for value in numeric_deltas)
    )
    return {
        "schema_version": 1,
        "map_name": before.get("map_name"),
        "before_candidate_sha256": before.get("candidate", {}).get("sha256"),
        "after_candidate_sha256": after.get("candidate", {}).get("sha256"),
        "score_deltas": deltas,
        "gate_transitions": transitions,
        "improved_gates": improved,
        "regressed_gates": regressed,
        "cleared_visual_defects": [
            {"view_id": view, "defect": defect} for view, defect in sorted(old_defects - new_defects)
        ],
        "introduced_visual_defects": [
            {"view_id": view, "defect": defect} for view, defect in sorted(new_defects - old_defects)
        ],
        "bounded_evidence_improvement": bounded_improvement,
        "promotion_allowed": False,
        "acceptance_status": "requires_explicit_user_approval",
    }


def write_json(value: dict[str, Any], output: Path | None) -> None:
    serialized = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if output is None:
        print(serialized, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(output)


def strict_failure(report: dict[str, Any]) -> bool:
    gates = report["gates"]
    return any(
        item["status"] != "pass"
        for name, item in gates.items()
        if name != "human_acceptance"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="audit one exact-hash evidence run")
    audit.add_argument("--candidate-pk3", type=Path, required=True)
    audit.add_argument("--visual-report", type=Path, required=True)
    audit.add_argument("--runtime-report", type=Path, required=True)
    audit.add_argument("--evidence-plan", type=Path, required=True)
    audit.add_argument("--output", type=Path)
    audit.add_argument(
        "--strict",
        action="store_true",
        help="exit 2 unless every non-human evidence gate passes",
    )
    materialize = subparsers.add_parser(
        "materialize",
        help="create an atomic content-addressed exact-hash evidence bundle",
    )
    materialize.add_argument("--candidate-pk3", type=Path, required=True)
    materialize.add_argument("--visual-report", type=Path, required=True)
    materialize.add_argument("--runtime-report", type=Path, required=True)
    materialize.add_argument("--evidence-plan", type=Path, required=True)
    materialize.add_argument("--output-dir", type=Path, required=True)
    verify = subparsers.add_parser(
        "verify-bundle", help="verify a materialized evidence bundle"
    )
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--output", type=Path)
    compare = subparsers.add_parser("compare", help="compare two audit reports")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            report = build_audit(
                args.candidate_pk3.resolve(),
                args.visual_report.resolve(),
                args.runtime_report.resolve(),
                args.evidence_plan.resolve(),
            )
            write_json(report, args.output.resolve() if args.output else None)
            return 2 if args.strict and strict_failure(report) else 0
        if args.command == "materialize":
            materialize_evidence_bundle(
                args.candidate_pk3.resolve(),
                args.visual_report.resolve(),
                args.runtime_report.resolve(),
                args.evidence_plan.resolve(),
                args.output_dir.resolve(),
            )
            print(args.output_dir.resolve() / "manifest.json")
            return 0
        if args.command == "verify-bundle":
            verification = verify_evidence_bundle(args.bundle.resolve())
            write_json(
                verification,
                args.output.resolve() if args.output else None,
            )
            return 0 if verification["valid"] else 2
        report = compare_reports(args.before.resolve(), args.after.resolve())
        write_json(report, args.output.resolve() if args.output else None)
        return 0
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
