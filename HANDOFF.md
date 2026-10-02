# HANDOFF: current state and next steps (living file; keep it current)

## Session rules

The overnight run (2026-10-01, until 06:00 ET) is over, and its rules no longer apply.
CLAUDE.md's rules hold again, including **pause at 75% context**: finish the step,
update this file, commit and push, then stop and give the user the one-line handoff.

## State (2026-10-02 16:45 ET)

- **Nothing is running.** Nothing was installed this session: `~/Documents/Games/moh/main/`
  still holds the 2026-10-01 builds of cs_dust2, cs_mirage, cs_nuke, cs_inferno, cs_cache,
  cs_cbble, cs_vertigo (shared prop paths, old LOD with shards, T/CT-copy spawns) and cs_rats
  (on hold). The user may play MOHAA on this Mac: ask before game runs (memory note).
- **Rebuilt, waiting for the user's install OK** (`local/csgo/<name>/<name>.pk3`; old local
  builds in `local/csgo/before/<name>_pre_repath/`): cs_cache, cs_dust2, cs_cbble, cs_mirage,
  cs_inferno, all full conversions with per-map prop paths (no clashes), the fixed LOD and
  FFA spawns from the nav mesh. Bots 27-32 kills (cbble 18), every ladder climbs.
  A/B against the installed builds (`mohkit ab`, 2 interleaved rounds; fps mean / worst):

  | map | harness settings | user's settings (r_lodscale 0.45, r_lodcap 0.35) |
  |---|---|---|
  | cs_cache | 296 / 241 -> 275 / 205 | 360 / 248 -> 326 / 242 |
  | cs_dust2 | 305 / 168 -> 277 / 165 | 372 / 225 -> 321 / 188 |
  | cs_cbble | 241 / 161 -> 180 / 112 | 229 / 149 -> 173 / 107 |
  | cs_mirage | 295 / 159 -> 269 / 145 | 345 / 184 -> 269 / 146 |
  | cs_inferno | 233 / 145 -> 189 / 116 | 210 / 134 -> 182 / 109 |

  (Absolute fps differ between runs; compare within a row.) Shots barely change, except
  inferno's APit, where the installed build draws a grey LOD shard band
  (`local/csgo/cs_inferno/ab/22_APit_ab.png`). Logs: `local/csgo/repath_all.log`,
  `local/csgo/after_queue.log`, `local/csgo/<name>_ab.log`, `<name>_ab_user.log`.
- **Lean de_nuke** (`local/csgo/cs_nukes/`, built as cs_nukes with `--props lean --structural
  -q fastrad`): 30 kills, 6/6 ladders, shots fine; vs s8 215 / 150 -> harness, 210 / 144 vs
  190 / 130 at the user's settings (+8-11%). s8 and s9 in `local/csgo/before/cs_nukes_s8|s9/`.

## NEXT (the user picks the order)

### A. Install the rebuilt conversions (user's decision)

Code fix done and verified in game (9c045d9; cs_cache with the 7 other installed pk3s:
18 of 19 cameras identical, the 19th = run noise). Options per map: install the rebuild
(`python -m mohkit install local/csgo/<name>/<name>.pk3`; `install` lists any clash left);
keep the installed build (it keeps clashing with the other old builds); rebuild with
`--props balanced` for fps (cbble lost the most: -25%); or write a pk3 path-rename tool for
the installed builds (clash fixed, look and fps unchanged, shards kept; ~1-2 h, not written).
Not rebuilt: cs_vertigo (loses no files), cs_nuke (see B), cs_rats (on hold). Once the other
maps are reinstalled, the old cs_nuke/cs_vertigo/cs_rats clash only among themselves.

### B. Lean rebuild of de_nuke (user, 2026-10-02), then de_mirage

Done for Nuke: `--props lean` (8686431: stock + wires dropped + fade cap >= 8 x prop size +
box-like props as VIS-culled brushes) with `--structural` (real VIS: 1,326 clusters, VIS 11 s).
Gain over s8 only +8-11% (csgo-conversion.md Nuke table): props as triangle soups can't keep
their light (engine.md 7.7), only ~9% of prop vertices are box-like, and the `_autocombine_`
clusters (37%) remain unculled static models. To install it as the map players know, rebuild
with `--name cs_nuke`. Open: whether to do Mirage the same way (expect a similar small gain),
and further levers: drop more autocombine clusters by kind (pipes, trusses), `prop_light`
as extra luxels for the brush proxies' light, and the 500-650 fps guess is out of reach.

### C. Local scripts that should be mohkit commands

Done 2026-10-02: `mohkit csgo <map> --final` (bots + ladder probe into report.json, never
installs), `mohkit ab <map> --a .. --b .. [--perf MS --rounds N --cvar k=v]` (same-camera
change + A | B images + interleaved fps; replaces `perf_nukes.sh` and the A/B part of
`cmp3.py`/`compare.py`). Left: the CS:GO | before | after sheet (`local/csgo/cmp3.py`),
`mohkit exposure --changed BEFORE AFTER [--ref]` and the README image builder
(`readme_img.py`); then point csgo-conversion.md at them.

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
