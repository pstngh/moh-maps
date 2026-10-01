# HANDOFF: current state and next steps (living file; keep it current)

## Summary (paused 2026-09-30 ~21:40 at the user's request)

All work is committed and pushed to `main`; nothing is running. This session:

- **Harness fixed** (`mohkit/game.py`): bots join after the cameras; the load
  wait counts frames; `finishloadingscreen` lets stock maps be shot from any
  spot. Shots used to be third-person bot views, or all the same spot on stock
  maps.
- **CS:GO conversions load in game again** (`.jpg` editor images were read as
  TGA fence masks). Prop shader scripts now go to `scripts/`. Displacement
  patches are simplified. Draft conversions compile props as runtime models.
  **cs_dust2 draft now builds in ~65 min instead of 3+ h, with props
  everywhere** (BSP 368 s instead of 1,213 s; light 55 min still slow).
- **Screenshot → map workflow** is done: `docs/from-reference.md`,
  `mohkit/camera.py`, `mohkit looks-like` / `swatches` / `compare --region`,
  and the proof map `maps/mk_ref_room`.
- **Zero-context test passed:** a fresh agent built `maps/mk_medina` (North
  African town, 24 bot kills/60 s) from the docs alone and reported doc gaps
  (listed below, not yet fixed).
- **Inherited claims checked:** 7 of 8 are now tested or verified (see the
  bottom). The checks also found the real lightmap limit (170), the shader
  headroom (~1,630), the BSP hotspots, slow single-threaded static-prop
  lighting, and the multi-threaded MOHlight crash.

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

1. **Fix the doc gaps and toolkit issues mk_medina's agent reported:**
   - CLAUDE.md says to validate `maps/<name>/<name>.map` before building, but
     that file only exists after `build`. Add a `mohkit generate maps/<name>`
     command (write and validate the `.map`), or fix the loop text.
   - Run the 64-vertex face check right after the BSP stage, and stop before
     VIS/light (it currently runs after lighting). Report face locations, not
     just shaders.
   - Passing a wall-band list to `b.box`/`b.hull` silently writes garbage into
     the `.map`. Raise a clear error.
   - Docs need a kit/build API overview: `facade`, `door`, `recess`, `strip`,
     `shutter`, `terrain`, `cv.solid`, band/side mapping, MatSpec keys.
   - Docs need a North African palette (`algiers/*`, mohdm7). Traps:
     `algiers/afrika_windecal` is a decal and needs a non-solid slab;
     `algiers/tentdsrt` renders black underneath, so use `algiers/desertcloth`.
   - The cause of >64-vertex faces: arch/detail pieces meeting a narrow
     ceiling strip add T-junction vertices. Stop them below the ceiling and
     close the gap with one lintel.
   - Draft `-fast` light still does radiosity. World size (sky height, hill
     ring) drives MOHlight time; static props light on one thread.
   - Terrain hill rings: a Euclidean falloff breaks the 510-unit patch limit at
     the corners; a p=4 norm works.
   - design.md: "2–4 min to run across" is impossible within ±8192 (~60 s at
     275 u/s).
   - `validate` uses a prop's full bounds for spawn clearance (palm canopies
     block spawns).
   - `mohkit test --shots <other>` overwrites `dist/<name>_shots.png`.
   - Check that `Shot.fov` takes effect in game; the agent saw no change with
     fov 30.
2. **cs_dust2** (`local/csgo/cs_dust2/cs_dust2_shots.png`, latest draft build):
   - Some converted props render **solid black** (rubble/debris in shots 01 and
     04); some crates look washed out. Check their shaders and models.
   - Run bots: `python -m mohkit test local/csgo/cs_dust2/cs_dust2.pk3 dm/cs_dust2 --bots 8 --seconds 60`.
   - Profile the 55-min light (`Stage.slowest`, `-v`).
   - 848 of 1,509 props are dropped. Engine entity limit: 600 runtime +
     others ≤ 1024.
   - Update the measured results in `docs/csgo-conversion.md`.
3. **mk_medina polish:** the narrow streets are too dark, and walls are plain
   and boxy. It has 28 DM spawns where the spec was 16–24, and it lights with
   `-threads 1` (multi-threaded MOHlight crashed at 00433F3A).
4. **Claim 8** (VIS overflow without the structural shell): test with
   `mohkit csgo de_dust2 --structural` when the machine is free (long).
5. Tell the user: accept the Xcode license, and consider moving the repo out
   of iCloud (`~/Developer/moh-maps`).

## Decisions made while the user was away

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
