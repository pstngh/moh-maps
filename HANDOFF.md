# HANDOFF: current state and next steps (living file; keep it current)

## Session rules

The overnight run (2026-10-01, until 06:00 ET) is over, and its rules no longer apply.
CLAUDE.md's rules hold again, including **pause at 75% context**: finish the step,
update this file, commit and push, then stop and give the user the one-line handoff.

## State (2026-10-02 21:26 ET)

**Nothing is running; all pushed. The user is playing MOHAA on this Mac (asked at 21:25 ET):
no game-window steps (shots, bots, ladder probes, fps) until they say they're done.** Their
own openmohaa process (connected to their server) is theirs: leave it alone.

Session of 21:05-21:26 ET, queue C below (no Summit corrections from the user yet). Done:
C.1 `exposure --changed`, C.2 checks-only `--final`, C.3 `--keep-before`, C.4 `mohkit
propcost` (stock models now read from the retail paks; `lod.engine_table` builds LOD tables as
`GetLODFile` does), C.5 `--readme-image`, C.6 exposure in `report["final"]`, C.7 `kit.ladder`,
`kit.step_ladder`, `kit.breakable`, `mohkit build --ladders`, `tests/rooms/` (laddertest
probed in game: func_ladder 170, three step columns 162 each onto a 160 ledge). Also
`exposure.shot_files` skips the 390 iCloud conflict copies (`<name> 2.png`) in local/csgo shot
folders (left on disk; deleting them needs the user's OK). Earlier today: mk_summit built and
**installed locally** (not on the VPS); reusable helpers moved into `mohkit.kit` /
`mohkit.site`. Summit details: next section.

## mk_summit, Summit from CoD Black Ops (user, 2026-10-02 ~17:10 ET)

The user asked for a replica of Black Ops' Summit; modes DM + TDM (their pick). References
(9 images from the CoD wiki, downloaded with the user's OK; never commit them):
`local/summit_ref/` (minimap `Map_Summit_BO.png`, bird's-eye, loading screen, gameplay
shots). `maps/mk_summit/build.py` places everything in minimap pixels at 12 u/px;
`mohkit generate` draws `dist/mk_summit_underlay.png` (plan over the minimap). Logs:
`local/summit/build_*.log`.

Done (all pushed): footprint and buildings traced from the minimap; plateau on cliffs over
a valley at z -1536 (trigger_hurt per void column); control hall (galleries, stairs,
consoles, skylight, glazed high windows); radar dome, gondola + cables, antenna mast,
power line, fences, rooftop parapets/dishes/billboards, door frames and lamps; AA-only
props. Draft + 8 bots: 31 kills in 90 s. The user got the first draft sheet + underlay
(~17:35 ET) and was asked for corrections; no reply yet.

Since then: catwalk over the drop, glass skylights, hall office, distant peaks, cliff
boulders, coarse backdrop lightmaps. **Normal build done 19:25 ET** (light 1,549 s; 8 bots 43
kills in 120 s): `dist/mk_summit.pk3`, sheet `dist/mk_summit_shots.png` (sent to the user).
fps at the user's settings (`local/summit/perf_user_settings.log`): mean 4,043, worst 2,222
(~30k tris per view). **Installed locally 2026-10-02 19:28 ET (user's OK)**: `main/mk_summit.pk3`
(sha1 2e3e118bf03b, map + scripts only; clashes unchanged at the old 4). Not on the VPS (the
user said "locally"). Nothing is running.

Next, in order: (1) the user's corrections (then rebuild, compare sheets with the installed
build on the same cameras, reinstall on OK); (2) fidelity: more interior furniture, rock
dressing on the cliff faces; (3) the older queue below.
Done 2026-10-02 ~20:00 ET (user's rule, now in CLAUDE.md): every reusable helper of mk_summit,
mk_medina and mk_village moved into `mohkit.kit` / `mohkit.site` (docs/api.md tables); the maps
regenerate byte-identical (mk_summit: one gondola clip box 9 lower, a latent bug fixed);
`tests/test_maps_regenerate.py` guards it.
Interiors and floor levels are guesses (the references show little of them).

## State (2026-10-02 17:00 ET)

- **Nothing is running.** **Installed 2026-10-02 ~16:50 ET (user's OK), locally and on the
  user's VPS (details in the agent's memory note, not in this public repo):** the rebuilt
  cs_cache, cs_dust2, cs_cbble, cs_mirage, cs_inferno. The VPS server was restarted to load
  them (user OK'd the telemetry reset). Local clashes: 252 -> 4 (old cs_rats loses 4 files to old
  cs_vertigo). The replaced local builds are in `local/csgo/before/installed_2026-10-01/`.
  Still old in the local game folder: cs_nuke, cs_vertigo, cs_rats (on hold). The user may
  play MOHAA on this Mac: ask before game runs (memory note).
- **The rebuilds** (`local/csgo/<name>/<name>.pk3`; old local
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

### A. Prop clash: done

Fixed (9c045d9), verified in game, and the five affected maps reinstalled (above). Left, for
the user: cbble lost the most fps (-25%): a `--props balanced` rebuild could win it back;
cs_vertigo and cs_nuke still carry the old shared names (harmless once alone).

### B. Lean rebuild of de_nuke (user, 2026-10-02), then de_mirage

Done for Nuke: `--props lean` (8686431: stock + wires dropped + fade cap >= 8 x prop size +
box-like props as VIS-culled brushes) with `--structural` (real VIS: 1,326 clusters, VIS 11 s).
Gain over s8 only +8-11% (csgo-conversion.md Nuke table): props as triangle soups can't keep
their light (engine.md 7.7), only ~9% of prop vertices are box-like, and the `_autocombine_`
clusters (37%) remain unculled static models. To install it as the map players know, rebuild
with `--name cs_nuke`. Open: whether to do Mirage the same way (expect a similar small gain),
and further levers: drop more autocombine clusters by kind (pipes, trusses), `prop_light`
as extra luxels for the brush proxies' light, and the 500-650 fps guess is out of reach.

### C. Knowledge still outside mohkit (audit of local/ + harvest items, 2026-10-02 ~20:15 ET)

The user asked that everything learned live in the repo's build machinery. A read-only audit
of all 40 scripts in `local/` found 35 covered or one-off queues; fixed the same evening:
spawn-removal warning, validate checks (60-char shader names, `.shader` outside `scripts/`),
stale docs (csgo-conversion.md, testing.md), wait-loop stale-"done" trap. **Still open, in
order (all small unless noted):**

1-7: done 2026-10-02 21:05-21:26 ET (see State).
8. `ladder_probe`: optional exit check (strafe off the top onto the platform, like
   local/csgo/strafe_test.py).

Harvest items still open (checked against the code 2026-10-02):
- CS:GO named cameras at fov 80 vs CS:GO's references at 90: `fov=90` in
  `convert.named_cameras`, then re-shoot and re-fit exposures (changes every sheet).
- Carver / `MapBuilder.box` split only X/Y at 512; the converter also splits Z (a 672-tall
  strip had 65 vertices). Changes generated maps' bytes: `tests/test_maps_regenerate.py`
  will fail until the maps are regenerated, re-shot and committed.
- LOD self-check at build time: replay each SKD and drop its LOD when the drawn area passes
  1.02x the full area at any level (the `test_lod` criterion).
- Fade cap scaled with prop size: done for `--props lean` only (`fade_size=8.0`), not
  balanced/stock.
- mk_medina still forces `-threads 1` (`maps/mk_medina/build.py`); with props injected after
  lighting MOHlight no longer lights its static models (the suspected crash trigger): run MT
  light a few times; drop the override if it holds, record it in toolchain.md.
- Re-check `docs/lighting.md` and `docs/from-reference.md` claims and the `lookalike` weights
  judged on `r_picmip 2` sheets (marked UNVERIFIED in from-reference.md).
- When the 3D-skybox room falls back to the 2D sky, prune its props' models from the pk3.
- de_vertigo's portal sky is dark navy above the city (csgo-conversion.md Known gaps).
- Two `--resume` builds of de_cache differing only in SKDs had different light grids
  (573,827 vs 575,503 bytes) and 164 world vertex colours off by 1: find the nondeterminism.
- Offline check for runtime props lit from inside solid / with no sun (`BSP.trace` against
  brushes, `SOLID|FENCE`), as a compile warning.
- Persistent wineserver (`wineserver -p`) to save ~15 s a build (untested).
- Untested idea for the six lost 3D skyboxes: CS:GO cubemap shots as the 2D sky.
- User question left unanswered (2026-10-01 ~23:39 ET, "will mastering cs go maps ... help
  it one shot maps too?"): proposal was to measure converted maps' layout numbers into
  design.md targets, use converted areas as recreate-from-screenshot benchmarks scored by
  `mohkit compare`, and turn recurring structures into `kit` prefabs.
