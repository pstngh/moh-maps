# Autonomous exact-hash evidence and improvement loop

Use this loop when the task requires unattended OpenMoHAA screenshots, runtime
and bot checks, evidence scoring, repeated map iteration, or improvement of this
skill. The loop may establish bounded technical and visual observations. It can
never approve or accept a map.

## Hard boundaries

- Keep the candidate map status unchanged unless the user separately changes
  the goal and the repository protocol permits that state edit.
- Never set `status: accepted`, `accepted_revision`, `accepted_baseline`, or
  `user_approval_evidence`. Only explicit user approval of the exact tested
  revision permits those changes.
- Treat lane scores as evidence completeness, not quality grades or acceptance
  probabilities.
- Do not let a generated report prove its own correctness. Correlate it with
  candidate bytes, isolated runtime bytes, logs, screenshots, source, and an
  independent inspection where practical.
- Preserve pre-existing dirty paths. Before and after each run, verify that only
  intended evidence and candidate paths changed.
- A map-edit loop requires a map-editing goal. During an audit, documentation,
  skill-only, or checkpoint-only task, do not modify map artifacts.

## Prepare one exact candidate

1. Record the candidate PK3 path and SHA-256 before launching anything.
2. Inspect every PK3 member. Require one expected BSP member at the exact
   case-sensitive path and record its inner SHA-256.
3. Correlate the compiled BSP, compile report, and packaged BSP by hash whenever
   those inputs exist. A same-named file is not correlation.
4. Use an isolated runtime containing exactly retail `Pak0.pk3` through
   `Pak6.pk3` plus the candidate. Permit only the narrowly recorded loose script
   used to drive fixed cameras; do not allow a loose BSP, shader, texture, or
   unrelated PK3.
5. Hash the candidate copy inside every visual and bot runtime after the run.
   A report that merely repeats the input hash is insufficient.
6. Record the OpenMoHAA executable hash, arguments, `fs_basepath`,
   `fs_homepath`, map/gametype, relevant cvars, elapsed time, and full log.

For repository-generated DM maps, prefer the proven launchers:

```powershell
powershell -NoProfile -File tools/run_generated_dm_visual_qa.ps1 `
  -GeneratedRoot generated/<map> -MapName <map>

powershell -NoProfile -File tools/run_generated_dm_bot_qa.ps1 `
  -GeneratedRoot generated/<map> -MapName <map> -MinimumCombatEvents 3
```

These launchers create isolated homes and fixed-camera or eight-bot reports.
They write QA reports under the generated map directory and use disposable
runtime roots under `C:\tmp\codex-*`; include those intended writes in the
scope check. Use a different harness only after verifying its commands against
the pinned OpenMoHAA source and recording why the repository launcher is
inapplicable.

Independently hash and scan the raw visual and bot logs. Do not trust summary
counts or empty diagnostic arrays when they contradict their source log. Record
every diagnostic as `blocking` or `proven_nonblocking` with its exact literal
text and supporting evidence. Leave unclassified diagnostics open; treat
unclassified script-load failures and invalid cvars as failures.

## Build the capture matrix

Copy `assets/evidence-loop.template.json` to an evidence workspace outside the
skill. Do not edit the template in place. Set the exact map name, expected BSP
member, fixed view IDs, and categories before capture.

At minimum, cover:

- player-height routes in both directions;
- a high-angle overview;
- boundaries and exposed edges;
- interiors, exteriors, and their transitions;
- long sightlines;
- every changed zone; and
- every exact user-reported failure viewpoint when one exists.

Use fixed origins and angles from the design report or a verified regression
manifest. Mark spectator-follow, bot-follow, or uncontrolled views as dynamic;
they may show activity but do not satisfy fixed-view coverage. Revalidate camera
origins after geometry changes. A camera in a wall, clip, floor, roof, void, or
unrepresentative location is a failed sample.

Before the first screenshot, dismiss team, weapon, model-selection, console, and
other modal UI through a verified command or input sequence and record it in
launch provenance. If modal UI obscures any requested view, fail that sample,
correct the capture harness, and rerun it; capture count cannot waive the defect.

After the launcher exits:

1. Require the requested view IDs and log markers in the same order.
2. Hash every screenshot and verify its recorded byte count and hash.
3. Reject missing or duplicate image content.
4. Inspect every full-resolution image yourself with the local image viewer.
5. Record each image hash, observations, and blocking defects in
   `visual_review`. Use `reviewer_kind: codex_visual` for autonomous inspection;
   never label it human review.
6. Re-run the audit after adding the review so the semantic lane is hash-linked.

Blocking visual defects include exposed void, floating or disconnected
geometry, missing or broken textures, z-fighting, failed cameras, ungrounded
props, unreadable lighting, concealed missing construction, bad scale, and any
user-reported regression. Capture count, file health, or an empty error log does
not establish visual coherence.

## Separate bot evidence lanes

The standard bot launcher can establish bounded evidence for BSP/Recast load,
eight bot entries, and a combat-event threshold. Do not infer movement, death,
respawn, route diversity, mapwide reachability, or enjoyable play from those
facts.

For lifecycle and route claims, add hash-linked observations to `bot_evidence`:

- Record positive observations for spawn, movement, combat, death, and respawn.
- For every required route, use instrumented position samples or a controlled
  route probe with at least two samples and one identified bot.
- Record the evidence source path, SHA-256, method, sample count, and unique bot
  count.
- Record a literal event or route sample string for every observation.
  Require the auditor to count that string in the hash-linked source.
- Do not use kill strings, bot entry messages, or Recast completion as route
  instrumentation.
- Inspect stalls, headroom, route width, collision, door behavior, spawn safety,
  and repeated use across meaningful routes.

Leave lifecycle or route gates `OPEN` when the current harness cannot observe
them. Do not weaken the gate to make a run pass.

## Audit and score

Run the deterministic skill script after visual and bot QA:

```powershell
python .agents/skills/mohaa-map-builder/scripts/evidence_loop.py audit `
  --candidate-pk3 generated/<map>/<map>.pk3 `
  --visual-report generated/<map>/<map>-visual-qa.json `
  --runtime-report generated/<map>/<map>-runtime-qa.json `
  --evidence-plan <evidence-workspace>/evidence-loop.json `
  --output <evidence-workspace>/audit.json
```

Use `--strict` in automated gates. Exit code `2` means at least one non-human
evidence gate is failed or open; exit code `1` means malformed/unreadable input.
The human-acceptance gate is intentionally always `OPEN` and is excluded from
strictness. The report always sets `promotion_allowed` to `false`.

Read lane scores separately:

- exact identity;
- source/design/compile/package hash provenance;
- runtime and bounded bot activity;
- exact OpenMoHAA launch provenance;
- independently classified raw runtime diagnostics;
- capture integrity and category coverage;
- semantic visual-review completeness; and
- lifecycle and route-evidence completeness.

Never average them into an overall map score. A high lane score only says the
specified evidence is present and internally correlated.

## Iterate from evidence

When the active goal permits map editing:

1. Select one cause-level defect or one representative structural zone.
2. Preserve the previous exact candidate and audit report.
3. Make the smallest reproducible source/generator change that tests the cause.
4. Compile, package, capture, inspect, bot-test, and audit the new exact hash.
5. Compare reports:

```powershell
python .agents/skills/mohaa-map-builder/scripts/evidence_loop.py compare `
  --before <previous-audit.json> --after <new-audit.json> `
  --output <comparison.json>
```

6. Keep `bounded_evidence_improvement` narrow. It means no scored lane or gate
   regressed within those manifests; it does not mean the map is better outside
   the inspected domains.
7. Revert or supersede a failed experiment through the repository’s normal,
   non-destructive workflow. Never discard unrelated user work.
8. Stop at the recorded stopping condition or at a human decision boundary.

## Improve this skill from repeated runs

Treat skill learning as a governed repository change, not memory accumulation.
After a run exposes a workflow weakness:

1. Classify it as map-specific, harness-specific, engine-specific, or reusable
   mapping knowledge.
2. Change the skill only when authoritative source proves the rule or the same
   bounded result repeats in controlled exact-hash runs. One generated failure
   may justify a regression test, but not a universal mapping rule.
3. Put concise routing in `SKILL.md`, detailed rules in `references/`, stable
   templates in `assets/`, and deterministic checks in `scripts/`.
4. Add or update a test that fails before the skill fix and passes after it.
5. Run the skill tests, state validator, Skill Creator `quick_validate.py`, and
   a clean-worktree diff check.
6. Forward-test with a fresh agent using a realistic prompt, the skill path, and
   raw evidence only. Do not tell the agent the expected diagnosis. The fresh
   agent must independently correlate hashes, inspect images when relevant,
   distinguish bot activity from route proof, and refuse acceptance.
7. Remove temporary forward-test artifacts, inspect the exact staged paths,
   commit, push, and verify synchronization.

No autonomous run, comparison, repeated success, skill edit, or fresh-agent
forward test can supply user approval or promote a map to accepted.
