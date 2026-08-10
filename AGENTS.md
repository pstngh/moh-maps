# Repository instructions for MOHAA map work

This repository is the source of truth for durable Medal of Honor: Allied
Assault and OpenMoHAA map work. Chat history is not a checkpoint.

## Authority and safety

- Treat explicit current user requirements and approval or rejection as the
  highest authority.
- Treat every Codex-generated map, report, screenshot conclusion, and reusable
  claim as untrusted until its evidence is rechecked.
- Treat all existing repository knowledge as an untrusted index until each
  claim is individually audited and traced to engine/tool source, original
  data, or controlled runtime evidence.
- Preserve every pre-existing dirty path as user-owned. Never restore, delete,
  overwrite, stage, or reformat it merely to obtain a clean worktree.
- Never use `git reset`, `git clean`, automatic rebase, force-push, broad
  staging, or checkout/restore of user files.
- Stage explicit intentional paths only and inspect both the full diff and the
  staged diff before committing.
- Do not copy or redistribute proprietary Valve or retail AA content. Stock AA
  references are allowed when the player supplies retail data; new bundled art
  must be original or demonstrably redistributable.

## Mandatory startup and resume protocol

At the beginning of every map or mapping-knowledge task:

1. Locate the Git root.
2. Inspect status, branch, remotes, upstream, HEAD, and recent history.
3. Verify `origin` is `https://github.com/pstngh/moh-maps.git` or the equivalent
   SSH URL, then fetch it.
4. Compare local HEAD with the configured upstream. If upstream is ahead or the
   histories diverged, stop implementation and reconcile safely with the user.
5. Preserve and report all dirty paths.
6. Read `PROJECT.md` and `PROJECT_STATE.json`.
7. Run
   `python .agents/skills/mohaa-map-builder/scripts/validate_state.py`.
8. Read `DECISIONS.md`, `REJECTIONS.md`, and `VALIDATION.md` as relevant.
9. Read the active map README, relevant revision reports, and only the mapping
   references needed for the recorded task.
   For runtime behavior, read
   `.agents/skills/mohaa-map-builder/references/openmohaa-source-guide.md`.
10. Compare the checkpoint with the worktree and recent commits. If they
    disagree, stop map implementation and reconcile without discarding work.
11. Report the goal and version, active map/revision, accepted baseline, latest
    candidate, known defects, one authoritative next action, stopping
    condition, dirty paths, and local/upstream synchronization.
12. Continue only `PROJECT_STATE.json.next_action` unless the user explicitly
    changes the goal or task.

Use the repository-local `$mohaa-map-builder` skill for map creation,
revision, conversion, compilation, packaging, defect investigation, screenshot
feedback, mapping-knowledge maintenance, and interrupted-work resumption.

## Stable mission

Keep the stable charter in `PROJECT.md` separate from mutable work state. A
material mission change requires explicit user approval, a `goal_version`
increment, a decision entry, and coordinated updates to `PROJECT.md` and
`PROJECT_STATE.json`.

## Evidence and uncertainty

When uncertain about map syntax, brushes, textures, shaders, entities, doors,
lighting, terrain, patches, compilation, packaging, navigation, Source
conversion, model origins, collision, scale, or visible construction:

1. Stop assuming about that decision and state the uncertainty.
2. Inspect authoritative primary evidence: original map/shader/entity sources,
   local retail assets, OpenMoHAA or tool source, compiler logs/behavior,
   reference geometry, or full-resolution in-game screenshots.
3. When practical, pair one primary source with an independent verification.
4. Record the question, exact paths and relevant lines/entities/coordinates or
   images, conclusion, evidence label, confidence, and remaining uncertainty.
5. Leave inconclusive questions `OPEN` and ask the user instead of inventing
   geometry or behavior.

For runtime questions, begin with the pinned routing index in
`.agents/skills/mohaa-map-builder/references/openmohaa-source-guide.md`, then
read the actual canonical OpenMoHAA source at the recorded commit. If the guide
is insufficient, search callers, declarations, configuration, and
compatibility branches directly. Record exact commit, paths, symbols, line
anchors, target variant, and evidence label. Distinguish AA, Spearhead,
Breakthrough, and OpenMoHAA behavior. Old Codex map behavior, generated reports,
and repository summaries are not proof of engine behavior.

Pair important source conclusions with a controlled runtime check when
practical; otherwise state that runtime confirmation was not performed and
leave unsupported parts `OPEN`. OpenMoHAA source proves only implemented
runtime semantics. It does not prove architecture, geometry, visual fidelity,
material choice, lighting, combat layout, enjoyment, polish, or acceptance,
and runtime success cannot override human-visible defects or rejection.

Use `PROVEN`, `OBSERVED`, `HYPOTHESIS`, `OPEN`, `REJECTED`, and `SUPERSEDED` as
defined in the skill's `references/verification-protocol.md`. Compilation,
navigation, combat, or automated screenshots alone cannot prove visual
coherence, polish, gameplay quality, or acceptance. Human rejection overrides
an automated pass. Never use a rejected or unknown generated map as a positive
construction template without re-verification.

## Production and acceptance gates

Apply every relevant gate in `VALIDATION.md`. For elaborate maps, first measure
the source/reference, build and inspect one representative structural zone,
correct the process, and only then expand zone by zone. Do not perform a large
whole-map transformation from unverified assumptions.

Keep `accepted_baseline` separate from `latest_candidate`. Promote a candidate
only after explicit user approval of the tested revision. Silence, successful
compilation, bot movement, automated screenshots, absence of criticism, or
mildly positive feedback are not approval.

## Checkpoint, commit, and push protocol

Before every meaningful stop, candidate handoff, interruption point, or risky
long-running operation:

1. Save only intentional source, documentation, and evidence changes.
2. Update map status, defects, verified knowledge, decisions, and rejections.
3. Set exactly one precise `next_action` and one `stopping_condition` in
   `PROJECT_STATE.json`; use `checkpoint.py` for atomic state updates.
4. Run state validation and all task-relevant checks.
5. Inspect Git status and the complete diff.
6. Stage only explicit intentional paths and inspect the staged diff.
7. Commit the coherent checkpoint and push to the configured upstream.
8. Verify local HEAD equals the upstream commit and report remaining dirty
   paths.

A checkpoint is incomplete until its push is verified. If interrupted before a
commit, preserve the local diff for the next task to reconcile. Never claim
completion after an unverified or failed push.
