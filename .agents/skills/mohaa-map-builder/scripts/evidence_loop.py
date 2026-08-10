#!/usr/bin/env python3
"""Audit and compare exact-hash OpenMoHAA map evidence without accepting maps."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FIXED_PERSPECTIVE = "fixed"
ROUTE_METHODS = {"instrumented_positions", "controlled_route_probe"}
REQUIRED_LIFECYCLE_EVENTS = {"spawn", "movement", "combat", "death", "respawn"}
DIAGNOSTIC_RE = re.compile(
    r"script error|not properly loaded|could(?:n't| not)|can(?:'t| not)|"
    r"failed|missing|invalid.{0,40}cvar|unknown command|error",
    re.IGNORECASE,
)
SEVERE_DIAGNOSTIC_RE = re.compile(
    r"script error|not properly loaded|invalid.{0,40}cvar",
    re.IGNORECASE,
)
DIAGNOSTIC_DISPOSITIONS = {"blocking", "proven_nonblocking"}


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


def runtime_copy_path(report: dict[str, Any], map_name: str) -> Path | None:
    explicit = report.get("runtimePackage")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit)
    qa_root = report.get("qaRoot")
    if not isinstance(qa_root, str) or not qa_root.strip():
        return None
    return Path(qa_root) / "base" / "main" / f"zz_{map_name}.pk3"


def audit_runtime_identity(
    label: str,
    report: dict[str, Any],
    map_name: str,
    candidate_sha: str,
    expected_bsp_member: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    issues: list[str] = []
    reported_sha = normalized_sha(report.get("candidateSha256"))
    if reported_sha != candidate_sha:
        issues.append("report candidateSha256 does not match the candidate")
    copy_path = runtime_copy_path(report, map_name)
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
        image_path = Path(raw_path)
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

    blocking: list[str] = []
    severe_unclassified: list[str] = []
    unclassified: list[str] = []
    checked_logs = 0
    for label, report in (("visual", visual_report), ("bot", runtime_report)):
        raw_path = report.get("log")
        if not isinstance(raw_path, str) or not raw_path.strip():
            issues.append(f"{label} QA report does not identify its raw log")
            continue
        log_path = Path(raw_path)
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
        classified: list[dict[str, str]] = []
        for line in diagnostics:
            matches = [
                item for item in valid_classifications
                if item["log"] == label and item["needle"] in line
            ]
            if any(item["disposition"] == "blocking" for item in matches):
                blocking.append(f"{label}: {line}")
            elif any(item["disposition"] == "proven_nonblocking" for item in matches):
                selected = next(
                    item for item in matches if item["disposition"] == "proven_nonblocking"
                )
                classified.append(
                    {"line": line, "disposition": selected["disposition"], "evidence": selected["evidence"]}
                )
            elif SEVERE_DIAGNOSTIC_RE.search(line):
                severe_unclassified.append(f"{label}: {line}")
            else:
                unclassified.append(f"{label}: {line}")
        detail[label] = {
            "path": str(log_path),
            "sha256": sha256_file(log_path),
            "diagnostic_count": len(diagnostics),
            "classified_nonblocking": classified,
        }

    if checked_logs != 2:
        issues.append(f"expected two raw logs, verified {checked_logs}")
    if blocking:
        issues.append("blocking diagnostics: " + " | ".join(blocking))
    if severe_unclassified:
        issues.append("severe unclassified diagnostics: " + " | ".join(severe_unclassified))
    if issues:
        return gate("fail", "; ".join(issues)), detail, 0, open_items
    if unclassified:
        open_items.append("classify raw runtime diagnostics: " + " | ".join(unclassified))
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
        "visual", visual, map_name, candidate_sha, bsp_member
    )
    runtime_identity, bot_runtime = audit_runtime_identity(
        "bot", runtime, map_name, candidate_sha, bsp_member
    )
    launch_gate, launch_detail, launch_score, launch_open = audit_launch_provenance(
        plan, plan_path, visual, runtime
    )
    diagnostic_gate, raw_logs, diagnostic_score, diagnostic_open = audit_raw_runtime_logs(
        plan, visual, runtime
    )
    capture_gate, capture, capture_open = audit_screenshots(visual, plan, candidate_sha)
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
            "visual_report": str(visual_path.resolve()),
            "runtime_report": str(runtime_path.resolve()),
            "evidence_plan": str(plan_path.resolve()),
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
        report = compare_reports(args.before.resolve(), args.after.resolve())
        write_json(report, args.output.resolve() if args.output else None)
        return 0
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
