#!/usr/bin/env python3
"""Create repository-relative, hash-linked durable evidence documents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def repo_path(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    source = args.source_root.resolve()
    evidence = repo / "generated/codex_cache/evidence/revision-1-exact-hash-20260810"
    reports = evidence / "reports"
    screenshots = evidence / "screenshots"
    logs = evidence / "logs"
    instrumentation = evidence / "instrumentation"

    original_visual = load(source / "visual-report.json")
    fixed = load(source / "fixed-view-plan.json")
    if len(original_visual["screenshots"]) != len(fixed["fixedViews"]):
        raise ValueError("fixed-view and screenshot counts differ")

    conversions: list[dict] = []
    durable_screenshots: list[dict] = []
    for index, (raw, view) in enumerate(zip(original_visual["screenshots"], fixed["fixedViews"])):
        raw_path = Path(raw["path"])
        png_path = screenshots / f"shot{index:04d}.png"
        if sha256(raw_path) != raw["sha256"]:
            raise ValueError(f"raw screenshot hash mismatch: {raw_path}")
        with Image.open(raw_path) as raw_image, Image.open(png_path) as png_image:
            raw_image.load()
            png_image.load()
            if raw_image.size != png_image.size or raw_image.mode != png_image.mode:
                raise ValueError(f"lossless conversion metadata mismatch at index {index}")
            raw_pixels = hashlib.sha256(raw_image.tobytes()).hexdigest()
            png_pixels = hashlib.sha256(png_image.tobytes()).hexdigest()
            if raw_pixels != png_pixels:
                raise ValueError(f"lossless conversion pixel mismatch at index {index}")
            dimensions = list(raw_image.size)
            mode = raw_image.mode
        durable_sha = sha256(png_path)
        durable_record = {
            "path": repo_path(repo, png_path),
            "bytes": png_path.stat().st_size,
            "sha256": durable_sha,
        }
        durable_screenshots.append(durable_record)
        conversions.append(
            {
                "view_id": view["id"],
                "source_tga": {
                    "name": raw_path.name,
                    "bytes": raw_path.stat().st_size,
                    "sha256": raw["sha256"],
                },
                "durable_png": durable_record,
                "dimensions": dimensions,
                "mode": mode,
                "decoded_pixel_sha256": raw_pixels,
                "lossless_pixel_match": True,
            }
        )

    conversion_manifest = {
        "schemaVersion": 1,
        "candidateSha256": original_visual["candidateSha256"],
        "transform": "TGA to PNG; decoded dimensions, mode, and pixel bytes verified identical",
        "count": len(conversions),
        "screenshots": conversions,
    }
    write(reports / "screenshot-conversion-manifest.json", conversion_manifest)

    visual = dict(original_visual)
    visual["screenshots"] = durable_screenshots
    visual["log"] = repo_path(repo, logs / "visual-qconsole.log")
    visual["runtimeLog"] = repo_path(repo, logs / "visual-qconsole.log")
    visual["stdoutLog"] = repo_path(repo, logs / "visual-engine.stdout.log")
    visual["stderrLog"] = repo_path(repo, logs / "visual-engine.stderr.log")
    visual["durableEvidenceConversion"] = {
        "sourceFormat": "TGA",
        "durableFormat": "PNG",
        "manifest": repo_path(repo, reports / "screenshot-conversion-manifest.json"),
        "losslessPixelMatch": True,
    }
    write(reports / "visual-report.json", visual)

    bot_runtime = load(reports / "bot-runtime-report.json")
    bot_runtime["log"] = repo_path(repo, logs / "bot-standard-qconsole.log")
    write(reports / "bot-runtime-report.json", bot_runtime)

    plan = load(source / "evidence-plan.json")
    for item, screenshot in zip(plan["visual_review"]["views"], durable_screenshots):
        item["screenshot_sha256"] = screenshot["sha256"]
    for item in plan["bot_evidence"]["event_observations"]:
        event = item["event"]
        if event in {"spawn", "combat"}:
            path = logs / "bot-standard-qconsole.log"
        elif event == "movement":
            path = logs / "bot-instrumented-qconsole.log"
        else:
            path = logs / "bot-lifecycle-observations.log"
        item["source_path"] = "../logs/" + path.name
        item["source_sha256"] = sha256(path)
    for item in plan["bot_evidence"]["route_observations"]:
        path = logs / "bot-route-observations.log"
        item["source_path"] = "../logs/" + path.name
        item["source_sha256"] = sha256(path)
    write(reports / "evidence-plan.json", plan)

    bot_instrumented = load(reports / "bot-instrumented-report.json")
    bot_instrumented["runtimeLog"] = repo_path(repo, logs / "bot-instrumented-qconsole.log")
    bot_instrumented["stdoutLog"] = repo_path(repo, logs / "bot-instrumented-engine.stdout.log")
    bot_instrumented["stderrLog"] = repo_path(repo, logs / "bot-instrumented-engine.stderr.log")
    bot_instrumented["durableLooseScript"] = repo_path(repo, instrumentation / "bot-codex_cache.scr")
    bot_instrumented["durableLooseScriptSha256"] = sha256(instrumentation / "bot-codex_cache.scr")
    write(reports / "bot-instrumented-report.json", bot_instrumented)

    door = load(reports / "door-instrumented-report.json")
    door["runtimeLog"] = repo_path(repo, logs / "door-instrumented-qconsole.log")
    door["stdoutLog"] = repo_path(repo, logs / "door-instrumented-engine.stdout.log")
    door["stderrLog"] = repo_path(repo, logs / "door-instrumented-engine.stderr.log")
    door["durableLooseScript"] = repo_path(repo, instrumentation / "door-codex_cache.scr")
    door["durableLooseScriptSha256"] = sha256(instrumentation / "door-codex_cache.scr")
    write(reports / "door-instrumented-report.json", door)

    harness_manifest = {
        "schemaVersion": 1,
        "candidateSha256": original_visual["candidateSha256"],
        "files": [
            {
                "path": repo_path(repo, path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(instrumentation.iterdir())
            if path.is_file()
        ],
    }
    write(reports / "instrumentation-manifest.json", harness_manifest)
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
