"""Tests for ``mohkit.pak`` and ``mohkit.shaders``.

Run under pytest or as a script::

    /Users/pstn/Documents/moh-toolchain/venv/bin/python tests/test_pak_shaders.py

The synthetic tests build throwaway game directories in a temp dir. The retail
tests read the installed game (``MOHKIT_GAME_DIR``, default ``~/Documents/Games/moh``)
and skip when it is missing.
"""

from __future__ import annotations

import io
import os
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mohkit.pak import GameFS, normalize, probe_image, write_pk3  # noqa: E402
from mohkit.shaders import ShaderIndex, parse_shader_text  # noqa: E402

GAME_DIR = Path(os.environ.get("MOHKIT_GAME_DIR", os.path.expanduser("~/Documents/Games/moh")))

try:  # pytest is optional
    import pytest
except ImportError:  # pragma: no cover
    pytest = None  # type: ignore[assignment]


class SkipTest(Exception):
    pass


def skip(msg: str) -> None:
    if pytest is not None:
        pytest.skip(msg)
    raise SkipTest(msg)


def _tga(w: int, h: int, bits: int = 24) -> bytes:
    return struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, bits, 8 if bits == 32 else 0) + b"\0" * 16


def _jpeg_header(w: int, h: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0\x01\x01\0\0\x01\0\x01\0\0"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, h, w, 3) + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def _make_game(root: Path) -> None:
    main = root / "main"
    main.mkdir(parents=True)
    write_pk3(str(main / "Pak0.pk3"), {
        "scripts/a.shader": b"textures/t/x\n{\n\tsurfaceparm wood\n}\n",
        "textures/t/base.tga": _tga(64, 32),
        "textures/t/both.tga": _tga(8, 8),
        "textures/t/both.jpg": _jpeg_header(16, 16),
        "Models/Static/Thing.tik": b"TIKI\n",
        "sound/a.wav": b"pak0",
    })
    write_pk3(str(main / "pak1.pk3"), {"sound/a.wav": b"pak1", "scripts/b.shader": b"textures/t/x\n{\n}\n"})
    write_pk3(str(main / "zzz_mod.pk3"), {"sound/a.wav": b"zzz"})
    (main / "sound").mkdir()
    (main / "sound" / "b.wav").write_bytes(b"loose")


# ---------------------------------------------------------------------------
# synthetic


def test_normalize() -> None:
    assert normalize("static//tree_oak.tik") == "static/tree_oak.tik"
    assert normalize("\\textures\\a\\\\b.tga") == "textures/a/b.tga"
    assert normalize("./maps/dm/x.bsp") == "maps/dm/x.bsp"


def test_write_pk3_deterministic() -> None:
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "f.bin"
        src.write_bytes(b"from disk")
        files = {"b/z.txt": b"z", "A/y.txt": b"y", "b\\x.txt": str(src)}
        p1, p2 = Path(d) / "one.pk3", Path(d) / "two.pk3"
        names = write_pk3(str(p1), files)
        write_pk3(str(p2), dict(reversed(list(files.items()))))
        assert p1.read_bytes() == p2.read_bytes()
        assert names == ["A/y.txt", "b/x.txt", "b/z.txt"]
        with zipfile.ZipFile(p1) as zf:
            assert [i.filename for i in zf.infolist()] == names
            assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in zf.infolist())
            assert zf.read("b/x.txt") == b"from disk"
        for bad in ({"../x": b""}, {"a/": b""}, {"a": b"", "A": b""}):
            try:
                write_pk3(str(Path(d) / "bad.pk3"), bad)
            except ValueError:
                continue
            raise AssertionError(f"accepted {bad}")


def test_gamefs_order_and_case() -> None:
    with tempfile.TemporaryDirectory() as d:
        _make_game(Path(d))
        fs = GameFS(d)
        assert [os.path.basename(c.path) for c in fs.containers] == ["Pak0.pk3", "pak1.pk3", "main"]
        assert fs.read("SOUND/A.WAV") == b"pak1"  # later pk3 wins, zzz_* is not retail
        assert fs.read("sound/b.wav") == b"loose"
        assert [e.origin for e in fs.sources("sound/a.wav")] == ["main/pak1.pk3", "main/Pak0.pk3"]
        assert fs.real_path("models/static/thing.tik") == "Models/Static/Thing.tik"
        assert fs.exists("models//static/THING.tik")
        assert fs.list("scripts/", ".shader") == ["scripts/a.shader", "scripts/b.shader"]
        assert fs.engine_list("scripts", ".shader") == ["scripts/b.shader", "scripts/a.shader"]
        everything = GameFS(d, pak_filter=lambda n: True)
        assert everything.read("sound/a.wav") == b"zzz"
        assert GameFS(d, loose=False).exists("sound/b.wav") is False


def test_find_image_and_probe() -> None:
    with tempfile.TemporaryDirectory() as d:
        _make_game(Path(d))
        fs = GameFS(d)
        assert fs.find_image("t/base") == "textures/t/base.tga"
        assert fs.find_image("textures/t/base.jpg") == "textures/t/base.tga"
        assert fs.find_image("t/both.tga") == "textures/t/both.jpg"  # r_loadjpg: .jpg first
        assert fs.find_image("t/missing") is None
        assert fs.image_size("t/base") == (64, 32)
        assert fs.image_size("textures/t/both.jpg") == (16, 16)
        info = probe_image(io.BytesIO(_tga(128, 256, 32)), "x.tga")
        assert info is not None and (info.width, info.height, info.has_alpha) == (128, 256, True)


def test_shader_parser_quirks() -> None:
    text = (
        "// header comment\r\n"
        "/* block\r\n comment */\r\n"
        "// for use as a clip\r\n"
        "textures/q/one\r\n{\r\n"
        "  qer_editorimage textures/q/one_ed.tga // trailing\r\n"
        "  surfaceparm  Nodraw\r\n  surfaceParm trans\r\n"
        "  fullbright\r\n"
        "  {\r\n    map textures/q/env.tga\r\n    tcGen environment\r\n  }\r\n"
        "  {\r\n    map textures/q/one.tga\r\n    blendFunc GL_SRC_ALPHA GL_ONE_MINUS_SRC_ALPHA\r\n"
        "    nextbundle\r\n    map $lightmap\r\n  }\r\n"
        "}\r\n"
        "textures/q/two\n{\n\tsurfaceparm stone\n\t{\n\t\tanimMap 2 textures/q/f1.tga textures/q/f2.tga\n"
        "\t\talphaFunc GE128\n\t}\n"
        "textures/q/three\n{\n\tskyParms env/sky 512 -\n\tcull none\n}\n"
        "textures/q/one\n{\n\tsurfaceparm metal\n}\n"
    )
    defs, problems = parse_shader_text(text, "scripts/q.shader")
    assert [d.name for d in defs] == ["textures/q/one", "textures/q/two", "textures/q/three", "textures/q/one"]
    one, two, three = defs[0], defs[1], defs[2]
    assert one.comment == "for use as a clip"
    assert one.surfaceparms == ["nodraw", "trans"] and one.editor_image == "textures/q/one_ed.tga"
    assert one.stage_image == "textures/q/one.tga" and one.stages[0].env and one.stages[1].uses_lightmap
    assert one.images == ["textures/q/env.tga", "textures/q/one.tga"]
    assert not one.transparent  # the opaque env stage comes first
    assert "fullbright" in one.unknown
    assert two.images == ["textures/q/f1.tga", "textures/q/f2.tga"] and two.alpha_tested and two.transparent
    assert two.material == "stone" and two.unknown_parms == ["stone"]
    assert any("missing '}'" in p for p in problems) and "missing '}' before 'textures/q/three'" in two.warnings
    assert three.skyparms == ["env/sky", "512", "-"] and three.cull == "none" and three.is_sky
    idx = ShaderIndex.from_texts([("scripts/q.shader", text)])
    assert idx.get("q/one").surfaceparms == ["metal"]  # last definition in a file wins
    assert len(idx.all_defs["textures/q/one"]) == 2
    idx2 = ShaderIndex.from_texts([("scripts/b.shader", "textures/q/one\n{\n surfaceparm wood\n}\n"),
                                   ("scripts/q.shader", text)])
    assert idx2.material("q/one") == "wood"  # first listed file wins


def test_shader_index_on_fs() -> None:
    with tempfile.TemporaryDirectory() as d:
        _make_game(Path(d))
        fs = GameFS(d)
        idx = ShaderIndex.from_fs(fs)
        assert idx.files == ["scripts/b.shader", "scripts/a.shader"]
        assert idx.surfaceparms("t/x") == []  # pak1's b.shader is listed first and wins
        assert idx.exists("t/x") and idx.exists("t/base") and not idx.exists("t/nope")
        assert idx.resolve_image("t/base") == "textures/t/base.tga"


# ---------------------------------------------------------------------------
# retail data


def _retail() -> GameFS:
    if not (GAME_DIR / "main" / "Pak0.pk3").is_file():
        skip(f"no retail game data at {GAME_DIR}")
    return GameFS(str(GAME_DIR), ("main",), loose=False)


def test_retail_gamefs() -> None:
    fs = _retail()
    names = [os.path.basename(c.path) for c in fs.containers]
    assert names[0] == "Pak0.pk3" and names[-1].lower() == "pak7.pk3"
    assert not any(n.lower().startswith("zzz") for n in names)
    assert fs.entry("scripts/tigertank.shader").pak == "pak7.pk3"
    assert fs.find_image("common/caulk") == "textures/common/caulk.tga"
    assert fs.image_size("general_structure/stonewall2") == (256, 256)
    assert fs.engine_list("scripts", ".shader")[0].lower() in {s.lower() for s in fs.list("scripts/", ".shader")}


def test_retail_common_shaders() -> None:
    fs = _retail()
    idx = ShaderIndex.from_fs(fs)
    assert len(idx) > 4000 and not idx.problems
    caulk = idx.get("common/caulk")
    assert caulk is not None and caulk.source == "scripts/common.shader" and caulk.pak == "Pak0.pk3"
    assert set(idx.surfaceparms("common/caulk")) == {"nodraw", "nomarks"}
    assert {"nonsolid", "playerclip", "monsterclip"} <= set(idx.surfaceparms("common/clip"))
    assert {"nonsolid", "weaponclip"} <= set(idx.surfaceparms("common/weapon"))
    assert "nonsolid" in idx.surfaceparms("common/nodraw")
    assert idx.material("common/metalclip") == "metal"
    assert idx.material("common/stoneclip") == "stone"  # not a Q3map surfaceparm (it knows "rock")
    assert idx.get("sky/mohday1").skyparms[0] == "env/mohday1"
    assert idx.resolve_image("mohcommon/window5").lower() == "textures/mohcommon/window5.tga"
    assert idx.exists("general_structure/stonewall2") and not idx.exists("common/weaponclip")


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except SkipTest as e:
            print(f"SKIP {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print("FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
