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
| `draft` | `-fast` (BSP: `-nomerge`) | `-fast -bounce 0` (`-fast` alone still runs 2 radiosity bounces: the light.log header says `Number of radiosity bounces = 2`, and its lightmaps match `-bounce 2` within 0.07 of 255) | iterating on geometry (seconds to minutes) |
| `fastrad` (`mohkit csgo` only) | `-fast` (BSP: `-nomerge`) | `-fast -bounce 2` | draft geometry with cheap bounce light, for big maps where `preview` won't finish in time (de_nuke 2,389 s of light alone, 2026-10-01) |
| `unlit` (`mohkit csgo` only) | `-fast` | none | geometry, props, doors and ladders in minutes; props flat grey |
| `preview` | full | `-bounce 2` | judging lighting faster than normal |
| `normal` | full | default (radiosity, 8 bounces) | real lighting |
| `final` | full | `-final` | release |

Draft keeps T-junction fixing although `FixTJunctions` was 281 s of a dust2 BSP: the
64-vertex face limit counts after it, so `-notjunc` drafts would hide checkerboard faces
until the release build.

The driver passes `-threads <cpu count>` to every stage, so two builds at once slow each
other about 2x: time stages only on an idle machine (testing.md "Long builds"). Full
lighting is the slow part (radiosity), so iterate on geometry with `draft`. If
multi-threaded MOHlight crashes, the driver retries with `-threads 1`, keeps the failed
run's output as `light_mt.log` and reports the exit code as a problem; the retried build
still counts as OK (`test_compile_ok_after_light_retry`). It doesn't retry when MOHlight
printed an `ERROR` (e.g. `MAX_MAP_LIGHTING`): those fail the same way on one thread.

**Verified 2026-09-30 on mk_medina:** multi-threaded MOHlight crashed on both
multi-threaded runs at the same instruction (`wine: Unhandled page fault on write
access to … at address 00433F3A`); one thread always worked. Wine then started
its crash debugger, which parked the process (the build hung ~20 min); the driver
now sets `WINEDLLOVERRIDES=winedbg.exe=d` so a crash fails fast and the retry runs.

**Static models are the likely trigger (2026-10-01):** the same mk_medina geometry with
its 107 `static_*` props held back (`build --inject-props`) lit on 10 threads without a
crash (463 s, `-fast -bounce 0`), and every converted CS:GO map (no static models since
props are injected) lit on 10 threads all night. One clean run is not proof, but it fits:
the crash was seen only on maps with MOHlight-lit static models.

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

**Never kill tools by name.** A timed-out stage used to run `pkill -f MOHlight.exe`,
which also killed the light stage of another map compiling at the same time (the dust2
build of 2026-10-01 failed that way twice). `Toolchain.kill_stragglers` now kills only
processes whose command line names the timed-out run's own compile root.

## Reading the output

`mohkit.compile.CompileResult` collects stats and every warning/error line. Right
after the BSP stage it checks face vertex counts (`face_checks`; T-junctions are
fixed by then) and **stops before VIS and light** if any face is over 64, so a bad
face costs seconds instead of a full light. After lighting it inspects the BSP
again (`bsp_checks`: limits, fence masks, lightmap pages).

| message | meaning | fix |
|---|---|---|
| `******* leaked *******`, `.lin` file written | the playable space reaches the void | seal it; the `.lin` file traces the path; use the Carver so leaks can't happen |
| `WARNING: Entity N of type 'light' leaked` | only that entity is outside the hull (stock maps have these) | harmless, but the light is wasted |
| `Entity N, Brush M: degenerate plane` | collinear face points | fix the generator |
| `LoadPortals: NumVisBytes X exceeds 2097152` | too many structural splits for VIS | make interior brushes detail; keep a simple structural hull |
| `Entity N origin is out of bounds, skipping!` for every entity (BSP), then `LoadPortals: couldn't read <map>.prt` (VIS) | the map lies outside ±8192 (de_vertigo is played 11,500 units up) | move it inside; CS:GO conversions do it automatically (`Options.offset`) |
| `MAX_MAP_DRAWINDEXES` | too many triangles after T-junction fixing | reduce detail; `-notjunc` as a last resort (risks cracks at T-junctions). Measured on mk_village: `-notjunc` cut draw indexes from 63,195 to 30,486 and draw verts from 30,644 to 20,244, same faces |
| `MAX_MAP_LIGHTING exceeded from N lightmaps` | more than 170 lightmap pages of 128×128 (the 8 MB `MAX_MAP_LIGHTING` buffer; 170 compiled, 172 failed in a test) | raise `lightmapdensity`/`surfaceDensity` on large surfaces, remove junk geometry |
| `MAX_MAP_SHADERS` (BSP stage, after writing the `.prt`) | more than 1,024 BSP shader entries. Q3map writes one entry per (shader name, surface flags, content flags), and the surface flags of every side of a brush are OR-ed together (a caulk side of a metal brush gets `metal`), so a map has 2–3 entries per shader. **But a shader name of exactly 60 characters (with `textures/`) is never matched again: every brush side using it adds an entry.** Measured on cs_nuke halves: every name of length 60 was duplicated (10 and 11 names, up to 149 entries each), no name of 51–59 was | keep shader names ≤ 59 characters (`mohkit.source.convert.MAX_SHADER_NAME`, `modelconv.texture_name`) |
| `Num lights per leaf clamped from N to 60` | too many lights reach one leaf. Not only entity lighting: on the first de_nuke draft (473 lights, a few 1024-unit leaves) the radio rooms' walls got almost no light while the light grid there was bright, so lightmaps are affected too | fewer, better placed lights; smaller leaves (structural walls, or `-blocksize`) |
| `WARNING: Could not find 'models/…/x.map'` | a prop has no collision file | normal for many props; add clip brushes if players should collide |
| `potential hash mismatch` (MOHlight) | curved-patch lighting quirk | harmless if it looks right |
| `BSP weighs in at X MB out of an allowed 10.00 MB` | advisory size | fine above 10, but watch load times |
| **bsp-check: non-.tga qer_editorimage**; in game the map drops to the menu with `LoadTGA: Only type 2 (RGB), 3 (gray), and 10 (RGB) TGA images supported` | Q3map copies each shader's `qer_editorimage` into the BSP fence-mask field and the engine loads it by exact name as a TGA (`qcommon/cm_fencemask.c`); a `.jpg` there is parsed as a TGA | name the `.tga` in `qer_editorimage` even when only the `.jpg` exists, as 205 retail shaders do (`mohkit.shaders.editor_image`) |
| **bsp-check: faces have > 64 vertices**, then one line per face: vertex count, shader, centre, x/y/z span | the renderer draws them with the default checker (`MAX_FACE_POINTS`, `renderergl1/tr_bsp.c`). The compile stops after BSP | go to the centre printed. A long face: split the brush (mohkit splits on a 512 grid automatically). A narrow face (a ceiling strip, a lintel) that many detail pieces touch: each touching edge adds T-junction vertices, so stop the pieces short of it and close the gap with one piece (see [map-format.md](map-format.md#64-vertex-faces)). `compile_map(..., stop_on_bad_faces=False)` compiles anyway |

Typical times on an Apple Silicon Mac through Wine:

| map | faces | BSP | VIS | light |
|---|---|---|---|---|
| test room | 11 | 5 s | 5 s | 6 s |
| mk_village (draft) | 5,000 | 58 s | 5 s | 225 s |
| mk_village (normal, 8 bounces) | 5,000 | 56 s | 5 s | 1,380 s |
| cs_dust2 (draft, detail in a caulk shell, 2026-09-30) | 18,200 | 1,213 s | 1 s | 3,090 s |
| cs_dust2 (draft, `-nomerge` + displacement simplification, 2026-10-01) | 18,200 | 368 s | 1 s | ~55 min |
| stock mohdm6 (normal) | 5,250 | 31 s | 110 s | 400 s |

About 5 s of each stage is Wine start-up when no wineserver is running; with another Wine
process alive in the bottle, small-map stages took 0.4-1.1 s (2026-09-30), so a persistent
wineserver (`wineserver -p`) would save ~15 s a build (untested). A compile's root, logs and
BSP are keyed by its name (`<build dir>/roots/dm_<name>/{bsp,vis,light,info}.log`): give
every variant of an A/B its own name. To test a MOHlight flag, compile one small, brightly
lit room per variant and compare `np.frombuffer(BSP(bsp).lump("lightmaps"), np.uint8)`
(mean absolute difference under 0.1 of 255 = the same result); light.log line 2 prints the
bounce count, and each phase banner (`====== Radiosity Lighting ======`) is followed by its
`(N) seconds.` line.

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
merging and patch simplification cuts the grouping work 3.9×: the draft BSP took 368 s.
Merging gains little on converted maps, whose Source faces are already merged: de_cache with
merging went from 11,763 faces to 11,538 (-2%), draw indexes 100,032 -> 98,703 (mk_village:
-30%).

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
