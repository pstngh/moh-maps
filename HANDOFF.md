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

## Summary (overnight run 2026-10-01, fourth session; ended 06:00 ET)

**Results (local only, `local/` is gitignored; install with
`python -m mohkit install local/csgo/cs_nuke/cs_nuke.pk3`, then `map dm/cs_nuke`):**

| map | pk3 | build | bots (8, 90 s) | ladders | notes |
|---|---|---|---|---|---|
| de_nuke | `local/csgo/cs_nuke/cs_nuke.pk3` (05:29, spot fix) | fastrad, BSP 200 s, light 2,389 s | **70 kills**, none stuck | **6/6** (A-site one: +use from the ledge) | 4,801 props, 718 overlays, 6 doors, 3 breakable vents, 38 glass windows, 70 ropes, 78 glows, water; interiors now lit |
| de_mirage | `local/csgo/cs_mirage/cs_mirage.pk3` (04:25, before the spot fix) | fastrad, BSP 262 s, light 3,838 s | **81 kills**, none stuck | 2/3 (leaning ladder: falls off the top) | 1,470 props, 512 overlays, 85 ropes, 35 glows, 3 breakable covers/shutter + 3 windows; shops dark |
| de_dust2 | `local/csgo/cs_dust2/cs_dust2.pk3` (04:14, before the spot fix) | fastrad, BSP 684 s, light 2,752 s | **91 kills**, none stuck | — | 1,574 props, 459 overlays |

Contact sheets: `local/csgo/<name>/<name>_shots*.png` (CS:GO's named spectator cameras).

**State at 06:00:** nothing is running. At 04:40 I found that every converted
`light_spot` pointed the wrong way (VRAD: z = +sin(pitch); ceiling spots lit ceilings),
which was why Nuke's radio rooms/lobby and Mirage's shops were dark. Nuke was rebuilt with
the fix (interiors now lit, `local/csgo/cs_nuke/cs_nuke_shots_3.png`); **Mirage and dust2
were not**: rebuild them first next session (`python -m mohkit csgo de_mirage -q fastrad`,
then de_dust2; ~45-60 min each alone). Mirage's folder holds the map/assets of a stopped
04:44 conversion next to its 04:25 pk3. Earlier packages are backed up in the session
scratchpad only (`cs_nuke_final_0437.pk3` etc.); they will be lost with it.

Done this run (all committed and pushed; details in `docs/csgo-conversion.md`):
- Step 1: `modelconv._hull_brush` is translation-invariant (merge test was origin-relative).
- **MAX_MAP_SHADERS:** EA Q3map never de-duplicates BSP shader entries whose name (with
  `textures/`) is exactly 60 characters. Names are capped at 59. docs/toolchain.md.
- **`mohkit.staticlight`**: static models injected into the lit BSP with light-grid vertex
  colours (calibrated to MOHlight's means). Converted maps inject every prop
  (`props_mode="inject"`, no entity or MOHlight cost); stationary `prop_dynamic`/physics
  props count too. From-scratch maps: `build --inject-props` (opt-in).
- Converter features: ladders -> `func_ladder` (verified in game with the new
  `game.ladder_probe`), water, breakable glass -> `func_window`, `info_overlay` decals
  (incl. DecalModulate), doors -> `func_rotatingdoor` (mesh turned to the MDL hull), ropes
  -> ribbon patches, `env_sprite` -> autosprite glows, fog -> farplane, sky via VMTs,
  func_brush StartDisabled/Solidity/rendermode, alpha-weighted additive and unlit model
  materials, named cameras (`maps/<map>_cameras.txt`) in sheet pages of 9.
- Lighting: near-zero lights dropped and pairs merged (MOHlight's 60-lights-per-leaf cap
  had darkened Nuke's interiors), `-blocksize 512`, sky fill from Source's ambient,
  drafts at lightmap density 32, new `fastrad` preset (`-fast -bounce 2`).
- Pipeline: `csgo -q unlit` (minutes), `--resume`, `--lightmap-density`;
  `kill_stragglers` no longer kills other maps' tools (it had killed a dust2 light stage).
- Later fixes: Pillow's premultiplied RGBA resize had darkened masked textures (decals
  black); converted lights reach 1.5x Source brightness; ladders: hanging ones extended to
  the floor in front, prop collision cleared from ladder volumes and mount boxes, origin
  slid along the width to a clear mount box; OnBreak props and every func_breakable ->
  `func_window`; `--refresh-assets`; `--texlights` (opt-in).
- **Spot lights:** `light_spot` now points along VRAD's direction (z = +sin(pitch)); every
  earlier conversion lit ceilings with its downward spots.
- Findings: claim 8 false for dust2 (structural compiles, 61 KB VIS); MT MOHlight lit
  mk_medina without static models cleanly (static models likely cause the crash).
- Traps: a scratchpad script named `bisect.py` shadowed the stdlib module (PIL imports it).

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

1. **CS:GO look, next lever: texlights.** `--texlights` (opt-in) adds one point light per
   `lights.rad` emitter face (surface lights were ~15 h of MOHlight on Nuke). Build
   `mohkit csgo de_nuke -q fastrad --texlights --name cs_nuket` (~70 min alone) and compare
   with `cs_nuke`: radio rooms, lobby, B site. If better, make it the default; Mirage has no texlights.
   Other Nuke gaps: vents break like glass; door handles lost; detail grass dropped.
2. **Structural CS:GO maps:** `--structural` dust2 compiles (61 KB VIS, claim 8 false).
   Try a lit structural build: smaller leaves may light faster and avoid the 60-lights-
   per-leaf cap, and VIS would cull. If it holds up, make it the default.
3. **From-scratch `build --inject-props`** exists (opt-in; tried on a mk_medina copy,
   `dist/mk_medinai_shots.png`). Compare it side by side with a MOHlight-lit build at the
   same quality before making it the default.
4. **Multi-threaded MOHlight crash:** evidence now points at static models: mk_medina
   without its static props (`--inject-props`) lit on 10 threads cleanly (docs/toolchain.md).
   To confirm, re-run MT light on `roots/dm_mtx` (with statics) a few times and on
   `roots/dm_mtnostatic` (without) a few times. If confirmed, mk_medina could drop its
   forced `-threads 1` when built with `--inject-props`.
5. **mk_medina** re-shoot at high detail:
   `python -m mohkit test dist/mk_medina.pk3 dm/mk_medina --shots maps/mk_medina --bots 8 --seconds 60`;
   then `mk_village`, `mk_ref_room`, and correct `docs/lighting.md` claims made at low detail.
6. Tell the user: accept the Xcode license (`sudo xcodebuild -license`), and consider
   moving the repo out of iCloud (`~/Developer/moh-maps`).

## Decisions made while the user was away

- (fourth session) Converted lights: Source lights below brightness 20 are dropped and a
  light within 32 units of a brighter one is folded into it (de_nuke 473 -> 247). The
  dropped ones were nearly zero, and the 60-lights-per-leaf cap made them cost real light.
- (fourth session) Converted maps compile with `-blocksize 512`, drafts light at density 32,
  and the final Nuke/Mirage builds use the new `fastrad` preset (`-fast -bounce 2`):
  `preview` would not have finished tonight.
- (fourth session) The vent slats and breakable vent covers of de_nuke stay unconverted
  (vents open). Doors are real `func_rotatingdoor`s. Ladders: only ladders hanging 32+
  units above the floor in front are extended down (one in Nuke).
- (fourth session) `build --inject-props` for from-scratch maps is opt-in: its prop
  lighting has no per-vertex shadows, so it isn't the default until a sheet comparison.

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
8. VIS overflow without the shell: **tested, false for de_dust2** (61 KB of VIS data, 2026-10-01).
