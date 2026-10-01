# HANDOFF: current state and next steps (living file; keep it current)

## Summary (paused 2026-09-30 ~22:25 at the user's request, second session)

All work is committed and pushed to `main`. **Two builds are still running**
(detached with nohup; they survive the session):

| build | log | results land in |
|---|---|---|
| cs_dust2 draft (`mohkit csgo de_dust2 -q draft`), light started 22:07 | `/private/tmp/claude-501/-Users-pstn-Documents-moh-maps/5245b254-4e68-40bc-9e0d-7ad12bb4c67d/scratchpad/dust2_draft.log` | `local/csgo/cs_dust2/cs_dust2_shots.png`, `report.json` |
| mk_medina preview + 8 bots 60 s (`mohkit build maps/mk_medina -q preview --bots 8 --seconds 60`), light started 22:06 | `…/scratchpad/medina_preview.log` (same folder) | `dist/mk_medina_shots.png`, `dist/mk_medina_report.json` (kills) |

Each light took ~55 min last time, so both should finish ~23:00–23:20. Check with
`ps aux | grep -E "[Q]3map|[M]OHlight|[o]penmohaa"` and the result files'
timestamps. Both passed the new post-BSP 64-vertex check (they reached VIS/light).

This session (second):

- **HANDOFF step 1 done** (mk_medina's doc gaps): `mohkit generate`; 64-vertex
  check right after BSP with face locations, stopping before VIS/light; band
  lists on brushes raise `TypeError`; spawn validation uses only player-blocking
  collision brushes (palm canopies are foliageclip); `Shot.fov` now works
  (`cg_fov`, engine clamps 65–120; narrower = centre crop); `test --shots
  <other>` no longer overwrites the map's sheet; draft light is `-fast -bounce 0`
  (`-fast` alone still ran radiosity, measured). New `docs/api.md`, North African
  palette, 64-vertex faces, hill rings, light-time breakdown.
- **cs_dust2 black rubble: cause found, fix unverified.** Runtime `script_model`s
  are lit from their origin (NOT_SOLID packs no box: `cg_modelanim.c:1064`,
  `sv_world.c:230`); the rubble's Source pivot is on the floor, so the sun trace
  starts in solid. `modelconv.convert_model(centre=True)` now moves each converted
  model's pivot to its bounds centre (mesh and collision), and the converter
  offsets entity origins (`Converter._prop_origin`). The running dust2 build tests it.
  Documented in `docs/reference/engine.md` §5.2 (says "renders black": confirm).
- **mk_medina polish, unverified in game:** `wall_trim` (ornamental
  `algiers/algiertrim` cornice under the roof edge, beam-end rows, string course
  at z 256), `balcony` (wooden mashrabiya boxes replacing ~30% of upper windows;
  upper windows moved to z+280 on tall walls), `sundiffuse 1.6`,
  `ambientlight 20 18 16`, alley lanterns 190, and 24 DM spawns (4 team-only).
  `mohkit generate` validates it with 0 errors.

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

1. **Done 2026-09-30 (second session):** mk_medina's doc gaps and toolkit issues.
   `mohkit generate`; the 64-vertex check runs after BSP and stops the compile with
   face locations; band lists on brushes raise; prop collision uses the
   player-blocking brushes (palm canopies no longer block spawns); `Shot.fov` works
   (`cg_fov`, 65–120, crop below); `test --shots` keeps the map's sheet; draft light
   is `-fast -bounce 0` (`-fast` alone ran radiosity). Docs: `docs/api.md`, North
   African palette, 64-vertex faces, hill rings, light-time breakdown.
2. **Check the two running builds** (table above):
   - cs_dust2: is the rubble in shots 01/04 lit now? Are props still in the right
     places (re-centring moves origins: compare with the old sheet)? If good,
     remove "(says renders black: confirm)" from this file, update
     `docs/csgo-conversion.md` (its "Known gaps" still says props are pending the
     model converter; add the pivot note, the measured times from the build summary,
     and the props report: instances/runtime/dropped), and commit.
   - Then dust2 bots: `python -m mohkit test local/csgo/cs_dust2/cs_dust2.pk3 dm/cs_dust2 --bots 8 --seconds 60`.
   - Dust2 still drops ~848 of 1,509 props in draft (runtime cap 600; engine
     entity limit 1024 total). Some crates looked washed out (shot 00): check.
   - mk_medina: look at `dist/mk_medina_shots.png` (alleys 05–07 brighter? cornices,
     balconies, beam ends look right, nothing floating or z-fighting?) and the bot
     kills in the build log/report. Fix, rebuild, commit. Light stays `-threads 1`
     (MT MOHlight crashed at 00433F3A).
3. **Medina is otherwise done** once the above looks right; update its README if
   anything changes.
4. **Claim 8** (VIS overflow without the structural shell): test with
   `mohkit csgo de_dust2 --structural` when the machine is free (long).
5. Tell the user: accept the Xcode license, and consider moving the repo out
   of iCloud (`~/Developer/moh-maps`).

## Decisions made while the user was away

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
