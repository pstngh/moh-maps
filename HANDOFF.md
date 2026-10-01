# HANDOFF: current state and next steps (living file; keep it current)

## Session rules

The overnight run (2026-10-01, until 06:00 ET) is over, and its rules no longer apply.
CLAUDE.md's rules hold again, including **pause at 75% context**: finish the step,
update this file, commit and push, then stop and give the user the one-line handoff.

## Current session (2026-10-01 from 16:05): ladders, exposure fit, blend textures

Working from the "Next steps" below, in order (no new user request).
- **Ladders (done in code, verified on Vertigo):** rail-clip drop narrowed to *pairs* flanking a
  16-32 wide axis (`Converter._drop_ladder_rail_clips`, before `ladders()`); near-square volumes
  switch axis only for 1.5x wall; floors count displacements (`_displacement_heights`) and the
  column starts at the lowest floor within 32 of the highest; `hang` in report entries (floor
  in front > 40 below, prop clips count); `game.ladder_probe` starts hanging ones in the air
  with +forward held; `_probe_start` stands on low solids (pallets). Vertigo rebuilt 16:25:
  ladders **3/3** (128, 179, hatch ladder to the top), 37 bot kills. Nuke/Cache/Rats ladder
  records unchanged except Nuke 0 (z0 on the displacement, 263 tall) and Cache (160).
- **Cobble ladders 2/2** (16:50): the 460-unit one failed only because the probe teleported
  0.5 above a patch and fell through it; probe starts are now floor + 4 (commit f2ba8f6).
- **Exposure fit (done for 3):** `python -m mohkit csgo <map> --fit-exposure` ->
  `data/csgo_exposure.json` (committed; used by `lighting.transfer` before the controller
  rule). dust2 1.45 -> 2.53 (error 17.4 -> 5.6), mirage 1.02 -> ~1.08, inferno 1.06 -> 2.16.
  Still to fit: nuke, cache, vertigo, cbble (after their final rebuilds).
- **Blend textures (done, verified on Mirage, 00076bc):** error 6.0 -> 4.4, plaster/blue walls
  back (`local/csgo/compare/cs_mirage_blend.png`). Installed: mirage (blends + fit), dust2 (fit,
  no blends yet), cbble (blends). `--refresh-assets` refused dust2/inferno (.map changed since
  their builds): they need full builds.
- **3D skybox as a MOHAA portal sky (done, 457024b):** verified on a Vertigo test build
  (`local/csgo/compare/cs_vertigo_sky.png`: T spawn window, B2, stairs show the city like
  CS:GO). Also fixed: Master fog controller (Vertigo was fogged black), HDR sky fallback.
- **3D skybox rules (b857580):** the room is its own VIS region (structural brushes), objects
  nearer the eye than 8 x spawn spread / 16 are dropped, and a room losing > 3/4 falls back to
  the 2D sky. Net effect: only Vertigo keeps a portal sky (its city); the other maps' skyboxes
  are rooms around the map that one fixed eye can't show (AA has no sky parallax).
- **Final rebuild done (18:50), installed:** dust2 (73 kills, error vs CS:GO 17.4 -> 5.3),
  mirage (68, ladders 3/3, 6.0 -> 4.1), nuke (81, 6/6, 7 -> 5.3), inferno (26, 19.2 -> 6.0, corr
  0.75 -> 0.95), vertigo (48, **3/3**, 10 -> 10.6: its portal city is darker than CS:GO's hazy
  one), cbble (49, **2/2**, 10 -> 5.0), rats (18 kills, ladders 25/30 as before). Fitted
  exposures in `data/csgo_exposure.json` (uncommitted until the next commit).
- **User (chat ~18:50): stop working on rats for now. Some skies looked buggy ("a map in the
  sky") and some maps/backgrounds had new bugs in the screenshots.** Audit (sheet
  `local/csgo/compare/sky_audit.png`): the "map in the sky" was the intermediate 17:06 build
  (dust2/mirage installed ~40 min with the room sharing the map's VIS region); all maps but
  Vertigo now have the plain 2D sky. Real regressions found:
  1. **Cache**: its blends all use `$blendmodulatetexture`; linear blending turned ivy walls into
     bare grey panels. **Reinstalled the afternoon Cache** (`before/cs_cache_pre_final2`), then
     implemented threshold blends (alpha test, docs "materials" row). **Cache rebuilt and
     installed (18:58)**: ivy patches over panels and grass patches like CS:GO's 01_T (the mean
     greenness number favoured the all-ivy build, but the images match CS:GO better), 28 kills,
     ladder 1/1, error 9.6.
     **RUNNING (19:00), NOT installed (`NOINSTALL=1`):** dust2, inferno, cbble
     (`local/csgo/final3_a.log`) and mirage, nuke (`final3_b.log`) rebuilt with threshold
     blends. Next session: read the logs, compare each against the installed build
     (`python local/csgo/cmp3.py <name>` compares against `before/<name>_pre_final2`; also look
     at blended walls/ground), then `python -m mohkit install local/csgo/<name>/<name>.pk3`.
  2. **Vertigo portal sky**: above the city the sky is dark navy in some views (T spawn window,
     overview) where CS:GO is light blue; it was light blue in the test build before the sky
     room became structural (b857580). Inside the room (normal view) it looks right. Next:
     find why the room's 2D sky draws dark in the portal view (`tr_sky.c`
     RB_StageIteratorSky: boxSize = zFar / 1.75, `tr.farclip`), or give the room's sky walls
     the haze colour; also bake CS:GO's sky_camera fog (143 172 186) into the room.
  3. Cache's pk3 carries unused skybox prop models when the room is dropped (bloat only).

## Previous session (2026-10-01 from 13:20)

**User (chat 13:20):** P1 lighting of the six conversions ("doesn't feel cozy; some rooms
and textures extremely bright, other places too dark"): measure first, trace causes, fix
in mohkit, rebuild + reinstall all six, show before/after. P2: de_vertigo then de_cbble,
final quality like Inferno/Cache (unlit pass, full build, 8 bots, ladder probe, sheets,
install). Keep going until done; pause rule at 75%.

**P1 status: DONE (15:50).** All six conversions rebuilt with CS:GO's own baked lighting
(commits 1320404, 1e4df5d, f4df496) and installed in `~/Documents/Games/moh/main/`.
Per-camera error vs CS:GO's own shots (0-255) before -> after, corr: dust2 52 -> 17
(-0.36 -> 0.96), mirage 35 -> 6 (0.05 -> 0.97), nuke 38 -> 7 (-0.05 -> 0.95), inferno
31 -> 19 (0.12 -> 0.75), cache 34 -> 13 (-0.38 -> 0.84). Bots (8, 90 s): inferno 24, nuke 74,
dust2 83, mirage 76, cache 29, rats 16 kills. Ladders 35/40 (rats' known 5 fail).
Sheets sent to the user: `local/csgo/compare/<name>.png` (CS:GO | before | after).
Old pk3s/shots kept in `local/csgo/before/<name>/`. Builds: `local/csgo/all_final.sh`.
- Tools: `python -m mohkit exposure` (+ `--ref`), `python -m mohkit csgo-ref <map>`
  (CS:GO port, netcon; restores its config), `python -m mohkit csgo <map> --shoot`,
  `--resume --exposure X`. Method + numbers: docs/csgo-conversion.md "Lighting".
- Causes found (for the record): MOHlight falloff (7500*I*cos/d^2 in display space, cap
  127) vs VRAD's linear d^2; texlights; the texture-colour cap; props at 1.78x and CS:GO's
  per-prop tints ignored (thousands of props drawn white).

**P2 status:** both converted, final-built and installed (16:02); `map dm/cs_vertigo`, `map dm/cs_cbble`.
- **de_vertigo**: moved into +-8192 by (-512, 512, -6656) (`Options.offset`, auto), 52 bot
  kills, error vs CS:GO 10 (corr 0.88), 48 lightmap pages (per-face `surfaceDensity` from
  Source luxel size). Ladders **1/3**: CS:GO rails ladders with player clips 24 units apart
  (narrower than a player); those rails are now dropped (commit after f4df496), which fixed
  the first. **Open:** ladder 2 at (-1520, -302, 5027) (no `probe_start`, climbs 0) and
  ladder 3 at (-1216, 883, 5044) (falls 83): look at the step columns and clips there
  (`local/csgo/cs_vertigo/cs_vertigo.map`, report.json `convert.ladders`).
- **de_cbble**: 40 bot kills, error 10 (corr 0.99), 190 lightmap pages (fine: renderer limit
  256; 170 was MOHlight's). Ladders **1/2**: the 460-tall one at (-1120, 2461, 90) climbs 0.
- Scripts: `local/csgo/{vertigo,cbble}_final.sh`, `vc_redo.sh`. The other six maps were built
  before the rail-clip change (their ladders all pass), so they don't need a rebuild for it.

**Next steps (suggested):** (1) Vertigo's 2 and Cobble's 1 failing ladders; (2) maps
still read ~10-15% darker than CS:GO (dust2 96 vs 113, inferno 79 vs 95): try
`--resume --exposure` sweeps per map, or a rule nearer the top of the auto-exposure range;
(3) masked prop tints exact (tinted texture variants); (4) blend textures (Nuke's red radio
walls); (5) the 3D skybox (Vertigo's city below shows the sky-box floor).

## Current session (2026-10-01, from 11:25): de_inferno, de_cache, de_rats_1337_v2

**User (chat 11:25):** convert de_inferno, then de_cache, then workshop de_rats_1337_v2
(Steam Workshop 741136461), each to final quality with bots and ladders checked, and
install them in the MOH folder. **User (chat ~11:30): the rats copy in ~/Downloads is the
wrong version; get the workshop one.** Done: `local/workshop/de_rats_1337_v2.bsp`
(24 MB VBSP 21, from Valve's UGC CDN via the public GetPublishedFileDetails API; the
download was a zip, SHA-1 matched the CDN hash).

**Results (13:00, all installed in `~/Documents/Games/moh/main/`; play with `map dm/<name>`):**

| map | pk3 | build | bots (8, 90 s) | ladders | notes |
|---|---|---|---|---|---|
| de_inferno | `local/csgo/cs_inferno/cs_inferno.pk3` | fastrad, BSP 233 s, light 674 s | **19 kills** (big map, spread spawns) | none | props merged 6,326 -> 3,436 models / 253 SKDs; fountain statue + lily pads now visible |
| de_cache | `local/csgo/cs_cache/cs_cache.pk3` | fastrad, BSP 148 s, light 1,202 s | **31 kills** | **1/1** (164 of 162) | skybox leak fixed, B skylight additive |
| de_rats_1337_v2 | `local/csgo/cs_rats/cs_rats.pk3` (`--scale 1.1 --name cs_rats`) | fastrad, light 1,220 s | **13 counted** (19 kill lines, all 8 bots fight) | **25/30** climb, 16 to the top | fails: 25 (volume hangs 600 up), 14 (no model, start blocked), 6/9/15 stop ~53 up under overhangs |
| de_nuke | re-injected 12:28 (`--resume`) | (unchanged compile) | **88 kills** | **6/6** | props 4,801 -> 2,917 / 598 SKDs: the old install had lost hundreds of props (skel cache) |

Mirage (1,470 props, 279 SKDs) and Dust2 (1,574, 177) are within both budgets: unchanged.
Scripts: `local/csgo/{inferno,cache,rats}_final.sh`, `merge_redo.sh`; logs beside them.

**Possible next steps (not requested):** bot-usable ladders (bots climb only `func_ladder`
off-mesh links; step columns are too steep for the navmesh; rats is ladder-heavy, so a
`func_ladder` in front of each column could help bots); rats' 5 failing ladders; 2-layer
blend textures (Inferno plaster walls show the first layer only); CS:GO cameras that look
past the map edge (Inferno "Construct") show the sky box bottom where CS:GO has a 3D skybox.
Installed pk3s share `models/csgo/...` and `textures/csgo/m/...` names; scale is per
instance so rats' 1.1 does not leak into other maps.

**Engine limits found (docs/reference/engine.md §5.2, docs/csgo-conversion.md):** at most
4,095 static models (`staticModelNumIndexes[4095]`, 12-bit sort key) and 1,024 SKDs in the
skeleton cache (shared with players/weapons). `mohkit.staticmerge` keeps 3,500 / 600.

**Done this session (committed and pushed):** spawn nudging (`validate.fix_spawns`),
touching ladder pieces merged, skybox by leaf bounds (Cache leak), Z splits at 512,
see-through refract/water model materials (Inferno fountain), additive world materials,
`prop_hallucination` props (rats), auto cameras look down the longest sightline,
staticmerge + prune, ladder probe start (`probe_start`), adaptive step depth.

## Earlier summary (morning session 2026-10-01, from 08:00)

**Results (local only, `local/` is gitignored; install with
`python -m mohkit install local/csgo/cs_nuke/cs_nuke.pk3`, then `map dm/cs_nuke`):**

| map | pk3 | build | bots (8, 90 s) | ladders | notes |
|---|---|---|---|---|---|
| de_nuke | `local/csgo/cs_nuke/cs_nuke.pk3` (11:13, **final**: step ladders, texlights (43), displacement + spot fixes, lightmap-lit props, metal debris for 3 vents) | fastrad, BSP 274 s, light 3,172 s | **88 kills** | **6/6** step ladders (250/271, 94/101, 351/360, 125/131, 176/206, 286/290) | B site, Hell, radio rooms, lobby lit like CS:GO; a wall in `25_Lobby2` stays very dark (check) |
| de_mirage | `local/csgo/cs_mirage/cs_mirage.pk3` (10:17, **final**: step ladders, displacement + spot fixes, lightmap-lit props) | fastrad, BSP 344 s, light 2,169 s (shared CPU) | **66 kills** | **3/3** step ladders climb to the top | fog-coloured walls gone; shop shelves and litter lit (were black) |
| de_dust2 | `local/csgo/cs_dust2/cs_dust2.pk3` (09:12, props re-injected 09:45) | fastrad, BSP 714 s, light 2,692 s (shared CPU) | **88 kills** | — (no ladders) | final: spot + displacement fixes, lightmap-lit props (tunnel crates no longer black) |

Contact sheets: `local/csgo/<name>/<name>_shots*.png` (CS:GO's named spectator cameras).

**All three final builds are done** (11:13). Scripts: `local/csgo/{dust2_rebuild,mirage_rebuild,nuke_final}.sh` (build, 8 bots, ladder probe); logs beside them.

**Done this session (all committed and pushed):**
- Displacements whose face has `side` 1 were inside out (back-facing; Mirage's flat
  fog-coloured walls): `SourceBSP.displacement` uses the stored plane.
- **User (chat, 08:50): CS-style ladders you run up are fine.** Ladders are invisible clip
  step columns by default (`Options.ladder_style`); verified on an unlit Mirage (all 3
  climb; strafing off the scaffold ladders lands on their platforms). Square ladder
  volumes try both axes (Mirage's leaning ladder faced a far wall).
- Breakables get metal/wood debris (`debris_7/8.tik`), not glass.
- **Injected props are lit from the lightmaps** (`staticlight.LightmapField`): MOHlight's
  light grid ignores spotlight cones (test room), which blackened dust2's tunnel crates.
- **`build` injects static props by default** (A/B on mk_medina: same look, all shots
  within 1%); `--mohlight-props` opts out.
- **Texlights on by default** for conversions (Nuke compared on the same cameras).
- `game.ladder_probe` records the highest point; docs/lighting.md preview vs normal
  re-checked at high detail.

**Next steps:**
0. **User's next priority (chat, 2026-10-01 11:25): de_inferno, then de_cache, then the
   workshop map de_rats_1337_v2.** All three should get the full treatment Nuke/Mirage got
   (final `-q fastrad` build, sheets checked, 8 bots, `local/csgo/ladprobe.py`), then
   `python -m mohkit install local/csgo/<name>/<name>.pk3` so the user can play them.
   - `de_inferno.bsp` (93 MB) and `de_cache.bsp` (217 MB) are in `~/Documents/Games/csgo/csgo/maps/`
     with `_cameras.txt`. Start each with `python -m mohkit csgo de_inferno -q unlit` (minutes)
     to check geometry, ladders and props before the long lit build. Copy
     `local/csgo/nuke_final.sh` as the build+bots+ladders script. Cache is big (217 MB):
     watch BSP time, shader count (<1,500) and lightmap pages (<=170).
   - **de_rats_1337_v2** (Steam Workshop 741136461, by SkyDusH, 8.7 MB, CS:GO only,
     custom models by Tomobobo packed in the BSP): not on disk. Getting it needs the user:
     subscribe in Steam with CS:GO legacy (`csgo_legacy` beta) installed, or `steamcmd
     +login <user> +workshop_download_item 730 741136461`; ask before downloading from any
     third-party site. The converter takes a `.bsp` path (`mohkit csgo path/to/x.bsp`).
     Rats is a giant-scale kitchen: expect big props, `--scale` questions and custom
     materials in the pakfile.
   - Installed for the user to try (11:20): `cs_nuke`, `cs_mirage`, `cs_dust2` in
     `~/Documents/Games/moh/main/`. Re-run `mohkit install` after rebuilding any of them.
1. Done 11:13: final Mirage and Nuke builds checked (table above).
2. Checked 10:25: a third-person player under dust2's tunnel spot looks as lit as in the
   sun (run-time light-entity lighting), so the grid needs no rewrite.
3. The remaining older steps below (structural dust2, MT MOHlight crash, Xcode note).

Done in the overnight run (all committed and pushed; details in `docs/csgo-conversion.md`):
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

1. **Done (10:15): texlights are the conversion default** (Nuke compared on the same
   cameras). Other Nuke gaps: vents break (metal debris now) instead of opening; door
   handles lost; detail grass dropped; blend textures use the first layer only.
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
