# HANDOFF: current state and next steps (living file; keep it current)

## Session rules

The overnight run (2026-10-01, until 06:00 ET) is over, and its rules no longer apply.
CLAUDE.md's rules hold again, including **pause at 75% context**: finish the step,
update this file, commit and push, then stop and give the user the one-line handoff.

## State (2026-10-02 13:20 ET)

- **Nothing is running.** Installed in `~/Documents/Games/moh/main/`: cs_dust2, cs_mirage,
  cs_nuke, cs_inferno, cs_cache, cs_cbble, cs_vertigo (2026-10-01 builds: LOD + fades, fitted
  exposure, threshold blends; old LOD with shards/dark panels; old T/CT-copy DM spawns) and
  cs_rats (on hold, user 2026-10-01).
- **History harvest done (2026-10-02):** 11 transcripts, 95 HANDOFF.md versions and 166
  commits went through `mohkit.harvest` + one subagent each; the lessons are now in code
  (guards + tests in 2eb121e), docs (symptoms.md ~40 rows, testing.md, toolchain.md,
  csgo-conversion.md, engine.md, CLAUDE.md) and memory (11 new notes about the user). Old
  session notes were dropped from this file: they are in git (`3ea41e4:HANDOFF.md`) and the
  transcripts (copies in `~/Library/Caches/mohkit/transcripts-backup/`).

## NEXT (the user picks the order)

### A. Installed conversions override each other's prop files (found by the harvest)

`pak.path_clashes(~/Documents/Games/moh/main)`: 252 files sit at the same path in several
installed `cs_*.pk3` with different contents (154 `.lod`, 52 `.skd`, 17 collision `.map`,
14 `.jpg`, 7 `.skc`, 5 `.tik`, 3 `.tga`). The engine searches a folder's pk3s from the last
name down (`FS_AddGameDirectory`, checked), so every map uses one pk3's copy: cs_cache lost
all 208 of its shared files (another map's LOD tables and vanish distances, an SKD vertex
order its STATICMODELDATA colours weren't permuted for, other texture gains). Not yet seen in
game at first; **verified 2026-10-02 13:15 ET**: cs_cache shot with all eight installed pk3s vs
cs_cache.pk3 alone, same 17 cameras: both trucks' cabs mangled and flat-shaded, a rock a dark
blob (Ttruck 3% of the pixels changed, LongABoost 1.6%; sheets and script in
`local/csgo/compare/cache_clash/`). Cause: prop models and their textures use shared names (`modelconv.model_names` /
`texture_name` with `prefix="csgo"`), while their content is map-specific since LOD,
headroom gain and staticmerge. `mohkit install` now warns.
1. Done (above). Files lost per map: cs_cache 208, cs_dust2 67 (53 to cs_mirage), cs_cbble
   32, cs_mirage 26, cs_inferno 12, cs_rats 4; cs_nuke and cs_vertigo lose none
   (`pak.path_clashes` lists the winner of each file).
2. Fix: per-map prop asset paths (e.g. `models/csgo/<name>/...`, `textures/csgo/<name>_p/...`;
   watch the 63-character `MAX_QPATH`, the hash fallback in `model_names`, and collisions
   with the world's `textures/csgo/<name>/...`). Takes effect only on a full conversion
   (`--resume` reuses the converted assets): do it before the lean rebuilds, then rebuild and
   reinstall each map after the user's OK.

### B. "Lean" rebuild of de_nuke (user, chat 2026-10-02 ~12:40), then de_mirage

**User: "do the lean rebuild on nuke, but in a fresh session".** Agreed plan: keep CS:GO's
world brushes, textures and baked lighting (they carry most of the look); compile so walls
block visibility (real VIS); replace the ~2,500 props with a small set: big gameplay pieces
(containers, crates, silos, trucks) as simple textured brush boxes/cylinders that VIS can
cull, a few hundred decorative static models, clutter dropped. Expected 500-650 fps (rough
guess; stock maps 1,200-1,700 on the harness; the user's own cap is `com_maxfps 250`). Then
the same for Mirage (with FFA spawns, `Options.ffa_spawns`). User (2026-10-02 07:35): "for
now only do nuke and mirage".

Facts to start from:
- Nuke world alone (props off, current `detail_all` build without real VIS): ~770 fps
  (`perf_s1_split.json`); props are the rest. Best prop build so far: s8 200 / 150 fps,
  s9 (fades 768, no wires) 266 / 194 but the A silo vanished (fade cap applied to a landmark).
- Static models are never VIS-culled in OpenMoHAA; world surfaces are. **Idea to verify
  first (cheap):** inject props as world *triangle-soup* surfaces instead of static models
  (the renderer loads `MST_TRIANGLE_SOUP`, `renderergl1/tr_bsp.c:1634`): assign each to the
  leaves it touches (`leafsurfaces`), vertex colours from CS:GO's prop lighting, so VIS and
  per-surface culling apply and the look is kept. Check in the source how a vertex-lit soup
  surface is shaded (lightmap -1, rgbGen) and test on a small map before Nuke. If it works,
  it could replace most of the proxy-brush work.
- Real VIS: `--structural` keeps Source's structural brushes structural (dust2 compiled
  with 61 KB VIS on 2026-10-01; untested lit, untested on Nuke). Watch leaks, compile time,
  VIS overflow, and the 3D-skybox room rules.
- Measure with `mohkit csgo de_nuke --perf 2000 [--toggle r_drawstaticmodels=0]` interleaved
  against `local/csgo/before/cs_nukes_s8/cs_nukes.pk3`; `mohkit.propcost` for prop vertices.
  Also shoot once at the user's settings (`r_lodscale 0.45`, `r_lodcap 0.35`, memory
  user-game-config).
- Restore before a new `--resume` on cs_nukes: `local/csgo/cs_nukes/statics.json` and
  `prop_light.npz` hold the s9 hand edit; s8's copies are in `local/csgo/before/cs_nukes_s8/`.

Other open choices from 2026-10-02 (ask the user): (a) accept s8-level fps for the other maps;
(b) re-inject every installed conversion with the fixed LOD (`--resume`, ~15 min each, then
reinstall); (c) full rebuilds with FFA spawns (they need a full conversion; untested with
bots: check kills and spawn spread).

### C. Local scripts that should be mohkit commands

The conversion finish (`local/csgo/*_final.sh`: fastrad build, 8 bots, `ladprobe.py`,
`--fit-exposure`, install unless `NOINSTALL=1`), the before/after sheets (`cmp3.py`,
`compare.py`), interleaved timing (`perf_nukes.sh`) and README images (`readme_img.py`) exist
only in gitignored `local/csgo/`. Make them `mohkit csgo <map> --final` (never installs),
`mohkit perf-ab A.pk3 B.pk3 --rounds 2`, `mohkit exposure --changed BEFORE AFTER [--ref]`
and a README image builder; then point testing.md / csgo-conversion.md at them.

### Open items found by the harvest (not started; small unless noted)

- CS:GO named cameras are shot at fov 80, CS:GO's references at 90: pass `fov=90` in
  `convert.named_cameras`, then re-shoot and re-fit the exposures (changes every sheet).
- Converter: warn in the log when `validate.fix_spawns` removes spawns (de_rats lost 4 at
  scale 1; suggest `--scale 1.1`).
- Carver / `MapBuilder.box` split only X/Y at 512; the converter also splits Z (a 672-tall
  strip had 65 vertices). Changes generated maps' bytes: re-check mk_* after.
- `validate`: warn on 60-character shader names (only the converter caps them) and on
  `.shader` files outside `scripts/` in a project's assets.
- LOD self-check at build time: replay each SKD and drop its LOD when the drawn area passes
  1.02x the full area (the `test_lod` criterion) at any level.
- Fade cap scaled with prop size so landmarks stay (s9's A silo).
- `kit.step_ladder` for from-scratch maps (reuse `Converter._ladder_steps`); bots can't use
  step ladders (idea: a `func_ladder` link in front of each column; untested).
- mk_medina still forces `-threads 1` (`maps/mk_medina/build.py`); with props injected after
  lighting MOHlight no longer lights its static models (the suspected crash trigger): run MT
  light a few times; drop the override if it holds, record it in toolchain.md.
- Re-check `docs/lighting.md` and `docs/from-reference.md` claims and the `lookalike` weights
  that were judged on `r_picmip 2` sheets (marked UNVERIFIED in from-reference.md).
- When the 3D-skybox room falls back to the 2D sky, prune its props' models from the pk3.
- de_vertigo's portal sky is dark navy above the city (csgo-conversion.md Known gaps).
- Two `--resume` builds of de_cache differing only in SKDs had different light grids
  (573,827 vs 575,503 bytes) and 164 world vertex colours off by 1: find the
  nondeterminism (CLAUDE.md: deterministic outputs).
- Offline check for runtime props lit from inside solid / with no sun (`BSP.trace` against
  brushes, `SOLID|FENCE`), as a compile warning.
- Persistent wineserver (`wineserver -p`) to save ~15 s a build (untested).
- Untested idea for the six lost 3D skyboxes: CS:GO cubemap shots as the 2D sky.
- User question left unanswered (2026-10-01 ~23:39 ET, "will mastering cs go maps ... help
  it one shot maps too?"): proposal was to measure converted maps' layout numbers into
  design.md targets, use converted areas as recreate-from-screenshot benchmarks scored by
  `mohkit compare`, and turn recurring structures into `kit` prefabs.
- Tell the user once (never delivered): accepting the Xcode license (`sudo xcodebuild
  -license`) restores system git/clang; moving the repo out of iCloud-synced `~/Documents`
  (e.g. `~/Developer/moh-maps`) would avoid file-provider surprises.
