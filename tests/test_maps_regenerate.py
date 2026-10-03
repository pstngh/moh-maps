"""Every generated map in maps/ and tests/rooms/ still produces its committed .map: a mohkit change that alters a
map's geometry shows up here (moving helpers into mohkit must not; the proof of the
"reusable code lives in mohkit" rule in CLAUDE.md). When a change is meant to alter a map,
regenerate it with ``python -m mohkit generate maps/<name>`` and commit the new .map."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _generated(folder: Path) -> str:
    spec = importlib.util.spec_from_file_location(f"regen_{folder.name}", folder / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.build()
    m = res.to_map() if hasattr(res, "to_map") else res
    return m.dumps()


def test_maps_regenerate_identically():
    checked = 0
    for folder in sorted([*(ROOT / "maps").iterdir(), *(ROOT / "tests" / "rooms").iterdir()]):
        name = folder.name
        src = folder / f"{name}.map"
        if not (folder / "build.py").is_file() or not src.is_file():
            continue
        assert _generated(folder) == src.read_text(), f"{name}: build.py no longer produces {src.name}"
        checked += 1
    assert checked >= 3


if __name__ == "__main__":
    test_maps_regenerate_identically()
    print("ok test_maps_regenerate_identically")
