---
name: mohaa-map-builder
description: "Create, revise, convert, compile, package, and validate Medal of Honor: Allied Assault and OpenMoHAA maps; autonomously run exact-hash screenshot, runtime, bot, evidence-scoring, regression, and governed skill-improvement loops; investigate geometry, material, lighting, runtime, bot, packaging, and visual defects; process screenshot and playtest feedback; maintain repository mapping knowledge; and safely resume interrupted map work from repository checkpoints. Use for any MOHAA/OpenMoHAA map-production, map-quality, evidence-audit, or map-building skill-improvement task in this repository."
---

# MOHAA Map Builder

Make the repository, not chat history, the source of truth. Preserve user work,
inspect primary evidence before uncertain construction decisions, and keep
technical success separate from human acceptance.

## Resume before acting

1. Locate the Git root and read the applicable `AGENTS.md`.
2. Inspect status, branch, remotes, upstream, HEAD, and recent history.
3. Verify and fetch canonical `origin`; compare local and upstream commits.
4. Stop implementation if upstream is ahead/diverged or if Git and
   `PROJECT_STATE.json` disagree.
5. Preserve and report every dirty path.
6. Read `PROJECT.md`, `PROJECT_STATE.json`, and relevant decision, rejection,
   validation, map, and revision records.
7. Run `python .agents/skills/mohaa-map-builder/scripts/validate_state.py`.
8. Report the goal/version, active map/revision, accepted baseline, latest
   candidate, defects, exact next action, stopping condition, dirty paths, and
   synchronization state.
9. Continue only the recorded `next_action` unless the user changes it.

Read [resume-protocol.md](references/resume-protocol.md) for the complete Git,
reconciliation, checkpoint, commit, and push procedure.

## Select evidence before construction

When syntax, geometry, materials, entities, lighting, terrain, patches,
toolchain behavior, navigation, conversion, model origins, collision, scale, or
visual construction is uncertain, stop that decision and inspect authoritative
evidence. Prefer original MOHAA/source-map files, local retail assets, engine or
tool source, controlled compile/runtime behavior, and full-resolution in-game
screenshots. Record the question, exact sources, conclusion, confidence, label,
and remaining uncertainty.

For any runtime-behavior question, first read
[openmohaa-source-guide.md](references/openmohaa-source-guide.md), then inspect
the canonical OpenMoHAA source at its recorded commit. If the guide does not
settle the question, search the direct implementation, callers, declarations,
configuration, and compatibility branches. Record exact commit, paths, symbols,
line anchors, target variant, evidence label, and uncertainty. Distinguish AA,
Spearhead, Breakthrough, and OpenMoHAA behavior. Never use old Codex map
behavior or repository summaries as proof of engine behavior.

Pair important source conclusions with controlled runtime confirmation when
practical; if it is not practical, say so and keep unsupported parts `OPEN`.
OpenMoHAA source establishes runtime semantics only, not architecture,
geometry, visual fidelity, material or lighting quality, combat layout,
enjoyment, polish, or acceptance. Runtime success cannot override a visible
defect or human rejection.

Read [verification-protocol.md](references/verification-protocol.md) before
investigating defects, interpreting generated evidence, converting a reference,
or promoting mapping knowledge.

## Execute the recorded task

- For geometry, terrain, materials, lighting, screenshot feedback, or visual
  quality, read
  [geometry-and-visual-quality.md](references/geometry-and-visual-quality.md).
- For compilation, packaging, isolated runtime, bots, gameplay, doors, or human
  handoff, read
  [bot-and-runtime-validation.md](references/bot-and-runtime-validation.md).
- For elaborate maps, validate a representative structural zone before
  expanding. Avoid large whole-map transformations from unverified assumptions.
- Modify no map artifact during a documentation/checkpoint-only task.
- Preserve rejected and unknown outputs as evidence, but never use them as
  positive templates without re-verification.

Apply all relevant gates in repository `VALIDATION.md`. Do not describe a map as
complete, polished, release-ready, visually coherent, or accepted based only on
compilation, Recast, bot combat, automated screenshots, or absence of criticism.

## Run autonomous evidence and improvement loops

For unattended OpenMoHAA capture/runtime/bot QA, exact-hash evidence scoring,
comparison between iterations, or improvement of this skill, read
[autonomous-evidence-loop.md](references/autonomous-evidence-loop.md). Copy
[evidence-loop.template.json](assets/evidence-loop.template.json) to an external
evidence workspace and bind it to the exact candidate, fixed views, screenshot
hashes, visual observations, and instrumented bot evidence.

Use the repository's proven visual and bot launchers, then audit their raw
reports and isolated runtime copies with
`scripts/evidence_loop.py`. Inspect every queued screenshot at full resolution;
file health and capture count are not semantic inspection. Keep bot
entry/combat, lifecycle, route coverage, visual quality, and human acceptance as
separate gates. Never infer route coverage from Recast, kills, or bot entry.

The loop may make a focused map iteration only when the active user goal permits
map edits. It may propose a skill change only from authoritative evidence or a
repeated controlled result, and must add a regression test plus a fresh-agent
forward test. The loop and its scorer must always leave human acceptance open,
set no acceptance field, and never promote a candidate without explicit user
approval of that exact tested revision.

## Maintain state and knowledge

- Keep the stable mission in `PROJECT.md` and mutable work in
  `PROJECT_STATE.json`.
- Keep `accepted_baseline` separate from `latest_candidate`.
- Require explicit user approval of the tested revision before acceptance.
- Put verified normative rules in the playbook, chronological evidence in the
  research log, map-specific state in its README/revision report, decisions in
  `DECISIONS.md`, and user rejection/supersession in `REJECTIONS.md`.
- Treat existing repository knowledge as an index until each claim is audited
  against primary source, original data, or controlled runtime evidence.
- Leave inconclusive claims `OPEN`; never promote `OBSERVED` or `HYPOTHESIS`
  because a build compiled.

Update the checkpoint atomically with:

```powershell
python .agents/skills/mohaa-map-builder/scripts/checkpoint.py `
  --next-action "<one exact action>" `
  --stopping-condition "<one exact stop condition>"
```

The script never stages, commits, pushes, restores, deletes, or modifies
unrelated files.

## Stop only at a pushed checkpoint

Before a meaningful stop or risky operation, update state and verified
knowledge, validate, inspect the complete diff, stage explicit paths, inspect
the staged diff, commit, push, and verify local HEAD equals upstream. Report any
preserved dirty paths. If push verification fails, preserve the local commit and
report the incomplete checkpoint.
