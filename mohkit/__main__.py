"""mohkit command line.

    python -m mohkit doctor                     check game, tools, wine, OpenMoHAA
    python -m mohkit new <name>                 scaffold maps/<name>/build.py from a working template
    python -m mohkit setup                      download the EA compilers (MOHTools) into .toolchain/
    python -m mohkit generate maps/<name>       write maps/<name>/<name>.map from build.py, validate it, draw its plan
    python -m mohkit build maps/<name> [-q draft|preview|normal|final] [--no-test] [--bots N --seconds S]
    python -m mohkit compile file.map --name dm/x [-q draft]
    python -m mohkit validate file.map
    python -m mohkit plan file.map [-o out.png] [--zmin Z --zmax Z]
    python -m mohkit inspect file.map|file.bsp
    python -m mohkit test file.pk3 dm/name [--shots maps/<name>] [--bots N --seconds S]
    python -m mohkit swatches stone brick [-o sheet.png]     stock materials by name, as a picture sheet
    python -m mohkit looks-like ref.png --box x0,y0,x1,y1 [--where wall] [--word stone]   texture look-alikes
    python -m mohkit compare ref.png shot.png [-o out.png] [--region name=x0,y0,x1,y1]   reference | shot | blend
    python -m mohkit install file.pk3            copy a package into the game's main/
    python -m mohkit csgo de_dust2 [--name cs_dust2] [-q draft] [--scale 1.0]   convert a CS:GO map (local/ only)
    python -m mohkit csgo de_dust2 --props-only                    re-place runtime props without recompiling
    python -m mohkit csgo de_dust2 --resume                        inject, package and test the last compile
    python -m mohkit csgo de_dust2 --shoot                         re-shoot the packaged map (sheets, shots, exposure)
    python -m mohkit csgo de_dust2 --fit-exposure                  match CS:GO's brightness (needs csgo-ref shots)
    python -m mohkit csgo de_dust2 -q fastrad --final              build, then 8 bots and the ladder probe (no install)
    python -m mohkit exposure local/csgo/*/shots [--by-map] [--stock] [--mask shot.png]   brightness check
    python -m mohkit csgo-ref de_dust2 [--name cs_dust2]        CS:GO's own screenshots from the same cameras
    python -m mohkit ab de_cache --a INSTALLED.pk3 --b NEW.pk3 [--perf 2000]   same cameras, two pk3 sets: changes, fps
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

from . import config


def cmd_doctor(a) -> int:
    cfg = config.load()
    ok = True

    def line(label, value, good):
        nonlocal ok
        ok &= bool(good)
        print(f"  [{'ok' if good else '!!'}] {label:12s} {value}")

    print("mohkit environment")
    line("game_dir", cfg.game_dir, cfg.game_dir)
    paks = cfg.retail_paks() if cfg.game_dir else []
    line("retail paks", ", ".join(p.name for p in paks) or "none", len(paks) >= 7)
    line("openmohaa", cfg.openmohaa, cfg.openmohaa)
    line("EA tools", cfg.tools_dir, cfg.tools_dir)
    line("wine", f"{cfg.wine} (bottle {cfg.wine_bottle})" if cfg.wine else "native Windows", cfg.wine is not None)
    print(f"  [--] csgo_dir     {cfg.csgo_dir}")
    print(f"  [--] build_dir    {cfg.build_dir}")
    if not cfg.tools_dir:
        print("\n  Run `python -m mohkit setup` to fetch Q3map.exe / MOHlight.exe.")
    return 0 if ok else 1


TEMPLATE = '''"""{name}: TODO one-line description.

Layout: TODO (describe the spaces and routes).
"""

from mohkit import kit
from mohkit.build import Carver, MapBuilder, Material as M
from mohkit.game import Shot

META = {{"name": "{name}", "title": "{title}", "mode": "dm", "ambience": "mohdm2"}}

FLOOR = M("central_europe/small_cobble")
PLASTER = M("general_structure/plaster_wall2")
STONE = M("general_structure/stonebricks1", (0.5, 0.5))
WOOD = M("general_structure/floor4")
CEIL = M("general_structure/plank_flat")


def build():
    b = MapBuilder("{title}", suncolor="70 66 58", sundirection="315 210 0", sundiffuse="1.2",
                   sundiffusecolor="56 62 78", ambientlight="10 10 12", farplane="6000",
                   farplane_color="0.62 0.66 0.72", farplane_cull="0")
    cv = Carver(16, sky_shader="sky/mohday2")
    b.carve(cv)
    yard = cv.room(-768, -768, 0, 768, 768, 320, floor=FLOOR, walls=[(0, STONE), (32, PLASTER)], sky=True)
    hall = cv.room(800, -256, 0, 1408, 256, 176, floor=WOOD, walls=PLASTER, ceiling=CEIL)
    cv.room(768, -64, 0, 800, 64, 128, floor=STONE, walls=STONE, ceiling=STONE)       # doorway
    kit.facade(b, cv, yard, "north", -768, 768, ((64, 144), (208, 288)), shutters=M("general_structure/beam_wood1"))
    kit.lamp(b, 1104, 0, 176)
    b.prop("static/winecasks", 1360, 200, 0, 180)
    b.prop("static/indycrate", -200, 100, 0, 20)
    spawns = [(-600, -600, 45), (600, 600, 225), (-600, 600, 315), (600, -600, 135), (0, -500, 90),
              (0, 500, 270), (1300, -180, 180), (900, 180, 0)]
    for i, (x, y, yaw) in enumerate(spawns):
        b.spawn((x, y, 1), yaw, kinds=("deathmatch", "allied" if i % 2 else "axis"))
    b.entity("info_player_start", (0, 0, 1), angle="0")
    return b


SHOTS = [
    Shot.looking_at("yard", (-700, -700, 80), (400, 400, 60)),
    Shot.looking_at("hall", (840, -220, 80), (1380, 220, 40)),
    Shot.looking_at("overview", (-900, -900, 900), (300, 0, 0)),
]
'''


def cmd_new(a) -> int:
    folder = config.REPO / "maps" / a.name
    if folder.exists():
        print(f"{folder} already exists")
        return 1
    folder.mkdir(parents=True)
    title = a.title or a.name.replace("_", " ").title()
    (folder / "build.py").write_text(TEMPLATE.format(name=a.name, title=title))
    (folder / "README.md").write_text(f"# {a.name}: {title}\n\nTODO: description, layout, how to build.\n")
    print(f"created {folder}/build.py; next: python -m mohkit build maps/{a.name} -q draft")
    return 0


def cmd_setup(a) -> int:
    dest = config.TOOLCHAIN / "MOHTools"
    if (dest / "Q3map.exe").is_file() and not a.force:
        print(f"already present: {dest}")
        return 0
    url = f"https://codeload.github.com/{a.repo}/tar.gz/refs/heads/master"
    print(f"downloading {url}")
    data = urllib.request.urlopen(url).read()
    tmp = config.TOOLCHAIN / "_dl"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(tmp, filter="data")
    top = next(tmp.iterdir())
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(top), dest)
    shutil.rmtree(tmp)
    print(f"installed to {dest}")
    return cmd_doctor(a)


def cmd_generate(a) -> int:
    from . import project, render, validate
    proj = project.Project.load(Path(a.folder))
    m = proj.generate()
    out = proj.folder / f"{proj.name}.map"
    issues = validate.check(m, validate.load_shader_index()) + validate.check_air(getattr(proj, "builder", None))
    for i in issues:
        if a.all or i.severity != "info":
            print(i)
    print(f"{out}: {sum(i.severity == 'error' for i in issues)} errors, "
          f"{sum(i.severity == 'warning' for i in issues)} warnings")
    plan = project.DIST / f"{proj.name}_plan.png"
    plan.parent.mkdir(parents=True, exist_ok=True)
    render.plan(m, str(plan))
    print(f"plan {plan}")
    if proj.underlay:
        u = dict(proj.underlay)
        image = next((p for p in (proj.folder / u["image"], config.REPO / u["image"]) if p.is_file()), None)
        if image is None:
            print(f"underlay {u['image']} not found (a local reference?): skipped")
        else:
            out_u = project.DIST / f"{proj.name}_underlay.png"
            render.underlay(m, str(out_u), str(image), tuple(u["origin_px"]), u["units_per_px"],
                            alpha=u.get("alpha", 0.5), zmin=u.get("zmin"), zmax=u.get("zmax"))
            print(f"underlay {out_u}")
    return 1 if any(i.severity == "error" for i in issues) else 0


def cmd_build(a) -> int:
    from . import project
    rep = project.build(Path(a.folder), quality=a.quality, test=not a.no_test, bots=a.bots, match_seconds=a.seconds,
                        inject_props=not a.mohlight_props)
    return 0 if rep.get("compile_ok") else 1


def cmd_compile(a) -> int:
    from . import compile as C
    res = C.compile_map(Path(a.map), a.name, quality=a.quality)
    print(res.summary())
    if res.ok and a.out:
        shutil.copy2(res.bsp, a.out)
    return 0 if res.ok else 1


def cmd_validate(a) -> int:
    from . import validate
    from .mapfile import MapFile
    m = MapFile.load(a.map)
    issues = validate.check(m, validate.load_shader_index())
    shown = [i for i in issues if a.all or i.severity != "info"]
    for i in shown:
        print(i)
    print(f"{sum(i.severity == 'error' for i in issues)} errors, {sum(i.severity == 'warning' for i in issues)} warnings")
    return 1 if any(i.severity == "error" for i in issues) else 0


def cmd_plan(a) -> int:
    from . import render
    from .mapfile import MapFile
    out = a.out or str(Path(a.map).with_suffix(".plan.png"))
    render.plan(MapFile.load(a.map), out, size=a.size, zmin=a.zmin, zmax=a.zmax)
    print(out)
    return 0


def cmd_inspect(a) -> int:
    p = Path(a.file)
    if p.suffix.lower() == ".bsp":
        from . import bsp
        print(json.dumps(bsp.BSP(p).summary(), indent=2))
        return 0
    from collections import Counter
    from .mapfile import Brush, MapFile, Patch, Terrain
    m = MapFile.load(str(p))
    kinds = Counter(type(pr).__name__ for _, pr in m.iter_prims())
    classes = Counter(e.classname for e in m.entities)
    shaders = Counter(f.shader for _, pr in m.iter_prims() if isinstance(pr, Brush) for f in pr.faces)
    print(f"{p.name}: {len(m.entities)} entities, {dict(kinds)}")
    print("worldspawn:", json.dumps(m.worldspawn.props, indent=1))
    print("classes:", ", ".join(f"{k} {v}" for k, v in classes.most_common(25)))
    print("top shaders:", ", ".join(f"{k} {v}" for k, v in shaders.most_common(25)))
    return 0


def cmd_test(a) -> int:
    from . import game
    shots = []
    stem = Path(a.pk3).stem
    if a.shots:
        from .project import Project
        shots = Project.load(Path(a.shots)).shots
        if Path(a.shots).resolve().name != stem:
            stem += "_" + Path(a.shots).resolve().name   # don't overwrite the map's own contact sheet
    r = game.run([Path(a.pk3)], a.map, shots, bots=a.bots, match_seconds=a.seconds,
                 perf_ms=a.perf, perf_toggles=_toggles(a.toggle), screenshots=not a.perf)
    print(r.summary())
    if a.perf:
        print(game.perf_table(r.perf))
        return 0
    for k, v in r.screenshots.items():
        print(f"  {k}: {v}")
    if len(r.screenshots) > 1:
        out = Path(a.out) if a.out else Path(a.pk3).with_name(stem + "_shots.png")
        print(f"== contact sheet {game.contact_sheet(r.screenshots, out)}")
    return 0


def cmd_swatches(a) -> int:
    from . import lookalike as L
    names = L.search_names(a.words)[:a.n]
    print("\n".join(names))
    print(L.swatches(names, Path(a.out)))
    return 0


def cmd_looks_like(a) -> int:
    from PIL import Image

    from . import lookalike as L
    im = Image.open(a.image).convert("RGB")
    if a.box:
        im = im.crop(tuple(int(v) for v in a.box.split(",")))
    ranked = L.rank(im, where=a.where, words=a.word or (), n=a.n, all_images=a.all)
    for name, dist in ranked:
        print(f"{dist:6.3f}  {name}")
    print(L.swatches([n for n, _ in ranked], Path(a.out), first=im))
    return 0


def cmd_compare(a) -> int:
    from . import game
    print(game.compare(Path(a.reference), Path(a.shot), Path(a.out)))
    if a.region:
        regions = {}
        for r in a.region:
            name, _, box = r.partition("=")
            regions[name] = tuple(int(v) for v in box.split(","))
        for name, m in game.measure(Path(a.reference), Path(a.shot), regions).items():
            print(f"{name:16s} reference {m['reference']}  shot {m['shot']}  ratio {m['ratio']}")
    return 0


def cmd_ab(a) -> int:
    from .source.convert import ab_local
    ab_local(a.map, [Path(x) for x in a.a], [Path(x) for x in a.b], a.name, a.scale,
             (a.label_a, a.label_b), Path(a.out) if a.out else None, shots=not a.no_shots,
             perf_ms=a.perf, rounds=a.rounds, cvars=dict(_toggles(a.cvar)) or None)
    return 0


def cmd_install(a) -> int:
    from . import pak
    cfg = config.load()
    dst = cfg.main_dir / Path(a.pk3).name
    shutil.copy2(a.pk3, dst)
    print(f"installed {dst}")
    for stem, where in pak.image_clashes(cfg.main_dir)[:10]:
        print(f"  ! {stem}: {', '.join(where)} (the game loads the .jpg)")
    clashes = pak.path_clashes(cfg.main_dir)
    if clashes:
        print(f"  ! {len(clashes)} files have the same path but different contents in several pk3s;"
              f" the game uses the first pk3 listed for every map:")
        for path, where in clashes[:10]:
            print(f"    {path}: {', '.join(where)}")
    return 0


def _toggles(specs) -> list[tuple[str, str]]:
    """``--toggle r_drawstaticmodels=0`` -> [("r_drawstaticmodels", "0")]."""
    return [tuple(t.split("=", 1)) for t in specs or ()]


def cmd_csgo(a) -> int:
    from .source.convert import build_local, resume_local
    if a.shoot:
        from .source.convert import shoot_local
        rep = shoot_local(a.map, a.name, scale=a.scale)
        return 0 if rep.get("contact_sheet") else 1
    if a.perf:
        from .source.convert import perf_local
        perf_local(a.map, a.name, scale=a.scale, ms=a.perf, toggles=_toggles(a.toggle),
                   pk3=Path(a.pk3) if a.pk3 else None, label=a.label)
        return 0
    if a.fit_exposure:
        from .source.convert import fit_exposure
        fit_exposure(a.map, a.name)
        return 0
    if a.resume:
        rep = resume_local(a.map, a.name, test=not a.no_test, exposure=a.exposure, lod=not a.no_lod)
        return _final(a) if rep.get("pk3") else 1
    if a.refresh_assets:
        from .source.convert import refresh_assets
        rep = refresh_assets(a.map, a.name, quality=a.quality, test=not a.no_test, scale=a.scale,
                             detail_all=not a.structural, max_texture=a.max_texture,
                             lighting="mohlight" if a.mohlight else "csgo")
        return 0 if rep.get("pk3") else 1
    extra = {"props_static_vertices": a.static_verts} if a.static_verts else {}
    if a.lightmap_density:
        extra["lightmap_density"] = a.lightmap_density
    if a.no_texlights:
        extra["texlights"] = False
    if a.props != "full":
        extra["prop_profile"] = a.props
    rep = build_local(a.map, a.name, quality=a.quality, test=not a.no_test, scale=a.scale,
                      detail_all=not a.structural, max_texture=a.max_texture, props_only=a.props_only,
                      lighting="mohlight" if a.mohlight else "csgo", **extra)
    return _final(a) if rep.get("compile_ok") else 1


def _final(a) -> int:
    """``--final``: the play checks after a build (bots, ladders); never installs."""
    if getattr(a, "final", False):
        from .source.convert import final_checks
        final_checks(a.map, a.name)
    return 0


def cmd_csgo_ref(a) -> int:
    from .source.reference import shoot
    return 0 if shoot(a.map, a.name) else 1


def cmd_exposure(a) -> int:
    from . import exposure as X
    if a.stock:
        X.stock_shots(per_map=a.stock_shots)
        a.paths = list(a.paths) + sorted(str(p) for p in (config.REPO / "dist" / "stock_shots").iterdir() if p.is_dir())
    if a.mask:
        for p in a.paths:
            out = Path(p).with_name(Path(p).stem + "_mask.png")
            print(X.mask(p, out))
        return 0
    if a.ref:
        _, text = X.against(Path(a.ref), [Path(p) for p in a.paths])
        print(text)
        return 0
    groups = {g: X.measure_all(imgs) for g, imgs in X.groups_in(a.paths).items()}
    if a.by_map:
        print(X.map_table(groups))
    else:
        for g, rows in groups.items():
            print(f"== {g or 'shots'}: {X.summary(rows, g)}")
            print(X.table(sorted(rows, key=lambda r: -r.score)[: a.n or None]))
    if a.json:
        X.save([r for rows in groups.values() for r in rows], Path(a.json))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mohkit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("new", help="scaffold a map project")
    s.add_argument("name")
    s.add_argument("--title")
    s.set_defaults(fn=cmd_new)
    s = sub.add_parser("setup")
    s.add_argument("--repo", default="pstngh/MOHTools")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_setup)
    s = sub.add_parser("generate", help="write and validate a project's .map, and draw its plan (no compile)")
    s.add_argument("folder")
    s.add_argument("--all", action="store_true", help="also show info-level notes")
    s.set_defaults(fn=cmd_generate)
    s = sub.add_parser("build")
    s.add_argument("folder")
    s.add_argument("-q", "--quality", default="normal", choices=["draft", "preview", "normal", "final"])
    s.add_argument("--no-test", action="store_true")
    s.add_argument("--bots", type=int, default=0)
    s.add_argument("--seconds", type=float, default=0)
    s.add_argument("--inject-props", action="store_true",
                   help="(the default) add static_* props after the light stage, lit from the lightmaps")
    s.add_argument("--mohlight-props", action="store_true",
                   help="let MOHlight light static_* props per vertex (one thread, ~190 vertices/s)")
    s.set_defaults(fn=cmd_build)
    s = sub.add_parser("compile")
    s.add_argument("map")
    s.add_argument("--name", required=True, help="game path, e.g. dm/mymap")
    s.add_argument("-q", "--quality", default="normal", choices=["draft", "preview", "normal", "final"])
    s.add_argument("-o", "--out")
    s.set_defaults(fn=cmd_compile)
    s = sub.add_parser("validate")
    s.add_argument("map")
    s.add_argument("--all", action="store_true", help="also show info-level notes")
    s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("plan")
    s.add_argument("map")
    s.add_argument("-o", "--out")
    s.add_argument("--size", type=int, default=1600)
    s.add_argument("--zmin", type=float)
    s.add_argument("--zmax", type=float)
    s.set_defaults(fn=cmd_plan)
    s = sub.add_parser("inspect")
    s.add_argument("file")
    s.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("test")
    s.add_argument("pk3")
    s.add_argument("map", help="game path, e.g. dm/mymap")
    s.add_argument("--bots", type=int, default=0)
    s.add_argument("--seconds", type=float, default=0)
    s.add_argument("--shots", metavar="FOLDER", help="use the SHOTS of this map project")
    s.add_argument("-o", "--out", help="contact sheet path (default <pk3 name>[_<shots folder>]_shots.png beside the pk3)")
    s.add_argument("--perf", type=int, default=0, metavar="MS",
                   help="time MS of uncapped frames at each camera instead of screenshots (fps, r_speeds)")
    s.add_argument("--toggle", action="append", metavar="CVAR=VALUE",
                   help="with --perf: also time each camera with this cvar set (e.g. r_drawstaticmodels=0)")
    s.set_defaults(fn=cmd_test)
    s = sub.add_parser("swatches", help="sheet of stock materials whose name contains a word")
    s.add_argument("words", nargs="+")
    s.add_argument("-n", type=int, default=36)
    s.add_argument("-o", "--out", default="dist/swatches.png")
    s.set_defaults(fn=cmd_swatches)
    s = sub.add_parser("looks-like", help="stock materials that look like a crop of a picture")
    s.add_argument("image")
    s.add_argument("--box", help="x0,y0,x1,y1 crop in pixels")
    s.add_argument("--all", action="store_true", help="also rank retail images no stock map uses")
    s.add_argument("--where", choices=["floor", "wall", "ceiling"])
    s.add_argument("--word", action="append", help="keep names containing this (repeatable)")
    s.add_argument("-n", type=int, default=23)
    s.add_argument("-o", "--out", default="dist/lookalike.png")
    s.set_defaults(fn=cmd_looks_like)
    s = sub.add_parser("compare")
    s.add_argument("reference")
    s.add_argument("shot")
    s.add_argument("-o", "--out", default="dist/compare.png")
    s.add_argument("--region", action="append", help="name=x0,y0,x1,y1: print mean colours and the brightness ratio")
    s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("ab", help="shoot a CS:GO conversion's cameras with two pk3 sets and measure what changed")
    s.add_argument("map", help="CS:GO map (cameras of local/csgo/<name>), e.g. de_cache")
    s.add_argument("--a", nargs="+", required=True, help="pk3s of set A (e.g. the installed build)")
    s.add_argument("--b", nargs="+", required=True, help="pk3s of set B (e.g. the new build)")
    s.add_argument("--name", help="converted map name (default cs_<map>)")
    s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--label-a", default="A")
    s.add_argument("--label-b", default="B")
    s.add_argument("-o", "--out", help="output folder (default local/csgo/<name>/ab)")
    s.add_argument("--perf", type=int, default=0, metavar="MS", help="also time each camera for MS, A/B interleaved")
    s.add_argument("--rounds", type=int, default=2, help="with --perf: interleaved rounds")
    s.add_argument("--no-shots", action="store_true", help="only --perf")
    s.add_argument("--cvar", action="append", metavar="NAME=VALUE",
                   help="set for both sets (e.g. r_lodscale=0.45, the user's settings)")
    s.set_defaults(fn=cmd_ab)
    s = sub.add_parser("install")
    s.add_argument("pk3")
    s.set_defaults(fn=cmd_install)
    s = sub.add_parser("csgo", help="convert a CS:GO map (output in local/, never commit it)")
    s.add_argument("map", help="map name in csgo/maps (de_dust2) or a .bsp path")
    s.add_argument("--name", help="MOHAA map name (default cs_<name>)")
    s.add_argument("-q", "--quality", default="draft", choices=["unlit", "draft", "fastrad", "preview", "normal", "final"],
                   help="unlit: BSP + fast VIS only, for geometry/prop/ladder checks in minutes")
    s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--max-texture", type=int, default=512)
    s.add_argument("--structural", action="store_true", help="keep Source world brushes structural (better VIS, may overflow)")
    s.add_argument("--static-verts", type=int, help="lit-vertex budget for compiled static props (default 70000; 0 for -q draft)")
    s.add_argument("--props-only", action="store_true",
                   help="re-place runtime props in the last compile (Q3map -onlyents, seconds); refuses other changes")
    s.add_argument("--lightmap-density", type=int, help="units per lightmap texel (default 16; 32 for -q draft)")
    s.add_argument("--texlights", action="store_true",
                   help="(the default) Source texlights (lights.rad emissive materials) -> one point light per emitting face")
    s.add_argument("--no-texlights", action="store_true", help="leave emissive materials unlit")
    s.add_argument("--refresh-assets", action="store_true",
                   help="re-convert and re-package with the last compile when only textures/models changed")
    s.add_argument("--resume", action="store_true",
                   help="only inject props, package and test what the last build left (after redoing a stage by hand)")
    s.add_argument("--no-test", action="store_true")
    s.add_argument("--final", action="store_true",
                   help="after the build: 8 bots for 90 s and every ladder probed (report.json 'final'); never installs")
    s.add_argument("--no-lod", action="store_true", help="with --resume: props without progressive LOD (A/B tests)")
    s.add_argument("--shoot", action="store_true", help="only re-shoot the packaged map (contact sheets, shots, exposure)")
    s.add_argument("--exposure", type=float, help="with --resume: tone-map CS:GO's light with this exposure")
    s.add_argument("--fit-exposure", action="store_true",
                   help="re-light the last build until it matches CS:GO's own shots (csgo-ref) and keep that "
                        "exposure in data/csgo_exposure.json")
    s.add_argument("--mohlight", action="store_true",
                   help="light with MOHlight from converted lights (default: transfer CS:GO's own baked lighting)")
    s.add_argument("--props", default="full", choices=["full", "balanced", "stock", "lean"],
                   help="prop detail (convert.PROP_PROFILES): balanced/stock drop small props, use CS:GO's "
                        "simpler meshes and shorter fades for frame rate; lean also drops overhead wires and "
                        "draws box-like props as VIS-culled brushes (use with --name, --structural)")
    s.add_argument("--perf", type=int, default=0, metavar="MS",
                   help="only time MS of uncapped frames at each camera of the packaged map (<label>.json)")
    s.add_argument("--toggle", action="append", metavar="CVAR=VALUE",
                   help="with --perf: also time each camera with this cvar set (e.g. r_drawstaticmodels=0)")
    s.add_argument("--pk3", help="with --perf: time this package instead of local/csgo/<name>/<name>.pk3")
    s.add_argument("--label", default="perf", help="with --perf: output name (<label>.json)")
    s.set_defaults(fn=cmd_csgo)

    s = sub.add_parser("csgo-ref", help="screenshots from CS:GO itself at the map's named cameras (local/ only)")
    s.add_argument("map")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_csgo_ref)

    s = sub.add_parser("exposure", help="brightness check of screenshots: mean, blown-out and crushed shares")
    s.add_argument("paths", nargs="*", help="shot images or folders (local/csgo/<map>/shots)")
    s.add_argument("--by-map", action="store_true", help="one summary line per folder")
    s.add_argument("--stock", action="store_true", help="also shoot and measure stock mohdm1-3, 5-7 and obj_team1-4 (dist/stock_shots)")
    s.add_argument("--stock-shots", type=int, default=9)
    s.add_argument("--mask", action="store_true", help="write <shot>_mask.png: red = near-white, blue = near-black")
    s.add_argument("-n", type=int, default=0, help="only the n worst shots per folder")
    s.add_argument("--json", help="write all measurements here")
    s.add_argument("--ref", help="reference shots (local/csgo/<name>/csgo_ref): compare each folder's cameras with them")
    s.set_defaults(fn=cmd_exposure)
    a = ap.parse_args(argv)
    # A redirected stdout is block-buffered: a backgrounded `mohkit build > log &` wrote nothing
    # until it exited (2026-09-30), so the log couldn't tell which stage was running.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except AttributeError:
            pass
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
