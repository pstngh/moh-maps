# Session handoff (2026-09-30), delete once picked up

Git history was restarted from a single clean commit and force-pushed to
GitHub `main` (user-approved). The old local `.git` is backed up at
`~/Library/Caches/mohkit/old-git-backup`; the user may delete it. Read `CLAUDE.md` first.

User priorities: original maps and CS:GO conversions **equally**. Goal (agreed):
an AI or the user can reliably produce good, playable MOHAA/OpenMoHAA MP maps,
ideally in one shot, via verified knowledge + mohkit + the automated
compile → screenshot → bot-test loop. Conversions are personal-use only.

## Environment notes

- Python: `~/Documents/moh-toolchain/venv/bin/python` (Pillow, numpy, dulwich).
- **System `git` is blocked** by an unaccepted Xcode license (`sudo xcodebuild
  -license` would fix it; the user must do that). Use the dulwich helper:
  `~/Documents/moh-toolchain/venv/bin/python ~/Documents/moh-toolchain/gitc.py status|commit "msg"|log|push <branch>`.
  Push needs `GH_TOKEN` (e.g. `GH_TOKEN=$(gh auth token)`).
- EA tools: `.toolchain/MOHTools` (gitignored). CrossOver Wine, bottle "Steam".
  Game at `~/Documents/Games/moh`, CS:GO at `~/Documents/Games/csgo`.
- Git: dulwich only (see above). The repo was re-initialised; `origin` =
  https://github.com/pstngh/moh-maps.git.
- **`~/Documents` is iCloud-synced.** Build scratch lives in
  `~/Library/Caches/mohkit/build` (iCloud deleted files mid-compile when it was
  in the repo).
- Wine buffers tool output: the per-stage logs (`<build>/roots/<name>/*.log`)
  only fill when a stage ends.

## State at pause

Done and committed: the mohkit toolkit, the docs, the `reference/` corpus
move, `data/` catalogs, `maps/mk_village`, the CS:GO converter
(brushes/displacements/materials/sky/lights/spawns), the prop converter
(`mohkit/source/modelconv.py`, verified in engine by an agent), tests.

Committed with this handoff, **untested**:

- `Converter.props()` / `_prop_clips()` in `mohkit/source/convert.py`. Static
  props become `static_*` models up to 70k lit vertices (largest first); the
  next 600 become `script_model` (spawnflags 1 = not solid) with collision
  baked as world clip brushes; the rest are dropped.
- **TODO:** `build_local()` doesn't yet pass `res.report["precache"]` into the
  Project, so the `_precache.scr` misses `cache models/…` lines for the
  runtime props. Fix that, then run `python -m mohkit csgo de_dust2`.

Running when paused (independent OS processes; results land by themselves):

1. `mohkit build maps/mk_village -q normal --bots 8 --seconds 60`: log
   `/tmp/claude-501/village_normal.log`; output `dist/mk_village_shots.png`,
   `dist/mk_village_report.json`. Normal lighting is slow (>20 min, radiosity
   with 8 bounces). Consider `light_args=["-bounce","2"]` or similar for
   iteration and document the trade-off.
2. `mohkit csgo de_dust2 --name cs_dust2 -q draft` (without props): log
   `/tmp/claude-501/dust2.log`; output in `local/csgo/cs_dust2/`. The BSP stage
   takes 20+ min (≈36k detail faces in a caulk shell). If it's too slow, try
   `--structural`, or profile which faces cost.
3. Before/after: `python /tmp/claude-501/dust2_compare.py new|old` renders six
   named dust2 spots. A render of the previous dust2 attempt is at `/tmp/claude-501/dust2_old.png`.

## Next steps (in order)

1. Look at `dist/mk_village_shots.png` (normal build). Fix lighting (interiors
   dark? too bright?), check the bot kills in the report, and commit the final
   village. The source already includes edits made after that build started:
   facade doors, fountain water, spawns moved out of props. Rebuild.
2. Look at the cs_dust2 screenshots: texture alignment, displacement facing,
   sky orientation, light levels. Fix the converter, then wire props (see
   TODO) and rebuild with props. Update `docs/csgo-conversion.md` with
   measured results and remove "in progress" for props.
3. Rerun the zero-context "one-shot" test: a fresh agent builds
   `maps/mk_medina` (North African town, arcades, alleys, roof terrace, palms,
   terrain edges) using only CLAUDE.md/docs, then reports doc gaps. Fix the
   docs from its report. The previous attempt was stopped at the pause.
4. Put a couple of screenshots (small JPGs) in `docs/images/` for the README.
5. Push the branch and open a PR to `pstngh/moh-maps` (confirm with the user
   first).
6. Tell the user: accept the Xcode license (restores git/clang); consider
   moving the repo out of iCloud (`~/Developer/moh-maps`).

## Findings from this session (already in the docs)

- Cheats need `thereisnomonkey 1`.
- `wait N` is in ms.
- `saveshot` gives clean captures.
- More than 64 vertices per face → checker.
- Scale 1.0 is standard.
- Props get collision from companion `.map`.
- Patch visible side = cross(row step, col step).
- Terrain control SIZE field = texture repeat in units.
- MOHlight `-threads` helps.
- `func_detail` is stripped.
- `surfaceparm stone` is a no-op.

## Unverified inherited claims (verify with a test, or delete)

The user trusts nothing from the previous (pre-mohkit) attempt. These claims
came from its notes and have not been re-tested. Verify each with a small
controlled compile or engine test (evidence into the doc), or delete it:

1. `func_detail` brush entities are stripped by Q3map (map-format.md, entities.md, design.md, CLAUDE.md).
2. Lightmap page limit "180" (toolchain.md, design.md, lighting.md, CLAUDE.md, compile.bsp_checks).
   Engine `MAX_MAP_LIGHTING 0x800000` / 49152 bytes per page ≈ 170: test it.
3. Static-model limits: ~75k lit vertices per map (MOHlight crash), ≤ 24
   surfaces per TIKI, < 1000 verts / 2000 tris per SKD surface, zero-filled
   collapse arrays required (design.md, modelconv).
4. `MAX_SURFACE_INFO` when compiling against a mod-heavy `main` (toolchain.md).
5. "Multi-threaded MOHlight access-violated once" (toolchain.md, compile.py retry).
6. `-notjunc` as a `MAX_MAP_DRAWINDEXES` fallback (toolchain.md).
7. Terrain mirroring "cell-owning controls + sentinel" (map-format.md).
8. VIS overflow fixed by structural shell + detail (design.md, csgo-conversion.md).
   The 2 MB limit itself is verified in engine source.
