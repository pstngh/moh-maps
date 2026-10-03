# Testing maps in OpenMoHAA

A map isn't done when it compiles. Every change is checked in the engine,
automatically, from the command line.

## What `mohkit build` / `mohkit.game.run` does

1. Builds an isolated base, `<build dir>/gamebase/`: the OpenMoHAA binary and libs plus
   symlinks to the **retail paks only**, so your mods and settings don't affect
   the test.
2. Makes a fresh home, `<build dir>/homes/<name>/main/`, with only the candidate PK3
   and a generated `harness.cfg`.
3. Launches `openmohaa +set fs_basepath … +set fs_homepath … +set cheats 1
   +set thereisnomonkey 1 … +devmap dm/<name> +exec harness.cfg`. It also sets
   `fs_apppath`, `fs_steampath`, `fs_gogpath` and `fs_microsoftstorepath` to the base:
   by default the engine searches the binary's own folder too (your game folder with
   every installed pk3, `qcommon/files.cpp` FS_InitPathVars), and until 2026-10-01 files
   missing from the candidate, or a `.jpg` twin of its `.tga` (tried first), came from
   installed maps. Check the "Current search path" lines in `qconsole.log`.
4. The harness waits ~3.5 s of rendered frames, hides the HUD, then for each
   camera does `tele`, `face`, `cg_fov`, `wait`, `saveshot <name>`. Bots (if any)
   join only after the last camera, then the match runs and the harness quits.
5. Screenshots are converted to PNG and tiled into a contact sheet
   (`dist/<name>_shots.png`). The console log is triaged for problems.

A 9-shot run takes about 20 seconds.

## Frame rate

`python -m mohkit test <pk3> <map> --perf 3000` (or `mohkit csgo <map> --perf 3000` for a
conversion's cameras) times 3 s of uncapped frames at each camera instead of taking
screenshots: `com_speeds 1` gives each frame's milliseconds, `r_speeds 1` the surfaces,
leafs, vertices and triangles drawn (`game.perf_commands`, `parse_perf`). `--toggle
r_drawstaticmodels=0` (repeatable) times each camera again with a cvar changed: what the
props cost. Close other GPU and CPU work first; compare builds in the same conditions.

Judge by the frame ms (`all`), not the `rf`/`bk` split: every 2D draw (HUD, fonts) flushes
the pending 3D commands (`R_IssuePendingRenderCommands`, `renderergl1/tr_draw.c:58` and on),
and each flush overwrites `backEnd.pc.msec` (`tr_backend.c:1492`, `=` not `+=`), so `bk`
holds only the last flush (the swap). The 3D scene's back end lands in `cl`.

Compare builds **interleaved** and only against each other: `mohkit ab <map> --a A.pk3 --b B.pk3
--no-shots --perf 2000 --rounds 2` times A, B, A, B in one run (add `--cvar r_lodscale=0.45
--cvar r_lodcap=0.35` for the user's settings); compare only within that run. The same build measured 233 fps at 07:30 and 166 at 09:20 on 2026-10-02 (a leftover
CPU-bound process: a heredoc `python -` script that had outlived its tool call; a
remote-desktop session like RustDesk also costs ~15-25%). Before timing, list the busiest
processes (`ps -Ao pid,pcpu,etime,command -r | head`) and kill strays by pid. Split the frame with `--toggle r_drawstaticmodelpoly=0` (prop vertex work off,
surfaces still sorted and visited) and `--toggle r_drawstaticmodels=0` (props off).
`mohkit propcost maps/<name> | de_dust2 [--player] [--pk3 X.pk3]` (`propcost.estimate`)
predicts drawn prop vertices per camera offline in seconds (within ~15% of r_speeds) for
comparing prop settings before a build; `--player` uses the owner's r_lodscale 0.45 /
r_lodcap 0.35. Stock models are read from the retail paks under the map (before
2026-10-02 they counted 0: mk_summit, all stock props, showed none; now 9.5k vertices per
camera on average, 17.5k at most). Binned by distance it
also tells what a fade cap buys: on de_nuke 57% of the drawn prop vertices were beyond 768
units, and capping fades there gave +33% fps.

To see where a slow frame goes, time one camera for 20 s in the background
(`game.run(..., perf_ms=20000, screenshots=False)`) and run `sample <openmohaa pid> 6 -file
out.txt`: waits under GL calls in the Main Thread tree mean draw-call or driver bound. Time
the same cameras at 640x360 and 1280x720 (`width=`, `height=`): equal ms means not
fill-bound (de_inferno: 16.35 / 76.8 / 81.4 ms vs 16.27 / 78.3 / 81.3, 2026-10-02).

**Players' settings differ from the harness.** The owner's configs have `r_lodscale 0.45`,
`r_lodcap 0.35` (harness 0.55 / 0.55: props coarser sooner), `r_fastentlight 1`,
`com_maxfps 250` (nothing above 250 fps is visible to them) and `cg_fov` 80 or 90. Shoot LOD
changes once more with those cvars (`cvars=`) before calling them artifact-free, and read fps
against the 250 cap: the worst camera matters most.

**Prop LOD artifacts:** shoot the same cameras with `cvars={"r_staticlod": "0"}`; if an
artifact goes away it is the LOD. Then bisect by packaging copies of the pk3 without the
`.lod` files of a group of models (no `.lod` = full detail) until one model is left; replay
that model's surfaces at the engine's cutoff (`lod.engine_cutoff`, `RB_StaticMesh` loop) to
see why. Geometry checks alone missed two of the three 2026-10-02 bugs (texture smear and
lost vertex lighting were on-surface).

## Cameras

Define `SHOTS` in `maps/<name>/build.py`:

```python
from mohkit.game import Shot
SHOTS = [
    Shot.looking_at("square_from_south", (0, -420, 90), (0, 200, 120)),   # eye position, target point
    Shot("overview", (-600, -700, 700), (35, 45, 0)),                    # eye, (pitch, yaw, roll)
    Shot.looking_at("tele_lens", (0, 0, 90), (400, 0, 90), fov=40),        # optional fov (default 80)
]
```

`fov` is the game's value: the horizontal angle of a 4:3 view. Wider screens keep
the vertical angle (64.4° at fov 80) and see more at the sides (`CG_CalcFov`,
`cgame/cg_view.c`). `game.fov_from_vertical(deg)` converts a photo's vertical
angle.

The engine draws fov **65 to 120** only. The harness sets the client cvar
`cg_fov`: OpenMoHAA ignores the server's `fov` command unless the player is zoomed
or in a script camera (`cgame/cg_predict.c`), and clamps `cg_fov` to 65..120 every
frame (`cgame/cg_view.c`). A narrower `fov` (a telephoto photo) is shot at 65 and
centre-cropped to the requested angle, a softer digital zoom; a wider one is drawn
at 120. Before this fix every shot was drawn at 80 whatever its `fov`.

Re-shoot an existing package with a project's cameras, without compiling:
`python -m mohkit test dist/x.pk3 dm/x --shots maps/x`. The contact sheet is
`dist/x_shots.png`; cameras from another folder write `dist/x_<folder>_shots.png`
instead, so the map's own sheet survives (`-o` picks any path).

The origin is the **eye** position (the harness subtracts the 82-unit eye
height before teleporting). Spectators fly, so overviews from above the roofs
work. Cover every space at player height (≈ 64–90 above the floor), looking both
ways along every route, plus interiors, stairs, one overview, and any spot a
human reported.

## Detail settings

Every run renders at retail's **high** preset (`Pak0.pk3:high.cfg`) with full-size
textures, written to the run's own `autoexec.cfg` (`game.QUALITY_CVARS`). A fresh
OpenMoHAA home starts near the low/safe-mode preset instead, and every contact sheet
before 2026-09-30 was shot that way:

- `r_picmip 2`: textures at a quarter of their size (the blurry look of old sheets);
- `r_fastentlight 1`: models lit from the light grid only. No sun trace and no
  `suncolor`/`ambientlight`: a test map with a pure red sun left every runtime model
  unchanged. Grid samples near a floor sit in solid, so props there rendered black;
- `r_subdivisions 20`: coarse curves.

The engine's own default for `r_fastentlight` is 0 (`renderergl1/tr_init.c:1506`) and
retail's default.cfg sets neither it nor `r_picmip`; where a fresh home's low values come
from was not found. Startup runs default.cfg, menu.cfg, `configs/omconfig.cfg`,
localized.cfg, then the home's `autoexec.cfg` (retail's own autoexec.cfg is never found); a
`custom.cfg` in the home is never executed (tried 2026-10-01). Check a cvar's effective
value in the run's `configs/omconfig.cfg` or with `cvarlist`, not its source default: the
source said `r_picmip 0` while every test home had 2, and three conclusions of 2026-09-30
(texture smear on 64-px textures, mk_ref_room's materials, the look-alike weights) were
drawn from those quarter-size textures. The qconsole line "You are now setup for medium
mode." is the single-player skill command (`server/sv_ccmds.c:1661`), not a detail preset.

Two traps: `cg_shadows 2` (high's stencil shadows) darkens the whole frame about 3×
in OpenMoHAA (mean brightness 84 → 30, measured), so the harness uses blob shadows
(1). And the command line holds at most 32 `+` commands (`MAX_CONSOLE_LINES`,
`qcommon/common.c`): extra `+set`s silently push `+devmap` off the end, and the game
idles at the console until the timeout.

Players on low/medium still get grid lighting. The CS:GO converter puts each runtime
prop's lighting point above the model, in open air, so it looks right both ways
(`docs/reference/engine.md` §5.2).

## Engine facts the harness depends on

- **Cheat commands need `thereisnomonkey 1`** as well as `cheats 1`; otherwise
  the first cheat command silently resets `cheats` to 0 (`fgame/entity.cpp`).
- `tele X Y Z` sets the feet position, `face P Y R` sets the view. Both go
  through the 20 Hz server, so the harness sets them, waits, sets again, then
  captures.
- `wait N` waits **N milliseconds**, but it subtracts each frame's duration, so
  a single long loading frame uses up the whole wait (`Cbuf_Execute`,
  `qcommon/cmd.c`). A bare `wait` holds the buffer for one `Cbuf_Execute` pass,
  and there are two passes per frame, so the harness waits for loading with runs
  of bare `wait`s (`game.frames`).
- **Custom loading screens pause the game.** A map with its own loading menu
  (stock mohdm1) shows a "continue" button and fake-pauses the local server
  when `sv_maxclients` ≤ 1 (`UI_EndLoad`, `client/cl_ui.cpp`); `tele` is then
  lost and every camera shows the spawn point. The harness sends
  `finishloadingscreen`, which dismisses it and is harmless otherwise.
- **Bots join after the cameras** (`sv_numbots` is 0 at launch and set after the
  last `saveshot`). With bots present the local spectator can end up following
  one, and every shot turns into a third-person view of a random bot.
- `ui_hud 0` must come *after* the map loads (CG_Init turns the HUD back on).
  `saveshot <name>` renders one frame without menus, HUD or spectator text
  and writes `screenshots/<name>.tga`.
- `setviewpos`, `cg_draw2D`, `cg_thirdperson`, `god` don't exist or don't work
  in OpenMoHAA (god mode is `dog 1`). Third person is `cg_3rd_person 1` (a cheat cvar,
  `cgame/cg_main.c:147`): use it to see how the player model is lit at a spot.
- Don't `tele` a player to within a unit above a patch (displacement ground): it falls
  through the patch's collision onto whatever is below (de_cbble: 46 units onto caulk).
  The harness writes `tele` coordinates as whole units, so start 4 or more units up.
  `viewpos` z minus the teleport z is about 82-84 when the player stands where intended
  (standing eye 82); much less means they fell or crouched.

## Bots

```sh
python -m mohkit build maps/mk_village --bots 8 --seconds 90
python -m mohkit test dist/mk_village.pk3 dm/mk_village --bots 8 --seconds 90
```

This sets `sv_maxbots` before the map loads (it is latched), `g_gametype 1`, and
`sv_numbots` after the cameras. The result counts kill messages in the log (`KILL_RE`:
falls such as "bot4 cratered" are not counted, so maps with drops read low). More than a
handful per minute means bots found each other and could navigate. Reference counts, 8
bots: small from-scratch maps 19-31 kills a minute (mk_village 31, mk_medina 19-24); CS:GO
conversions in 90 s: de_dust2 / de_mirage / de_nuke 66-91, de_cbble / de_vertigo 37-53,
de_cache 28-31, the big de_inferno 19-26, de_rats 13-18. The same map varies ~25% between
runs, so only a drop to a few kills, or 0, means something. For deeper checks watch a match yourself: `python -m mohkit install
dist/x.pk3`, then in game `set sv_maxbots 8; set sv_numbots 8; set g_gametype 1;
map dm/x`.

## Log triage

`RunResult.problems` lists warnings and errors minus lines every stock run
prints. Stock-noise examples: missing player models from Spearhead, the
`allied_pilot` box warning, `fx_fence_wood` precache hints, `sound/null.wav`.
Ones that matter:

`RunResult.loaded` is False and a problem is listed when the log has no "has entered the
battle" (the map never loaded: an ERR_DROP back to the menu still exits 0 after ~16 s, with
every shot of the menu or one spot); a negative exit code is a crash (`CRASHED` in the
summary, the Backtrace at the end of stdout.txt).

| line | meaning |
|---|---|
| `----- Server Shutdown (Server crashed: ...)` | the map failed to load; the reason follows (e.g. `LoadTGA: Only type 2 ...`: a `.jpg` editor image became a fence mask) |
| `No free spots open in skel cache` | more than 1,024 SKDs: props past it never load (staticmerge budget) |
| `WARNING: MAX_FACE_POINTS exceeded: N` | a face has > 64 vertices and renders as a checker (the compile's bsp-check also catches this) |
| `Couldn't find image for shader textures/…` | a material your map uses is missing |
| `Add the following line to the *_precache.scr` | cache a runtime model |
| `^~^~^ Script Error` | your `.scr` has a bug |

## Looking at screenshots

Checklist for every sheet:

- black-and-white checkerboards: a missing texture, or the 64-vertex face limit;
- black faces: no light reaches them, or inside-out geometry;
- sky visible where a wall should be;
- floating or buried props (pivot or bounds wrong);
- visible caulk (flat grey) or `nodraw` holes;
- texture scale and alignment (bricks the size of a head are wrong);
- interiors too dark in normal-quality builds, or flat and washed out
  (too much ambient);
- repetition: long identical facades need breaking up.

Also render a plan (`python -m mohkit plan maps/x/x.map`) to check layout,
spawns and lights from above before compiling.

## Measuring exposure

Judging brightness by eye from sheets misses patterns. `mohkit.exposure` measures each
shot at 1280 x 720: mean Rec. 709 luma, 5th/50th/95th percentiles, near-white (luma >=
240) and near-black (<= 16) pixel shares, blown/crushed 32-pixel blocks (mean >= 225 /
<= 20) and R/B warmth, flags shots outside a band and ranks them by a badness score:

```sh
python -m mohkit exposure local/csgo/cs_nuke/shots -n 10     # the 10 worst shots
python -m mohkit exposure local/csgo/*/shots --by-map        # one line per map
python -m mohkit exposure --stock --by-map                   # + stock mohdm1-3, 5-7, obj_team1-4 (no mohdm4 source; dist/stock_shots)
python -m mohkit exposure shot.png --mask                    # shot_mask.png: red near-white, blue near-black
python -m mohkit exposure --ref local/csgo/cs_nuke/csgo_ref local/csgo/before/cs_nuke/shots local/csgo/cs_nuke/shots
python -m mohkit exposure --changed local/csgo/before/cs_nuke/shots local/csgo/cs_nuke/shots \
    --ref local/csgo/cs_nuke/csgo_ref [-n 6] [--rank ref] [-o sheet.png]
```

`--ref` compares each folder's cameras with CS:GO's own shots of the same cameras: mean
brightness, mean absolute error and correlation of the per-camera means
(`exposure.against`). Before a rebuild meant to change the look, keep the build
(`mohkit csgo <map> --keep-before TAG`: pk3, reports and `shots/` to
`local/csgo/before/<name>_<TAG>/`); afterwards `--changed` draws
reference | before | after for the `-n` cameras that changed most (`exposure.changed_sheet`;
default `local/csgo/<name>/changed.png`) and prints every camera's pixel change (mean of the
largest channel difference, as `mohkit ab`), mean luma before -> after, the reference's and
how much closer to it the new shot is, then the `--ref` summary of both folders. `--rank ref`
orders by that last column (gains and losses alike) instead of pixel change. On
de_dust2's 2026-10-01 final rebuild the top camera changed 17.0 (T_to_Long: the ground's pale patches
appeared) and the mean |error| against CS:GO went 5.6 -> 5.0; the tunnels changed < 3.

Shot folders under `~/Documents` collect iCloud Drive conflict copies (`<name> 2.png`) when a
re-shoot replaces files during an upload (390 in local/csgo on 2026-10-02): every folder
reader goes through `exposure.shot_files`, which drops them.

Numbers find the bad shots; images decide. A single scalar can rank the wrong build first:
de_cache's mean greenness error against CS:GO was 0.57 for layer 1 only, 0.99 for a linear
blend and 0.86 for threshold blends, yet the threshold build matched CS:GO's images best
(ivy patches over panels). And a number from a contaminated test (shots that read installed
pk3s) is precisely wrong: the first exposure fits had to be redone. When fitting a mapping
between a noisy estimate and a reference, compare the two distributions' quantiles instead
of binning by the estimate: binning made the lightmap-field / MOHlight ratio fall from 3.5x
in the dark to 1.3x in the light (regression dilution); the quantiles showed a flat
1.8-2.1x, so one scale (1.78) was right.

Converted maps save their full-size shots in `local/csgo/<name>/shots/` and
`exposure.json` (`python -m mohkit csgo <map> --shoot` re-shoots the packaged map);
`csgo-ref` saves CS:GO's own shots from the same cameras (`docs/csgo-conversion.md`).
Stock MOHAA DM maps measured this way (spawn cameras, 2026-10-01) are dark and moody:
mean luma 36-63 per map with 9-25% near-black pixels; the CS:GO maps' own shots are
94-110 with 1-3%. The thresholds flag what neither does: whole areas at the cap (Nuke's
radio room, mean 183 with no shading) and crushed interiors.

## Ladders

`game.ladder_probe(pk3s, map, game.ladders_for_probe(bsp))` climbs every ladder as a
player, one game per ladder (a player still on a ladder ignores `tele`).
`ladders_for_probe` returns the BSP's `func_ladder`s plus the CS-style step ladders listed
in the `report.json` beside a converted BSP (`convert.ladders`). The probe joins a team,
`tele`s to the foot (28 units back from the climb face, or a step ladder's `probe_start`:
clear of world and prop-clip brushes, 4 units above the floor, may stand on a solid up to
16 high), faces -50 toward the wall, taps `+use` (mounts even a ladder hanging over a gap;
walking into one only works from the floor under it, and at -70 the view trace misses) and
holds `+forward` for 4 s, sampling `viewpos` every 500 ms (cgame prints `(x y z) : yaw`).
It reports the highest point, since a player who gets off at the top walks on and may drop
off the ledge (de_mirage's leaning ladder: 142 units at 1.5 s, 95 at 3 s, 1 at 4 s). A step
ladder with `hang` > 40 starts in the air at the column with `+forward` already held (a
falling player pressing into a column steps up it). `ok` = climbed at least
min(64, half its height). Stock mohdm2's three ladders climb 325, 225 and 256 units (the
last two to the top), so the probe works.

When a ladder fails: check whether the probe's start box overlaps a brush, then slice the
solids around it (clip, world and entity brushes, side and top views, from the `.map`) and
shoot it from two side angles; on de_rats that told probe problems (a start inside a clip
strip) from ladder problems (overhangs, steps too deep). After changing ladder rules,
recompute every converted map's ladder records without compiling (`Converter(bsp, game,
Options(props=False))`, then `brushes()`, `_drop_ladder_rail_clips()`, `ladders()`; ~8 s a
map) and diff them with each `report.json`: only the ladders you meant to change may move
(the first rail-clip rule also moved a de_nuke ladder 11.5 units).

## Diagnosing a wrong look

When a shot looks wrong and the data "checks out on paper", test what the game really does:

- **Which file is drawn:** repackage a copy with the suspect images filled with one solid
  colour and re-shoot the same cameras. No colour change means the game draws some other
  file (a shadowing pk3, a `.jpg` twin, another shader): check "Current search path" in
  qconsole.log. Two minutes of this found the `fs_apppath` leak after an hour of alpha maths.
- **Which light reaches a runtime model:** copy the compile root, set worldspawn
  `suncolor "255 0 0"` and `ambientlight "0 0 60"`, rewrite only the entity lump
  (`compile.update_entities`, ~17 s on dust2) and shoot: red = the sun trace reached the sky,
  blue = ambient/grid only (lightmaps stay as baked). Swap two props' positions to tell a
  position problem from a model problem.
- **What changed between two builds:** before blaming the change, diff the packages (file
  lists, changed files by type, `.jpg`/`.tga` pairs, then the BSP lump by lump) and re-shoot
  the old package with the same cameras. A "LOD broke the blends" scare was 48 stale
  `l2_*.jpg` files the package had gained.
- **What another package does to it:** `mohkit ab <map> --a X.pk3 --b X.pk3 <others>`
  shoots the same cameras with both sets and ranks them by change (`game.shots_ab`: mean
  largest-channel difference, share of pixels off by more than 40, A | B images,
  `ab_sheet.png`). It found installed CS:GO conversions overriding each other's props
  (cs_cache's Ttruck camera: 3% of the pixels; `pak.path_clashes` lists such files). The
  same command with the installed and the new build is the regression check before an install.
  Both sets must hold the same map name (`dm/<name>`): to compare variants, build them under
  one `--name` and keep the older pk3 in `local/csgo/before/`.
  Shots repeat exactly run to run except a conversion's overview camera (two runs of one
  pk3: mean 1.0, the top ~15 rows holding the previous frame and one sky face flickering), so
  check a surprising change against an A-vs-A run first.
- **What a pixel shows:** cast that camera's rays (eye, angles, fov) through the `.map` or
  both BSPs (Source and compiled) and list the first face hit with its shader and facing. A
  Source hit with no MOHAA hit is a missing face; the same hit facing away is an inside-out
  face (de_mirage's displacements); a hit on an unexpected shader names the material
  (de_cache's black panes were `effects/trainsky`). Check the camera origin too: some CS:GO
  cameras sit inside or on top of geometry. Pixels exactly in `farplane_color` mean nothing
  was drawn there.
- **How it plays:** `game.run(pk3s, map, (), extra_commands=[...])` drives a player:
  `auto_join_team`, `primarydmweapon rifle`, `tele`/`face` twice, `+attack` / `wait 100` /
  `-attack` to shoot, `+forward` or `+moveleft` held with `viewpos` every `wait 100` for a
  10 Hz position trace, `saveshot <name>` (TGA only) before and after. A stand probe (`tele`
  to a list of points, `wait 800`, `viewpos` each) maps where the collision floor really is.

## Long builds, background jobs and the shell

- Compile and light times only compare on an otherwise idle machine: every stage runs with
  `-threads <cpu count>`, so concurrent builds slow each other about 2x (de_nuke's fastrad
  light 2,389 s alone, 4,550 s with three other builds; a texlit one 3,172 s vs 6,403 s).
  Under load dust2's `-nomerge` BSP looked useless (1,257 vs 1,211 s) while merging alone
  cost 374 s. Judge threading by cumulative CPU time over wall time (`ps -o time`), not
  `%CPU`, which lags (it read 95-99% while MOHlight used 5-7 cores).
- A build or test started before an edit to mohkit runs the old code to the end: re-shoot
  its package or rebuild before judging the fix.
- Run long builds detached (`nohup ... > local/.../x.log 2>&1 &`): they get PPID 1 and
  survive the session ending, an app restart or an account switch, but not a Mac sleep or
  restart. Put each one's command, log and ETA in HANDOFF; the next session finds them with
  `ps aux | grep -E "[Q]3map|[M]OHlight|[o]penmohaa"` (the bracket keeps grep from matching
  its own command line). Keep anything a later session needs (backup pk3s, logs) under
  `local/`, never in the session scratchpad. The agent's own background-task runner stops a
  job at its timeout (2 h at most), so a queue of several conversions must be detached too.
  Its **default is 30 minutes**: a `-q normal` build of a new map (mk_summit, 2026-10-02) was
  killed mid-light and left MOHlight running as an orphan (PPID 1) whose result nothing would
  package. Pass `timeout: 7200000` for any build that may light longer than half an hour, and
  kill the orphan by pid when it happens.
- A queue that starts `python -m mohkit` once per step imports mohkit afresh at each step:
  edits made while it runs reach its later steps. Keep such edits opt-in (a new profile or
  flag) until the queue ends, or the rebuilt maps silently mix two versions of the code.
- Wait in the background: a foreground `sleep` is blocked and a foreground command is cut at
  600 s (it then keeps running unseen). Use one `until grep -q "^done" log; do sleep 30;
  done` or `while kill -0 PID; do sleep 30; done` with `run_in_background`, one watcher per
  job (two on one file report everything twice; Monitors expired after 5-30 minutes and had
  to be re-armed 6-15 times per long build). Stop your watchers before a handoff. A log that
  is appended to across runs still holds the last run's "done": truncate it when the job
  starts (`> log`), or wait with `until grep -q "^done" log && [ log -nt script ]`.
- `pgrep -f` / `pkill -f pattern` also match your own wait loops whose command line contains
  the pattern (a `pkill -f "dm_cs_nukei"` killed the loop waiting on it), while a heredoc's
  command line is just `python -`, so `pkill -f` on words from its code never matches it.
  Kill by pid, or filter `ps -axo pid=,command=` on the compile root as
  `Toolchain.kill_stragglers` does.
- Killing a batch script doesn't stop the build it started: stop its children too (mohkit
  csgo/test, Q3map.exe, MOHlight.exe, openmohaa), then check `ps`.
- mohkit refusals are `SystemExit` messages with exit code 1 and no traceback (e.g.
  `--refresh-assets` after the `.map` changed). In batch scripts record `rc=$?` and the last
  log line of each step, not a Traceback count; a step that ends in seconds instead of
  minutes failed.
- Give every variant of an A/B its own compile name: roots, logs and BSPs are keyed by
  name, so a second run silently replaces the first.
- The Bash tool runs zsh: quote globs (`grep -rn x --include='*.py'`; unquoted, zsh aborts
  with "no matches found"), quote words starting with `=` (`echo '==='`), and use `${=var}`
  or an array where a variable should split into words. macOS has no `timeout` command.
  Scripts outside the repo need `PYTHONPATH=<repo>`. Never name a scratch script after a
  stdlib module (`bisect.py`, `random.py`): its folder comes first on `sys.path`, and
  `from PIL import Image` (which imports `random`, then `bisect`) failed.
- If Bash calls fail with "auto mode classifier gave no verdict", don't retry: switch to
  Read/Edit/Write, save the pending command as a script under `local/`, record the next step
  in HANDOFF and end the turn before the 10th consecutive failure (which stops the turn).
- A regression test counts only if it fails on the code before the fix: read the old module
  from HEAD (dulwich `tree.lookup_path`), save it inside the package (`mohkit/_x_old_tmp.py`;
  a module loaded from outside breaks dataclasses), point the test at it, run it, delete the
  copy. The first LOD shard test passed the buggy code; total drawn area caught it (+35%).
