#!/usr/bin/env python3
"""Convert VRF-exported CS2 base-color PNGs into local MOHAA TGA textures.

The input conversion manifests and all emitted images are Valve-derived local
build products. They must remain under generated/codex_nuke/.local-source2 (or
another untracked directory) and must never be committed or published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - explicit user-facing failure
    raise SystemExit(
        "Pillow is required. Install it with: python -m pip install Pillow"
    ) from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest-root",
        required=True,
        type=Path,
        help="Directory recursively containing *.conversion.json manifests.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-size", type=int, default=1024)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_size < 64:
        raise SystemExit("--max-size must be at least 64")

    manifests = sorted(args.manifest_root.rglob("*.conversion.json"))
    if not manifests:
        raise SystemExit(f"No conversion manifests found under {args.manifest_root}")
    args.output.mkdir(parents=True, exist_ok=True)

    outputs_by_shader: dict[str, dict[str, object]] = {}
    records: list[dict[str, object]] = []
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sources = manifest.get("sources") or [manifest["source"]]
        for material in manifest.get("materials", []):
            image_name = material.get("baseColorImage")
            shader = material.get("shader")
            if not image_name or not shader:
                continue
            source_index = int(material.get("sourceIndex", 0))
            if source_index < 0 or source_index >= len(sources):
                raise SystemExit(
                    f"Material {material['name']} has invalid sourceIndex "
                    f"{source_index} for {len(sources)} GLB source(s)"
                )
            source = Path(sources[source_index]["path"]).parent / image_name
            if not source.is_file():
                raise SystemExit(
                    f"Missing VRF base-color image for {material['name']}: {source}"
                )
            texture_name = Path(str(shader).replace("\\", "/")).name
            destination = args.output / f"{texture_name}.tga"

            with Image.open(source) as image:
                has_alpha = (
                    material.get("alphaMode", "OPAQUE") != "OPAQUE"
                    or "A" in image.getbands()
                )
                converted = image.convert("RGBA" if has_alpha else "RGB")
                if max(converted.size) > args.max_size:
                    scale = args.max_size / max(converted.size)
                    converted = converted.resize(
                        (
                            max(1, round(converted.width * scale)),
                            max(1, round(converted.height * scale)),
                        ),
                        Image.Resampling.LANCZOS,
                    )

                source_hash = sha256_file(source)
                previous = outputs_by_shader.get(str(shader))
                if previous and previous["sourceSha256"] != source_hash:
                    raise SystemExit(
                        f"Shader collision with different pixels: {shader}"
                    )
                if not previous:
                    converted.save(destination, format="TGA", compression=None)
                    output = {
                        "shader": shader,
                        "material": material["name"],
                        "source": str(source),
                        "sourceSha256": source_hash,
                        "sourceSize": list(image.size),
                        "alphaMode": material.get("alphaMode", "OPAQUE"),
                        "output": str(destination),
                        "outputSha256": sha256_file(destination),
                        "outputBytes": destination.stat().st_size,
                        "outputSize": list(converted.size),
                        "mode": converted.mode,
                    }
                    outputs_by_shader[str(shader)] = output
                    records.append(output)

    report = {
        "schemaVersion": 1,
        "manifestRoot": str(args.manifest_root.resolve()),
        "outputRoot": str(args.output.resolve()),
        "maxSize": args.max_size,
        "textures": records,
        "legalBoundary": (
            "These texture files are transformed from user-owned Valve data. "
            "Keep them local/untracked and do not redistribute them."
        ),
    }
    report_path = args.report or args.output.parent / "texture-conversion.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Converted {len(records)} unique base-color textures")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
