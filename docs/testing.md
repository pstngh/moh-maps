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
   +set thereisnomonkey 1 … +devmap dm/<name> +exec harness.cfg`.
4. The harness waits ~3.5 s of rendered frames, hides the HUD, then for each
   camera does `tele`, `face`, `cg_fov`, `wait`, `saveshot <name>`. Bots (if any)
   join only after the last camera, then the match runs and the harness quits.
5. Screenshots are converted to PNG and tiled into a contact sheet
   (`dist/<name>_shots.png`). The console log is triaged for problems.

A 9-shot run takes about 20 seconds.

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
  in OpenMoHAA (god mode is `dog 1`).

## Bots

```sh
python -m mohkit build maps/mk_village --bots 8 --seconds 90
python -m mohkit test dist/mk_village.pk3 dm/mk_village --bots 8 --seconds 90
```

This sets `sv_maxbots` before the map loads (it is latched), `g_gametype 1`, and
`sv_numbots` after the cameras. The result counts kill messages in the
log. More than a handful per minute means bots found each other and could
navigate. For deeper checks watch a match yourself: `python -m mohkit install
dist/x.pk3`, then in game `set sv_maxbots 8; set sv_numbots 8; set g_gametype 1;
map dm/x`.

## Log triage

`RunResult.problems` lists warnings and errors minus lines every stock run
prints. Stock-noise examples: missing player models from Spearhead, the
`allied_pilot` box warning, `fx_fence_wood` precache hints, `sound/null.wav`.
Ones that matter:

| line | meaning |
|---|---|
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
