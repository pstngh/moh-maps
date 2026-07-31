# Session handoff — 2026-07-31 (transient; delete once absorbed)

Continuation notes from a remote Claude Code session on branch
`claude/nuke-update-regression-owwbxt`. Read `AGENTS.md` and the docs it
lists before acting; this file only adds session context that is not yet in
the permanent docs.

## The mission (user's own framing)

The user's end goal: AI one-shots complete MOHAA **multiplayer** maps from a
single prompt, with format knowledge good enough that nothing needs a second
attempt. This repository is the knowledge base being built toward that.
Standing policy (recorded in `AGENTS.md`): **multiplayer output only** — the
single-player sources in `aa/`, `bt/`, `sh/` are reference material, never
build targets.

## State of this branch (all pushed)

1. **Nuke revision 5 shipped, playtest verdict pending.**
   Revision 4's regression (fence/foliage/window surfaces showing garbage
   textures) was diagnosed from the user's 18 screenshots: 4,747 world draw
   surfaces shipped with `lightmapNum = -1`, an unsupported state that binds
   undefined texture memory. Fix: deterministic BSP edit
   (`generated/codex_nuke/tools/relight_nuke_unlit_surfaces.js`) appending a
   constant-white lightmap page (167 total) and pointing every unlit
   non-sky face at it. Shaders unchanged; byte-precise diff verified;
   inspector gained `--require-revision-5` (zero unlit non-sky faces).
   New PK3: 9,299,991 bytes, SHA-256
   `D95D477163C553B050408DA28F609D08720BDDF83B7FF44F2D5BFA320830A59F`.
   The user has this pk3. **Open gate: their in-game screenshot verdict.**
   If accepted, record acceptance (REVISION-5.md, map README, research log)
   and ask about merging this branch into `main`; the user conditionally
   approved merging ("if you're 100% sure").
2. **`docs/MAP-SOURCE-FORMAT.md`** — measured format reference for the
   retail corpora (109 files: 10 AA MP, 35 AA SP, 5 community, 24 BT MP,
   11 BT SP, 13 SH MP, 9 SH SP). Scope is retail/community sources only —
   the user explicitly did NOT want the generated codex maps analyzed or
   documented there. Confidence labels are explicit: counts/decodes are
   measured; `terrainDef` header fields, `farplane_cull`/`bias` modes, and
   `map_time` remain observations pending engine tests.
3. **Merged `origin/main`** (SP source uploads + the user's
   `REVISION-4-PLAYTEST.md`). Moved four misplaced root files
   (`m6l1a/b/c.map`, `m6l2a.map`) into `aa/`.

## Agreed roadmap toward one-shot generation (user endorsed)

1. **Probe-map suite** — ~20 tiny maps isolating one construct each
   (terrainDef, farplane_cull values, lightmapdensity, surfaceColor,
   overbright...), compiled once, screenshotted, to convert every
   "observed" label into engine fact. Needs the retail MOHTools toolchain —
   the user compiles on a Windows machine (see conversion-report paths).
2. **Generic `.map` linter + budget estimator** — map-agnostic preflight
   (grammar, winding, convexity, shader-image resolution, sealed shell,
   spawn coverage) plus predictive budgets for the known ceilings
   (180 lightmap pages, 60 lights/leaf, draw indexes, portal data).
3. **Fast headless build loop** — MOHTools under Wine or equivalent, draft
   light passes, so an agent can iterate generate→compile→boot→screenshot
   internally.
4. **Prefab library** — parameterized, compile-proven assemblies mined from
   the retail corpus (door+origin+areaportal+trigger, stairs, clips,
   fixtures, hint/vis idioms).
5. **Layout gates** — route-graph/sightline/spawn-balance checks plus
   Recast/bot metrics as automated acceptance.

## The immediate task this handoff continues

**Community map calibration corpus.** The user has five "Volute" map packs
locally at `/Users/pstn/Documents/moh/main` (also at
`https://dl.volute.io/downloads/`, which the remote environment's network
policy blocked — a local session can reach both). Agreed approach:

- Use **pk3s/BSPs, not decompiled `.map` files** — decompiles teach
  non-authored idioms and must never enter the reference corpus (quarantine
  if kept at all). Full pk3s are preferred over bare BSPs because they also
  carry authored shader scripts and `.scr` files. Author-released `.map`
  sources, if any exist, are the most valuable and belong in `aa_custom/`.
- **Never commit the pk3s/BSPs** (size + redistribution). Scan locally and
  commit only derived measurements: suggested
  `docs/data/community-bsp-survey.json` plus a short summary doc indexed in
  `docs/README.md`.
- What to extract per BSP (generalize
  `generated/codex_nuke/tools/inspect_nuke_bsp.js`, which knows the BSP19
  lump layout): lightmap page count, draw-surface/brush/shader counts, VIS
  cluster count, entity-lump classname histogram and worldspawn keys,
  shader/material usage. Purpose: empirical budget distributions to
  calibrate roadmap item 2, plus entity-convention statistics.

## Requested experiment: from-scratch Nuke rebuild

The user asked for a clean-room rebuild of Nuke from the CS reference as a
one-shot benchmark. Rules of the experiment:

- Input: the user's local `de_nuke_d.vmf` (and CS files) — ask for the
  path; never commit them.
- Write a NEW generator from scratch (do not copy `generate_nuke.js`);
  reuse only the documented knowledge: `docs/MAP-SOURCE-FORMAT.md`, the
  playbook, and the research log's case law (winding, detail policy,
  displacement planarization, prop-evidence rules, lighting budgets,
  unlit-face relight, atlas repack).
- Output a complete MP package under a NEW map name (do not overwrite
  `codex_nuke`): .map, original textures, shaders, .scr files, validator.
- Compile/light/package on the user's Windows MOHTools setup, then bot QA
  per the playbook gates. Measure how far one generation attempt gets
  before human screenshots are needed — that gap is the roadmap metric.

## Cautions for the next session

- Follow `AGENTS.md` gates: no map change is "complete" without compile,
  isolated-PK3, and bot evidence — revision 5 was validated statically
  because the remote environment had no retail data; do not repeat that
  pattern locally if the toolchain is available.
- Keep reference VMFs, retail assets, and community pk3 payloads out of the
  repository.
- The generated codex maps stay documented under `generated/<map>/` only.
- Playbook now cross-references the rev-4 "unrelated image" observation to
  its rev-5 root cause; keep both entries intact.
