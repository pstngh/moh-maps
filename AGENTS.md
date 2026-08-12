# Agent bootloader

Continuity lives in three files:

- `.agent/GOAL.md` — stable goal, constraints, and non-goals.
- `.agent/STATE.md` — current handoff and exact next action.
- `.agent/DECISIONS.md` — non-obvious durable rationale.

## Resume

1. Read this file and `GOAL.md`.
2. Inspect Git status, branch, upstream, and recent commits; fetch before
   implementation when possible.
3. Read `STATE.md`, then relevant decisions and project evidence.
4. Inspect the files related to the active task.
5. Reconcile documentation with Git, code, and validation. Repository reality
   wins when they disagree.
6. Continue from the exact next action unless the user changes the task.

For map work, also read `docs/README.md`, `VALIDATION.md`, `REJECTIONS.md`, the
active map evidence, and the applicable repository-local skill.

## Handoff

Update continuity only at meaningful checkpoints or before leaving unfinished
work. Keep `GOAL.md` stable and `STATE.md` current rather than historical.
Record what is complete, remaining, blocked, assumed, and verified, then leave
one concrete next action. Preserve unrelated dirt and stage explicit paths only.

## Boundary

Continuity may read the repository but writes only `AGENTS.md` and `.agent/*.md`
plus minimal documentation routing during setup. It must not modify or
participate in source, tests, scripts, dependencies, build/CI, configuration,
infrastructure, generated code, deployment, or runtime behavior. Add no hooks,
automation, services, or executable helpers. Normal coding tasks may modify the
project when authorized; the continuity mechanism may not. Deleting continuity
must have zero project effect.

## Drift and concurrency

Before expanding scope, verify that work still serves the goal and constraints.
Flag adjacent work, contradicted assumptions, or reversed decisions instead of
rewriting history to make drift look intentional.

For concurrent sessions, prefer separate branches/worktrees, avoid sharing one
task silently, and reconcile `STATE.md` with Git before resuming. Do not build a
locking system.
