# Project decisions

## D-001 - Canonical repository and delivery path

- Date: 2026-08-09
- Status: PROVEN
- Decision: Use `https://github.com/pstngh/moh-maps` as the canonical
  repository, work on the current branch, and push coherent validated
  checkpoints directly to its configured upstream without force-pushing.
- Evidence: Current user requirement; verified `origin` configuration and Git
  synchronization during bootstrap.

## D-002 - Repository state outranks chat history

- Date: 2026-08-09
- Status: PROVEN
- Decision: Store the stable charter in `PROJECT.md` and the authoritative
  mutable checkpoint in `PROJECT_STATE.json`. Keep one exact authoritative next
  action and validate Git agreement before implementation.
- Reason: Future tasks must resume safely without conversation context.

## D-003 - Acceptance is a human decision

- Date: 2026-08-09
- Status: PROVEN
- Decision: Keep `accepted_baseline` separate from `latest_candidate`. Require
  explicit user approval of the tested revision before promotion.
- Reason: Compilation, Recast, combat logs, and automated cameras failed to
  detect serious visible defects in rejected maps.

## D-004 - Evidence-first construction

- Date: 2026-08-09
- Status: PROVEN
- Decision: Stop and inspect primary evidence whenever a material map decision
  is uncertain. Record uncertainty instead of filling gaps with invented
  geometry or behavior.
- Reason: Existing generated artifacts and documents include confident claims
  later contradicted by human evidence.

## D-005 - Canonical OpenMoHAA source for runtime semantics

- Date: 2026-08-09
- Status: PROVEN
- Decision: Use `https://github.com/openmoh/openmohaa` at an explicitly
  recorded commit as the primary technical reference for engine runtime
  behavior. Begin with the repository source guide, inspect direct source when
  needed, distinguish AA/SH/BT/OpenMoHAA variants, and seek controlled runtime
  confirmation for important conclusions when practical.
- Boundary: Engine source does not prove map architecture, geometry, visual
  fidelity, material or lighting quality, combat layout, enjoyment, polish, or
  acceptance. Existing repository knowledge remains an untrusted index until
  the individual claim is traced to primary evidence.
- Evidence: Canonical `main` fetched and inspected at
  `a2f340195975f4f042e28a60b62561dd9a0b2700`; exact implementation routes are
  recorded in the source guide.
