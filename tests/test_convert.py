"""Small tests for the CS:GO converter's helpers (no game data needed).

    ~/Documents/moh-toolchain/venv/bin/python tests/test_convert.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit.source import convert as C  # noqa: E402
from mohkit.source import modelconv as mc  # noqa: E402


def test_named_cameras() -> None:
    text = '''// comment "Not" "1 2 3 4 5"
"Cameras"
{
\t"T Spawn"\t\t"-2385.6 -1200.0 -230.2 29.1 151.1"
\t"B1"\t"548.7 -118.7 -457.9 30.2 -69.9"
}
'''
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "de_x_cameras.txt"
        p.write_text(text)
        cams = C.named_cameras(p, scale=2.0)
    assert [c.name for c in cams] == ["T Spawn", "B1"]
    assert cams[0].origin == (-4771.2, -2400.0, -460.4) and cams[0].angles == (29.1, 151.1, 0.0)


def test_shader_names_fit_q3map() -> None:
    """Q3map duplicates BSP shader entries of 60-character names (docs/toolchain.md)."""
    assert C.MAX_SHADER_NAME == 59
    long = "models/props/de_nuke/hr_nuke/nuke_light_fixture/nuke_fluorescent_light_cable_32"
    assert len(mc.texture_name(long)) <= 59
    assert len(mc.texture_name("metal/hr_metal/hr_metal_corrugated_001x")) <= 59


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
