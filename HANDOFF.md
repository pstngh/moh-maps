# HANDOFF: current state and next steps (living file; keep it current)

## Session rules

The overnight run (2026-10-01, until 06:00 ET) is over, and its rules no longer apply.
CLAUDE.md's rules hold again, including **pause at 75% context**: finish the step,
update this file, commit and push, then stop and give the user the one-line handoff.

## Summary (overnight run 2026-10-01, fourth session; ended 06:00 ET)

**Results (local only, `local/` is gitignored; install with
`python -m mohkit install local/csgo/cs_nuke/cs_nuke.pk3`, then `map dm/cs_nuke`):**

| map | pk3 | build | bots (8, 90 s) | ladders | notes |
|---|---|---|---|---|---|
| de_nuke | `local/csgo/cs_nuke/cs_nuke.pk3` (05:29, spot fix) | fastrad, BSP 200 s, light 2,389 s | **70 kills**, none stuck | **6/6** (A-site one: +use from the ledge) | 4,801 props, 718 overlays, 6 doors, 3 breakable vents, 38 glass windows, 70 ropes, 78 glows, water; interiors now lit |
| de_mirage | `local/csgo/cs_mirage/cs_mirage.pk3` (06:02, spot fix) | fastrad, BSP 242 s, light 1,259 s | **75 kills** | 2/3 (leaning ladder at (444 652 -182): falls off the top) | 1,470 props, 512 overlays, 85 ropes, 35 glows, 3 breakable covers/shutter + 3 windows; shops and palace now lit |
| de_dust2 | `local/csgo/cs_dust2/cs_dust2.pk3` (09:12, spot + displacement fixes) | fastrad, BSP 714 s, light 2,692 s (3 builds sharing the CPU) | **88 kills** | — (no ladders) | 1,574 props, 459 overlays; tunnels now lit; props re-injected (`--resume`, 09:45) with lightmap-based colours: the black tunnel crates are fixed |

Contact sheets: `local/csgo/<name>/<name>_shots*.png` (CS:GO's named spectator cameras).

**Morning session (2026-10-01, 08:00):** the Mirage spot-fix rebuild finished at 06:05
(75 kills; shops and palace lit). Its sheets showed flat `farplane_color` walls:
displacements whose face has `side` 1 were turned inside out (back-facing patches; dust2
176, Mirage 143, Nuke 77). Fixed in `SourceBSP.displacement` (docs/csgo-conversion.md).
**User (chat, 08:50): CS-style ladders you run up are fine** (MOHAA ladders fight CS
layouts). Done: `Options.ladder_style="steps"` (default): invisible clip step columns;
Mirage's leaning ladder now faces its ledge (square volume, both axes tried); breakable
vents/covers get metal or wood debris (`debris_7/8.tik`); `game.ladder_probe` records
the highest point; `game.ladders_for_probe` includes step ladders from report.json.
Step ladders verified on an unlit Mirage (`local/csgo/cs_miragel`, 09:20): all 3 climb
to the top (147/148, 143/160 (one step short under the scaffold's upper floor, above its
platform), 139/146 onto the ledge). dust2 rebuild done 09:12 (row above).
**Still running (started 08:20):** `local/csgo/mirage_rebuild.sh` and
`local/csgo/nuket_build.sh`. Both were converted before the step ladders, so Mirage needs
one more build; cs_nuket is only the texlights comparison. Logs
`local/csgo/{mirage_rebuild,nuket_build}.log` end with "done".

**Exact next steps (09:30; shell commands were blocked by a failing permission check):**
1. Commit `HANDOFF.md` (only uncommitted file).
2. `python local/csgo/strafe_test.py`: check that strafing off the top of Mirage's scaffold
   ladders lands on the platforms (expected; hole ladders can't be left backward).
3. When `mirage_rebuild.log` says done: check its sheets for the fog-coloured walls (should
   be gone), then rebuild Mirage with step ladders: `local/csgo/mirage_rebuild.sh`
   (build, 8 bots, `local/csgo/ladprobe.py`).
4. Done 09:45: injected props are lit from the lightmaps (`staticlight.LightmapField`);
   MOHlight's light grid ignores spotlight cones (docs/csgo-conversion.md). Open question:
   players are still lit from that grid, so under CS:GO spots they may look dark. A fix
   would rewrite the grid lump from the lightmap field (palette + RLE re-encode).
5. When `nuket_build.log` says done: compare `cs_nuket` with `cs_nuke` (old shots backed
   up in the scratchpad `nuke_0529/`; else re-shoot `cs_nuke.pk3`): radio rooms, lobby, B
   site. Then the final Nuke build with step ladders (+ `--texlights` if better).

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
3. **Done (09:55): prop injection is the `build` default** (`--mohlight-props` opts out).
   A/B on mk_medina's own lit BSP (props stripped and re-injected from the lightmaps): mean
   brightness within 1% on all 20 shots, props look the same (docs/entities.md).
4. **Multi-threaded MOHlight crash:** evidence now points at static models: mk_medina
   without its static props (`--inject-props`) lit on 10 threads cleanly (docs/toolchain.md).
   To confirm, re-run MT light on `roots/dm_mtx` (with statics) a few times and on
   `roots/dm_mtnostatic` (without) a few times. If confirmed, mk_medina could drop its
   forced `-threads 1` when built with `--inject-props`.
5. **mk_medina re-shot at high detail (05:35):** `dist/mk_medina_shots.png`, 20 shots,
   **19 bot kills** in 60 s; alleys, arcades, cornices, café and props read well (its props
   are MOHlight-lit; compare with the injected copy `dist/mk_medinai_shots.png`: nearly the
   same, MOHlight's props show a little more self-shading). `mk_village` and
   `mk_ref_room` were re-shot too (sharp textures, props lit; `dist/*_shots.png`). Still to
   do: re-check the `docs/lighting.md` claims that were made from low-detail sheets.
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
