# HANDOFF: current state and next steps (living file; keep it current)

## Overnight run rules (2026-10-01, until 06:00 America/New_York)

The user is asleep and authorized an unattended run. These rules override CLAUDE.md's
"pause at 75% context" rule for this run only:

- Do **not** pause or hand off for context. Let auto-compaction happen as often as needed.
- Keep this file current at every milestone and commit + push after tests pass, so a
  compaction loses nothing.
- Work through "Next steps" in order. Skip a step that's blocked (note why) and keep
  going. When the list runs out, add worthwhile work toward the Goal and do it.
- Don't ask questions. Make reasonable decisions and log them under "Decisions made
  while the user was away".
- Run long builds in the background and work on something else meanwhile. Never end a
  turn with nothing running before 06:00 (check `date`). Use a background waiter
  (`while kill -0 PID; do sleep 30; done`) so you're woken up.
- At 06:00 ET: finish or park the current step, update this file, commit, push, and stop
  with a short summary for the user.

## Summary (paused 2026-09-30 ~23:35, third session; overnight run until 06:00 ET next)

All work is committed and pushed to `main`. Nothing is running.

The mk_medina preview build (`-q preview --bots 8 --seconds 60`) finished at 23:28:
compile OK in 5,032 s (light on one thread), 107 static models lit, 32 lightmap pages,
**22 kills** in 60 s with 8 bots, no validation issues. `dist/mk_medina.pk3` holds
the new cornices/balconies/lighting. Its sheet `dist/mk_medina_shots.png` was shot with
the **old low-detail harness** (the process had loaded `game.py` before the fix), so
re-shoot it (step 2) before judging.

This session (third) found why converted props were black, and that **every contact
sheet so far was shot at low detail**:

- **Harness detail (verified in game):** a fresh OpenMoHAA home is near low/safe mode:
  `r_picmip 2` (quarter-size textures, the blur in old sheets), `r_fastentlight 1`
  (models lit from the light grid only, so floor props sampling grid points in solid
  were black), `r_subdivisions 20`. `game.run` now writes retail `high.cfg` values to
  the run's `autoexec.cfg` (`game.QUALITY_CVARS`), with `cg_shadows 1` because `2`
  darkens the whole frame about 3× (measured). Keep the command line short: it holds
  32 `+` commands and silently drops the rest (`+devmap` too). `docs/testing.md`.
- **Runtime prop lighting (code-read and in-game colour test):** a NOT_SOLID
  `script_model` is lit from **8 below its origin** (`q_math.c:1652`), with one sun
  trace. With a pure red `suncolor` and blue `ambientlight`, the rubble went red (sun)
  and cars and some crates went blue (ambient only: the trace from inside their own
  multi-brush hull hits another hull brush). `modelconv` now puts the origin 16 above
  the mesh's top (`LIGHT_ABOVE_TOP`), so the lighting point is 8 above the model.
  **Unverified in game:** it changed the collision hulls, so it needs a full rebuild
  (step 1). `docs/reference/engine.md` §5.2.
- **`mohkit csgo <map> --props-only`** (verified on dust2, 48 s instead of ~45 min):
  re-converts, refuses if anything but `script_model`s changed
  (`mapfile.compiled_difference`), and rewrites the entity lump of the last compile
  (`compile.update_entities`, `Q3map -onlyents`). Useful for any runtime-entity change.
  `docs/csgo-conversion.md`.
- dust2 with the new harness (props-only, centre pivots): rubble is lit, crates in shot
  03 lit, textures sharp. Cars are still dark (ambient only). Sheet:
  `local/csgo/cs_dust2/cs_dust2_shots.png`.

Trick worth reusing: to see which light reaches a runtime model, copy the compile root,
set worldspawn `suncolor "255 0 0"` and `ambientlight "0 0 60"` in the `.map`, run
`compile.update_entities` on the copy and screenshot. Red means sun, blue means ambient
only. Lightmaps are unchanged because they are baked.

Read `CLAUDE.md` first. Git: GitHub `main` (https://github.com/pstngh/moh-maps).
The old pre-restart `.git` is backed up at `~/Library/Caches/mohkit/old-git-backup`
(the user may delete it).

**Goal (confirmed by the user):** (1) convert CS:GO maps to MOHAA; (2) create
any map from scratch, whether invented, described, or **recreated from a
screenshot the user sends**, bug-free and at stock quality. Both priorities are
equal. Conversions are personal-use only.

## Environment notes

- Python: `~/Documents/moh-toolchain/venv/bin/python` (Pillow, numpy, dulwich).
- **System `git` is blocked** by an unaccepted Xcode license (`sudo xcodebuild
  -license`; the user must do that). Use the dulwich helper and **always pass
  paths**: `~/Documents/moh-toolchain/venv/bin/python ~/Documents/moh-toolchain/gitc.py commit "msg" path1 path2…`,
  then `GH_TOKEN=$(gh auth token) … gitc.py push main`. (`status`, `log` also work.)
- EA tools: `.toolchain/MOHTools` (gitignored), CrossOver Wine bottle "Steam".
  Game `~/Documents/Games/moh`, CS:GO `~/Documents/Games/csgo`, OpenMoHAA
  source `~/Documents/moh-toolchain/openmohaa-src` (cite it for engine facts).
- `~/Documents` is iCloud-synced; build scratch is `~/Library/Caches/mohkit/build`.
- Tool stages run on a pseudo-terminal: logs (`<build>/roots/<name>/*.log`)
  are live and timestamped (`Stage.timeline`, `Stage.slowest()`; summary lists
  the longest silences). No `timeout` binary on this Mac.
- Quality presets: `draft` (BSP `-nomerge`, fast VIS/light), `preview`
  (`-bounce 2`, looks like normal), `normal`, `final`.

## Next steps (in order)

1. **dust2: verify the above-top pivot.** First check why moving the pivot changed clip
   hulls by up to 20 units (Hausdorff, old vs new map; e.g. worldspawn brushes
   6716/6730, 32→35 faces). A convex hull should not depend on translation: look at
   `modelconv._hull_brush` (plane snapping/rounding relative to the origin?) and fix
   it if it's a bug. Then do the full draft rebuild: `python -m mohkit csgo de_dust2 -q draft`
   (~45 min, background it). Check that cars and crates are sunlit, that props are in
   the same places as `local/csgo/cs_dust2/cs_dust2_shots.png`, and nothing floats.
   Then bots: `python -m mohkit test local/csgo/cs_dust2/cs_dust2.pk3 dm/cs_dust2 --bots 8 --seconds 60`.
   Add the measured stage times and the props report (1,509 instances, 600 runtime,
   909 dropped) to `docs/csgo-conversion.md`.
2. **mk_medina:** the package is built; re-shoot at high detail (no compile needed):
   `python -m mohkit test dist/mk_medina.pk3 dm/mk_medina --shots maps/mk_medina --bots 8 --seconds 60`.
   Check alleys 05–07 brightness, cornices, balconies, beam ends (nothing floating or
   z-fighting), and kills (22 in the 23:28 run, 24 before). Fix, rebuild, commit, update the README.
3. **Re-judge the other maps at high detail:** re-shoot `mk_village` and `mk_ref_room`
   (`mohkit test dist/<x>.pk3 dm/<x> --shots maps/<x>`; build first if `dist/` lacks
   the pk3). Earlier lighting judgments and `docs/lighting.md` recipes were made at
   picmip 2 with grid-lit models. Correct any doc claim that no longer holds.
4. **Multi-threaded MOHlight crash** (medina light is ~55 min on one thread):
   `~/Library/Caches/mohkit/build/roots/dm_mtx` holds a copy of medina's pre-light
   BSP/VIS. Run `Toolchain().run("light_mt", "MOHlight.exe", ["-threads", "10", "-fast",
   "-bounce", "0", "-gamedir", to_tool_path(root), "-moddir", "main", to_tool_path(map)], root, 3600)`
   on it. Hypothesis: the crash is in static-model lighting (medina has 107 static
   models; dust2 drafts with 0 static models ran on 10 threads fine). Test by stripping
   `static_*` entities (or `-nostatic` at BSP), and record the result in
   `docs/toolchain.md`. If you find a safe MT setup, the driver can use it.
5. **Claim 8** (VIS overflow without the structural shell):
   `mohkit csgo de_dust2 --structural` when the machine is free (long).
6. **A second CS:GO map** (e.g. `de_inferno` or `de_mirage`) to exercise the converter
   on new content. Fix what breaks, then do bots and shots.
7. **Converter gaps** (`docs/csgo-conversion.md` "Known gaps"): `func_ladder`, water,
   overlays/decals, blend textures. Do them in order of visual impact on the maps
   converted so far.
8. Tell the user: accept the Xcode license (`sudo xcodebuild -license`), and consider
   moving the repo out of iCloud (`~/Developer/moh-maps`).

## Decisions made while the user was away

- (third session) Screenshots render at retail's high preset with full-size textures
  and blob shadows (`game.QUALITY_CVARS`): stock-quality judgments need what a player
  with a decent PC sees. Stencil shadows are off because they darken OpenMoHAA frames 3×.
- (third session) Converted models are lit from 8 above their top (pivot 16 above it),
  not from the centre: self-shadowing by their own hull is worse than an occasional
  lit-under-an-overhang prop.

- (second session) Draft light became `-fast -bounce 0`: lighting.md already said
  draft has no radiosity, and drafts are for geometry. Draft interiors are darker
  than before; judge lighting on preview or normal.
- (second session) mk_medina keeps 14 spawns per team but only 24 DM spawns: four
  choke-point or crowded spawns are team-only.

- Village accepted as final: the preview build has the latest source and looks
  the same as normal.
- Dust2's grey look in draft is the cool fill light in shadow, not the textures.
- Screenshot proof: a stock mohdm1 screenshot is the reference.
  `docs/images/ref_room_compare.jpg` (60 KB) and `mk_village.jpg` are
  committed; no retail files are.
- `mk_ref_room` was left with its door 2× too bright and slightly red walls.
  It's good enough to prove the workflow.
- `looks-like`: tiling textures to the crop's world size made every test
  worse, so that option was removed.
- Displacement simplification tolerance is 1 unit. 2 would be faster, but the
  remaining BSP phases dominate.
- Draft skips Q3map face merging but keeps T-junction fixing, so 64-vertex
  problems still show up in drafts.
- Draft conversions use 0 static-prop vertices: static-prop lighting took
  hours.
- The 160k static-vertex test on full dust2 was skipped (hours of
  single-threaded lighting).
- The pre-fix dust2 build was stopped after 2 h 47 min in prop lighting; the
  fixed draft replaced it.
- mk_medina was committed as the agent left it, a good second example. Its
  scaffold had landed earlier in ac8066e by mistake.

## Inherited claims (status)

1. `func_detail`: **tested.** It isn't stripped. It becomes an unlit, black
   generic Object. Docs fixed.
2. Lightmap pages: **tested, the limit is 170** (170 compile, 172 fail). Docs
   and bsp_checks fixed.
3. Static models: TIKI limits **verified in source**. The ~75k crash was **not
   reproduced** (161k converted props lit fine in a small map). Prop lighting is
   single-threaded at ~190 verts/s.
4. `MAX_SURFACE_INFO`: **tested.** About 1,632 shaders fit beyond retail. The
   converter warns above 1,500.
5. Multi-threaded MOHlight crash: **verified on mk_medina** (page fault at
   00433F3A, both MT runs). The driver disables winedbg (it used to hang the
   build) and retries on one thread.
6. `-notjunc`: **tested.** It halves draw indexes.
7. Terrain control layout: **verified** on 15,747 stock terrains.
8. VIS overflow without the shell: still unverified (step 4 above).
