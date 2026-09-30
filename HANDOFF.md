# HANDOFF: current state and next steps (living file; keep it current)

Read `CLAUDE.md` first. Git: GitHub `main` (https://github.com/pstngh/moh-maps).
The old pre-restart `.git` is backed up at `~/Library/Caches/mohkit/old-git-backup`
(the user may delete it).

**Goal (confirmed by the user):** (1) convert CS:GO maps to MOHAA; (2) create
any map from scratch, whether invented, described, or **recreated from a
screenshot the user sends**, bug-free and at stock quality. Both priorities are
equal. It works through verified knowledge + mohkit + the automated
compile → screenshot → bot-test loop. Conversions are personal-use only.

## Environment notes

- Python: `~/Documents/moh-toolchain/venv/bin/python` (Pillow, numpy, dulwich).
- **System `git` is blocked** by an unaccepted Xcode license (`sudo xcodebuild
  -license`; the user must do that). Use the dulwich helper:
  `~/Documents/moh-toolchain/venv/bin/python ~/Documents/moh-toolchain/gitc.py status|commit "msg" [paths…]|log|push main`.
  **Always pass paths to `commit`**: without them it stages everything,
  including a background agent's half-written files (that happened once:
  `maps/mk_medina` scaffold landed in commit ac8066e). Push needs
  `GH_TOKEN=$(gh auth token)`.
- EA tools: `.toolchain/MOHTools` (gitignored). CrossOver Wine, bottle "Steam".
  Game at `~/Documents/Games/moh`, CS:GO at `~/Documents/Games/csgo`,
  OpenMoHAA source at `~/Documents/moh-toolchain/openmohaa-src` (cite it).
- **`~/Documents` is iCloud-synced.** Build scratch lives in
  `~/Library/Caches/mohkit/build`.
- Wine buffers tool output: per-stage logs (`<build>/roots/<name>/*.log`) only
  fill when a stage ends, and Q3map's BSP log has no per-phase timings.
- No `timeout` binary on this Mac.

## Done this session (all committed and pushed)

- Village normal build: 31 kills/60 s with 8 bots; `-q preview` (2 bounces)
  looks the same as 8 bounces. Latest source (facade doors, fountain water,
  spawns out of props) is built and verified in `dist/mk_village_shots.png`.
- **Harness fixes** (`mohkit/game.py`, docs/testing.md):
  - bots join *after* the cameras (the spectator was following bots, so shots
    were third-person views of random bots);
  - load wait counts frames (bare `wait` = one Cbuf pass, two per frame),
    because `wait N` is consumed by one long loading frame;
  - `finishloadingscreen` after load: maps with their own loading menu (stock
    mohdm1) fake-pause the server until "continue" (`UI_EndLoad`), so `tele`
    was lost. Stock maps can now be shot from any spot.
  - `Shot.fov`, `game.fov_from_vertical`, `game.vertical_fov`, `game.compare`
    (reference | shot | blend), CLI `mohkit compare`, `mohkit test --shots maps/x`.
- `-q preview` quality (full VIS, MOHlight `-bounce 2`).
- **cs_dust2 failed to load in engine** (`LoadTGA: Only type 2…`): Q3map
  copies `qer_editorimage` into the BSP fence-mask field, and the engine reads
  it as a TGA by exact name; our shaders named `.jpg`. Fixed with
  `shaders.editor_image` (always `.tga`, like 205 retail shaders), a
  `bsp_checks` error, docs (materials.md, toolchain.md). Verified by patching
  the old BSP: dust2 loads and renders (draft light, shots looked right).
- `build_local` passes the runtime-prop precache list to the Project.

## Running now

1. `mohkit csgo de_dust2 --name cs_dust2 -q draft` **with props** (1509
   instances: 61 static / 69,989 verts, 600 script_model, 848 dropped).
   Log: `/private/tmp/claude-501/-Users-pstn-Documents-moh-maps/428d8928-2422-476b-8216-47fa81ef2aca/scratchpad/dust2_props.log`
   (session scratch; if gone, rerun). Expect ≈20 min BSP + ≈50+ min light.
   Output `local/csgo/cs_dust2/` (+ `cs_dust2_shots.png`).
2. A background agent is doing the zero-context one-shot test: builds
   `maps/mk_medina` from CLAUDE.md/docs only and reports doc gaps. It writes
   only under `maps/mk_medina/`.

## Next steps (in order)

1. When dust2 finishes: look at `local/csgo/cs_dust2/cs_dust2_shots.png`
   (props placed/oriented right? floating? missing textures?), run bots on it
   (`mohkit test local/csgo/cs_dust2/cs_dust2.pk3 dm/cs_dust2 --bots 8 --seconds 60`),
   update `docs/csgo-conversion.md` with measured results (remove "in
   progress" for props). Consider why BSP takes 20 min (experiment: `-notjunc`?
   fewer splits? `detail_all` vs structural) and why 848 props are dropped.
2. When the medina agent reports: fix every doc gap / toolkit bug it lists;
   judge its map; commit `maps/mk_medina` only if it's good (else delete it
   from the repo in a normal commit).
3. **Screenshot → map workflow**: write `docs/from-reference.md` (read the
   image; scale from known objects: door ≈ 112–128 u, player 94 u eye 82,
   storey 128–192, window ≈ 56×80; materials → stock look-alikes; block out
   with Carver, detail with kit/props; camera: eye height, fov via
   `fov_from_vertical`, `Shot.looking_at`; `mohkit compare`; iterate).
   Prove it: reference = stock mohdm1 camera `c8` = eye (-288, 1240, 130),
   yaw 0 (stone room: beamed ceiling, hanging bulb, door, barred window) —
   rebuild it from scratch as `maps/mk_ref_room`, compare side by side.
   Candidate sheet: `game.run([], "dm/mohdm1", shots)`.
4. Screenshots (small JPGs) in `docs/images/` for the README.
5. Tell the user: accept the Xcode license; consider moving the repo out of
   iCloud (`~/Developer/moh-maps`).

## Decisions made while the user was away

- Village: accepted as final at `normal` quality (no rebuild needed; the
  preview build contains the latest source and looks the same).
- Dust2 colour: left as is. Textures are the right sandstone colour; the grey
  look in draft shots is the cool fill light in shadow, not a converter bug.

## Unverified inherited claims (verify with a test, or delete)

The user trusts nothing from the previous (pre-mohkit) attempt. Verify each
with a small controlled compile or engine test (evidence into the doc), or
delete it:

1. `func_detail` brush entities are stripped by Q3map.
2. Lightmap page limit "180" (engine `MAX_MAP_LIGHTING 0x800000` / 49152 ≈ 170: test it).
3. Static-model limits: ~75k lit vertices per map (MOHlight crash), ≤ 24
   surfaces per TIKI, < 1000 verts / 2000 tris per SKD surface, zero-filled
   collapse arrays required.
4. `MAX_SURFACE_INFO` when compiling against a mod-heavy `main`.
5. "Multi-threaded MOHlight access-violated once" (toolchain.md, compile.py retry).
6. `-notjunc` as a `MAX_MAP_DRAWINDEXES` fallback.
7. Terrain mirroring "cell-owning controls + sentinel".
8. VIS overflow fixed by structural shell + detail (the 2 MB limit is verified).
