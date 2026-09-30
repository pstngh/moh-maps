# Toolchain: setup, compiling, packaging

## What you need

| piece | where it comes from | used for |
|---|---|---|
| Retail Allied Assault data (`main/Pak0.pk3` … `Pak6EnUk.pk3`, `pak7.pk3`) | your game install | compiling (shader scripts!) and playing |
| EA compilers **Q3map.exe 1.34** and **MOHlight.exe 1.48** | [pstngh/MOHTools](https://github.com/pstngh/MOHTools) (MOHRadiant SDK) | BSP, VIS, lighting |
| Wine (CrossOver on macOS) | CrossOver.app / `wine` | running the 32-bit Windows compilers off Windows |
| OpenMoHAA | your install | automated testing, screenshots, bots |
| Python ≥ 3.10 + Pillow + numpy | `pip install pillow numpy` | mohkit |

```sh
python3 -m venv .venv && .venv/bin/pip install pillow numpy
.venv/bin/python -m mohkit setup      # downloads MOHTools into .toolchain/ (gitignored)
.venv/bin/python -m mohkit doctor     # shows what was found
```

Paths are auto-detected. Override them with environment variables
(`MOHKIT_GAME_DIR`, `MOHKIT_OPENMOHAA`, `MOHKIT_TOOLS_DIR`, `MOHKIT_WINE`,
`MOHKIT_WINE_BOTTLE`, `MOHKIT_CSGO_DIR`) or a `mohkit.local.json` at the repo root
with the same keys in lower case without the prefix (see `mohkit/config.py`).

On macOS, CrossOver's wine runs the tools inside an existing bottle
(`--bottle <name> --wait-children`); any bottle works. Paths are passed as
`Z:\…` (Wine maps `/` to `Z:`).

## The pipeline

```text
.map ──Q3map──▶ .bsp + .prt ──Q3map -vis──▶ .bsp (+vis) ──MOHlight──▶ lit .bsp ──zip──▶ .pk3
```

`python -m mohkit build maps/<name>` does all of it, and `mohkit.compile.compile_map`
is the library call. Each compile gets a fresh **game root**:

```text
<build dir>/roots/<name>/main/Pak0.pk3 … pak7.pk3     symlinks to the retail paks
<build dir>/roots/<name>/main/textures/…              the map's own assets (loose)
<build dir>/roots/<name>/main/maps/dm/<name>.map
```

Rules learned the hard way:

- **Always compile against the retail paks.** Q3map takes surface and content
  flags from `scripts/*.shader`. Without them `common/caulk` is an ordinary
  (missing) texture and skies aren't skies: the map compiles, then renders
  with black holes.
- **Compile against retail only, not a mod-heavy `main`.** Q3map loads every
  shader script it can see and holds a fixed number (`MAX_SURFACE_INFO`,
  consistent with q3map's 4096). Tested 2026-09-30: on top of the retail
  scripts, 1,632 extra script shaders compile and 1,639 fail with
  `MAX_SURFACE_INFO`. So a map (or the mods in `main`) may add about **1,600
  shaders**; a large conversion with many prop materials can get close.
- The map's own textures and shader scripts must be in the compile root too.
  Lightmap sizes and surface flags come from them.

## Commands

The driver runs the equivalent of:

```text
Q3map.exe   -threads N -gamedir <root> -moddir main  <root>\main\maps\dm\x.map    BSP
Q3map.exe   -vis -threads N [-fast] -gamedir … x.map                              VIS
MOHlight.exe -threads N [-fast|-final] -gamedir … x.map                           light
Q3map.exe   -info <root>\main\maps\dm\x.bsp                                       sizes
```

| mohkit quality | VIS | MOHlight | use |
|---|---|---|---|
| `draft` | `-fast` (BSP: `-nomerge`) | `-fast` | iterating on geometry (seconds to minutes) |
| `preview` | full | `-bounce 2` | judging lighting faster than normal |
| `normal` | full | default (radiosity, 8 bounces) | real lighting |
| `final` | full | `-final` | release |

The driver passes `-threads <cpu count>` to every stage. Full lighting is the
slow part (radiosity), so iterate on geometry with `draft`. If multi-threaded
MOHlight crashes (an access violation was seen once on a large map), the
driver retries with `-threads 1`, keeps the failed run's output as
`light_mt.log` and reports the exit code as a problem. It doesn't retry when
MOHlight printed an `ERROR` (e.g. `MAX_MAP_LIGHTING`): those fail the same way
on one thread. (**UNVERIFIED**: whether multi-threading itself ever causes a
crash. The single report predates these logs.)

### Q3map 1.34 options (BSP stage)

`-v -threads N -info -vis -nowater -nofill -nodetail -nohint -fulldetail
-onlyents -nosubdivide -leaktest -verboseentities -nocurves -notjunc -expand
-detailterrainborders -fakemap -nomerge -lightmapdensity D -smoothangle A
-blocksize S (default 1024, 0 = off) -chopblocklast -nomanvis -nostatic
-visiblestatic -gamedir -moddir`. `-snapdistance` is ignored ("disabled in code").
`-onlyents` rewrites only the entity lump. It does **not** update static models;
changing props needs a full compile.

### VIS options

`-fast -level N -nosort -deleteprt -nofarplane -farplane N -threads`. VIS also
reads worldspawn `farplane`, `farplane_cull`, `vis_derived`.

### MOHlight 1.48 options

| option | default | meaning |
|---|---|---|
| `-fast` / `-final` / `-extra` | | quality presets; `-extra` = extra sun sampling |
| `-bounce N` | 8 | radiosity bounces (needs VIS data, otherwise radiosity is off) |
| `-radscale X` | 0.95 | radiosity strength, 0 = none |
| `-attenuate N` | 4 | % of bounced light lost per 16 units |
| `-chop N`, `-minchop N` | 64, 64 | radiosity patch size |
| `-ambient R G B` | | ambient override (0–255 scale) |
| `-point X`, `-area X` | 1.0 | scale all point lights / surface lights |
| `-nogrid -onlygrid -extragrid -radgrid` | | entity light grid control |
| `-notrace -nosurfshadows -nocurveshadows -nopatchshadows -staticshadows` | | shadow control |
| `-nodiffusesun -nopatchlight -nocurvelight -vertex -smoothangle N` | | misc |

**MOHlight with no arguments waits for a keypress.** The driver runs every tool
with stdin closed so this can't hang a build.

## Reading the output

`mohkit.compile.CompileResult` collects stats and every warning/error line. After
lighting it also inspects the BSP (`bsp_checks`).

| message | meaning | fix |
|---|---|---|
| `******* leaked *******`, `.lin` file written | the playable space reaches the void | seal it; the `.lin` file traces the path; use the Carver so leaks can't happen |
| `WARNING: Entity N of type 'light' leaked` | only that entity is outside the hull (stock maps have these) | harmless, but the light is wasted |
| `Entity N, Brush M: degenerate plane` | collinear face points | fix the generator |
| `LoadPortals: NumVisBytes X exceeds 2097152` | too many structural splits for VIS | make interior brushes detail; keep a simple structural hull |
| `MAX_MAP_DRAWINDEXES` | too many triangles after T-junction fixing | reduce detail; `-notjunc` as a last resort (risks cracks at T-junctions). Measured on mk_village: `-notjunc` cut draw indexes from 63,195 to 30,486 and draw verts from 30,644 to 20,244, same faces |
| `MAX_MAP_LIGHTING exceeded from N lightmaps` | more than 170 lightmap pages of 128×128 (the 8 MB `MAX_MAP_LIGHTING` buffer; 170 compiled, 172 failed in a test) | raise `lightmapdensity`/`surfaceDensity` on large surfaces, remove junk geometry |
| `Num lights per leaf clamped from N to 60` | too many lights reach one leaf | fewer, better placed lights |
| `WARNING: Could not find 'models/…/x.map'` | a prop has no collision file | normal for many props; add clip brushes if players should collide |
| `potential hash mismatch` (MOHlight) | curved-patch lighting quirk | harmless if it looks right |
| `BSP weighs in at X MB out of an allowed 10.00 MB` | advisory size | fine above 10, but watch load times |
| **bsp-check: non-.tga qer_editorimage**; in game the map drops to the menu with `LoadTGA: Only type 2 (RGB), 3 (gray), and 10 (RGB) TGA images supported` | Q3map copies each shader's `qer_editorimage` into the BSP fence-mask field and the engine loads it by exact name as a TGA (`qcommon/cm_fencemask.c`); a `.jpg` there is parsed as a TGA | name the `.tga` in `qer_editorimage` even when only the `.jpg` exists, as 205 retail shaders do (`mohkit.shaders.editor_image`) |
| **bsp-check: faces have > 64 vertices** | the renderer draws them with the default checker (`MAX_FACE_POINTS`, `renderergl1/tr_bsp.c`) | split long brushes (mohkit splits on a 512 grid automatically) |

Typical times on an Apple Silicon Mac through Wine:

| map | faces | BSP | VIS | light |
|---|---|---|---|---|
| test room | 11 | 5 s | 5 s | 6 s |
| mk_village (draft) | 5,000 | 58 s | 5 s | 225 s |
| mk_village (normal, 8 bounces) | 5,000 | 56 s | 5 s | 1,380 s |
| cs_dust2 (draft, detail in a caulk shell) | 18,200 | 1,213 s | 1 s | 3,090 s |
| stock mohdm6 (normal) | 5,250 | 31 s | 110 s | 400 s |

About 5 s of each stage is Wine start-up.

**Where BSP time goes.** The driver runs each tool on a pseudo-terminal, so
logs are live (Wine's C runtime buffers output to files and pipes until
exit, but flushes every line to a terminal) and every line is timestamped
(`Stage.timeline`; `CompileResult.summary()` lists the longest silences of
stages over a minute). Measured with Q3map `-v` on mk_village: 65 of 84 s
is **"Merging faces"**. `-nomerge` skips it: 23 s instead of 84 s, for 30%
more draw surfaces (6,552 vs 5,041) and 17% more draw indexes. Use it for
iteration on big maps; keep merging for release builds (`-q draft` uses it).

cs_dust2 (23k faces, 619 patches), 1,360 s under load: `PatchMapDrawSurfs` 673 s
(patch LOD grouping compares every control point pair: see csgo-conversion.md),
"Merging faces" 374 s, `FixTJunctions` 281 s, everything else ~30 s. Draft skips
merging and patch simplification cuts the grouping work 3.9×, so a draft BSP
should take about a third of that.

## Packaging

A `.pk3` is a zip with forward-slash names. `mohkit.project.write_pk3` writes
sorted entries with fixed timestamps, so identical inputs give identical bytes.

```text
maps/dm/<name>.bsp
maps/dm/<name>.scr               level script (see scripting.md)
maps/dm/<name>_precache.scr
maps/dm/<name>.min               optional: loading-bar data (OpenMoHAA writes one after first load)
textures/…  scripts/….shader  models/…  env/…     only your own assets
```

Never ship `.prt`, `.vis`, `.lin`, or retail/commercial assets. Install by
copying the `.pk3` into the game's `main/` (`python -m mohkit install x.pk3`),
then `map dm/<name>` (FFA needs `g_gametype 1`).

## Editors

- **MOHRadiant** (EA, in MOHTools) runs under Wine. Point the project at the game
  dir and put `entdefs.pk3` in `main/`.
- **NetRadiant-custom** with a MOHAA gamepack (experimental, not verified here): the fork
  [pstngh/netradiant-custom](https://github.com/pstngh/netradiant-custom) branch
  `codex/macos-openmohaa` adds a native macOS build, MOHAA `.map` + `terrainDef`
  editing, and entity definitions generated from OpenMoHAA. Its q3map2 MOHAA
  backend doesn't write static models, terrain LOD or sphere lights yet, so
  keep compiling with the EA tools.
- Anything mohkit writes opens in both editors.
