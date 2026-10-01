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

## Summary (overnight run in progress, 2026-10-01; fourth session)

**Live state (update as you go, 00:52):**
- Nuke **unlit** build `cs_nukeu` (00:35-00:43; BSP 261 s, VIS 1 s, 4,801 props injected,
  38 named-camera shots): reads clearly as Nuke (layout, props, overlays/signage, B-site
  reactor and pool under the glass grid, doors, open vents). **Bots: 83 kills in 90 s**
  with 8 bots, navmesh built in 10 s, nothing stuck. **Ladders (`game.ladder_probe`): 5 of
  6 climbed**; the A-site one hangs 47 units above the box you climb from: fixed (trigger
  extended down to the floor in front), not yet re-verified. Sheet bugs fixed since:
  light-shaft cards drawn solid white (additive now alpha-weighted, unlit materials
  `rgbGen identity`), asphalt cracks as grey squares (DecalModulate -> modulate decal).
- Running: Nuke lit draft `cs_nuke` (started 00:24, light 39% at 00:49, built from code
  before those fixes and before ropes/func_brush handling), dust2 draft (light started
  ~00:46, slow first %), both in the session scratchpad logs.
- Next: look at the lit Nuke sheet, then a fresh Nuke build with every fix (unlit first
  for ladders/geometry, then lit), bots, then the final-quality decision.

Done this run (all committed and pushed):
- Step 1: `modelconv._hull_brush` is translation-invariant (merge test was origin-relative).
- **MAX_MAP_SHADERS on de_nuke:** EA Q3map never de-duplicates BSP shader entries whose
  name (with `textures/`) is exactly 60 characters: one entry per brush side. Names are
  now capped at 59 (`convert.MAX_SHADER_NAME`, `modelconv.texture_name`). docs/toolchain.md.
- **`mohkit.staticlight`**: static models injected into the lit BSP, vertex colours from
  the BSP light grid (calibrated to MOHlight means). The converter's default
  `props_mode="inject"` makes all 4,801 Nuke props static models (no MOHlight time, no
  entities) with clip brushes. `tests/test_staticlight.py`.
- Converter: ladders → `func_ladder`; water → water shader + `common/waterskip`; glass
  `func_breakable` → `func_window`; `info_overlay` → decal patches (`ov_*` shaders);
  contact sheets from `maps/<map>_cameras.txt` (36 Nuke cameras), pages of 9.
- Trap: a scratchpad script named `bisect.py` shadowed the stdlib module (PIL imports it).

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

**User's priority:** chat (2026-09-30 23:34): de_nuke first, as perfect as possible, then
de_mirage. HANDOFF edit (23:45): finish de_dust2 first, time-boxed to ~02:00, then Nuke,
then Mirage. Don't use the pre-restart Nuke work (`~/Library/Caches/mohkit/old-git-backup`).

1. **de_nuke** (`python -m mohkit csgo de_nuke`, output `local/csgo/cs_nuke/`; quick checks
   with `-q unlit --name cs_nukeu`):
   - Look at the lit draft sheet (`cs_nuke_shots*.png`, 38 named cameras) and fix what it
     shows; rebuild with every fix since 00:24 (ropes, func_brush, beams, cracks, ladders).
   - Re-run `game.ladder_probe` (script pattern in `docs/testing.md`): all 6 ladders must climb.
   - Bots: `python -m mohkit test local/csgo/cs_nuke/cs_nuke.pk3 dm/cs_nuke --bots 8 --seconds 90`.
   - Final lighting: drafts are `-fast -bounce 0` at lightmap density 32. Decide between
     `-q preview` (radiosity) at density 32 and the draft, from the time a draft takes alone.
   - Known gaps: vent slats/breakable vent covers are left open (not converted); door
     handles are lost; sprites and detail grass are dropped.
2. **de_dust2**: draft running (fresh, density 32). Look at the sheet (23 named cameras),
   bots, record stage times in `docs/csgo-conversion.md`.
3. **de_mirage** the same way (`de_mirage_cameras.txt`; 93 entity props now converted).
4. From-scratch maps could use `staticlight` too: MapBuilder props compiled as
   `static_*` cost mk_medina ~55 min of single-threaded MOHlight. Add an opt-in
   `build --inject-props` (needs a GameFS reader for retail TIKI/SKD in `tiki_mesh`) and
   compare a sheet against MOHlight's lighting before making it the default.
5. **Multi-threaded MOHlight crash** (medina's static models): less urgent now that
   conversions inject props. `~/Library/Caches/mohkit/build/roots/dm_mtx` has the BSP.
6. **mk_medina** re-shoot at high detail:
   `python -m mohkit test dist/mk_medina.pk3 dm/mk_medina --shots maps/mk_medina --bots 8 --seconds 60`;
   then `mk_village`, `mk_ref_room`, and correct `docs/lighting.md` claims made at low detail.
7. **Claim 8** (VIS overflow without the structural shell): `mohkit csgo de_dust2 --structural`.
8. Tell the user: accept the Xcode license (`sudo xcodebuild -license`), and consider
   moving the repo out of iCloud (`~/Developer/moh-maps`).

## Decisions made while the user was away

- (fourth session) The chat said "de_nuke first"; HANDOFF (edited 23:45, after the run
  started) says finish dust2 first, time-boxed to ~02:00. Did step 1, then built the
  converter features both maps need while Nuke compiled, and started a dust2 rebuild at
  00:00 in parallel with the Nuke build. Nuke is the main focus after ~02:00.
- (fourth session) All props are injected static models (`staticlight`), not MOHlight-lit
  `static_*` or `script_model`s: 4,801 Nuke props would light for hours on one thread and
  the entity limit is 1,024. Per-vertex colours come from the 32-unit light grid
  (calibrated to MOHlight's means), so fine prop self-shadowing is lost.
- (fourth session) Doors (`prop_door_rotating`) and the breakable vent slats
  (`prop_dynamic` opened by `func_button`/`OnBreak`) aren't converted yet, so those
  doorways and vents are open. Converting doors needs a brush door with a baked texture
  or a scripted `script_model`; decide after the first Nuke sheet.

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
