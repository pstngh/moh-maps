# State

Updated: 2026-08-12

## Active task and status

The raw-runtime-diagnostics replay hardening for the repository-local
`mohaa-map-builder` verifier is **paused in progress** until the user resumes
development. It serves the goal by preventing stale or coordinated diagnostic
claims from overstating exact-hash runtime evidence.

## Completed

- Skill checkpoints through `f472664` were committed, pushed, and synchronized.
- Three preserved local files contain the proposed replay, its rule, and its
  regression test.
- Before the pause, the full skill suite passed 43/43 tests, including rejection
  of a checksum-valid `proven_nonblocking` → `blocking` rewrite.
- The lightweight continuity migration is documentation-only; development dirt
  was not changed.

## Remaining

1. Reconcile and rerun the 43-test suite after development resumes.
2. Materialize the real `codex_cache` bundle twice and prove determinism.
3. Verify a checksum-valid real-bundle disposition attack is rejected by the
   replayed gate, normalized raw-log summary, and score.
4. Obtain a zero-context audit of hashes, roles, scorer, logs, PK3/BSP identity,
   and the no-promotion boundary.
5. Stage only intentional skill paths, update this state, commit, push, fetch,
   and verify synchronization.

## Blockers and unknowns

- Development has not been explicitly resumed after continuity setup.
- `codex_cache` revision 1 has four blocking visual findings, no raw compile log,
  and no human acceptance.
- Legacy read-only skill helpers still reference the removed JSON checkpoint;
  reconciling project tooling is a separate authorized task.

## Assumed, not verified now

- The three-file diff is still one coherent checkpoint.
- The earlier 43-test result and retained real evidence will reproduce.

## Verified at setup

- Preserved modified paths:
  - `.agents/skills/mohaa-map-builder/references/autonomous-evidence-loop.md`
  - `.agents/skills/mohaa-map-builder/scripts/evidence_loop.py`
  - `.agents/skills/mohaa-map-builder/tests/test_evidence_loop.py`
- Their respective SHA-256 fingerprints are `3C6C88EB…B129300`,
  `8278F616…A037DF`, and `6B4F11B3…E4D54DA`.
- Preserved deleted PK3s: `codex_cobblestone`,
  `codex_obj_team2_expanded`, and `codex_reactor`.
- Active evidence candidate: `codex_cache` revision 1, PK3
  `90477F68…84C53`, containing sole BSP `maps/dm/codex_cache.bsp`
  (`653AEF5E…EE94C`). Latest candidate is `codex_dust2_v2`; accepted baseline is
  empty.

Relevant evidence: `generated/codex_cache/evidence/revision-1-exact-hash-20260810/`,
`VALIDATION.md`, and `REJECTIONS.md`.

## Exact next action

After the user resumes development, inspect the exact three-file skill diff
against HEAD, confirm its fingerprints and scope, then rerun the full 43-test
suite with Python bytecode disabled. Do not stage or modify the three deleted
PK3 paths.
