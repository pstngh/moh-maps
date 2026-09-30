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
   camera does `tele`, `face`, `fov`, `wait`, `saveshot <name>`. Bots (if any)
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
angle. Re-shoot an existing package with a project's cameras, without compiling:
`python -m mohkit test dist/x.pk3 dm/x --shots maps/x`.

The origin is the **eye** position (the harness subtracts the 82-unit eye
height before teleporting). Spectators fly, so overviews from above the roofs
work. Cover every space at player height (≈ 64–90 above the floor), looking both
ways along every route, plus interiors, stairs, one overview, and any spot a
human reported.

## Engine facts the harness depends on

- **Cheat commands need `thereisnomonkey 1`** as well as `cheats 1`; otherwise
  the first cheat command silently resets `cheats` to 0 (`fgame/entity.cpp`).
- `tele X Y Z` sets the feet position, `face P Y R` sets the view. Both go
  through the 20 Hz server, so the harness sets them, waits, sets again, then
  captures.
- `wait N` waits **N milliseconds**, but it subtracts each frame's duration, so
  a single long loading frame uses up the whole wait (`Cbuf_Execute`,
  `qcommon/cmd.c`). On stock mohdm1 every camera ran before the client was in
  game. A bare `wait` is exactly one frame, so the harness waits for loading
  with runs of bare `wait`s at `com_maxfps 60` (`game.frames`).
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
