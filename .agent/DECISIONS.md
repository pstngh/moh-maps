# Decisions

## D-001 — Reality outranks continuity

Git, actual files, primary evidence, and executed validation are ground truth.
`STATE.md` is authoritative only after reconciliation; generated reports and
newer prose are not proof.

## D-002 — Acceptance is human

Latest candidate and accepted baseline remain separate. Only explicit user
approval of the exact tested candidate permits promotion. This follows prior
cases where technical automation missed defects later rejected by the user.

## D-003 — Evidence-first runtime and map claims

Investigate material uncertainty from primary evidence. Canonical OpenMoHAA
source may prove implemented runtime semantics, preferably paired with a
controlled run; it cannot prove visual fidelity, architecture, enjoyment,
polish, or acceptance. Detailed gates and human rejections live in
`VALIDATION.md` and `REJECTIONS.md`.

## D-004 — Minimal, isolated continuity

Continuity is only `AGENTS.md` plus `.agent/{GOAL,STATE,DECISIONS}.md`; one
active task does not justify `TASKS.md`. It adds no schema, validator, script,
automation, or project integration and may write only its own Markdown.

The rejected alternative was the large JSON checkpoint, validator/checkpoint
coupling, duplicate architecture document, and map-status ledger. Deleting the
continuity files must have zero build/runtime effect.

## D-005 — Preserve unfinished diagnostic replay

The three modified skill files remain one unfinished development checkpoint.
Continuity setup neither completes nor discards them because 43 tests passed
but real-bundle replay and independent validation remain incomplete. Resume
only under an explicit development instruction.
