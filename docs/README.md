# Map-generation documentation

The documentation is split by purpose so future work can find the current rule
without losing the experiments that established it.

| Document | Role | Read when |
| --- | --- | --- |
| [`../AGENTS.md`](../AGENTS.md) | Fresh-session bootloader | At the start of every coding-agent session |
| [`../.agent/GOAL.md`](../.agent/GOAL.md) | Stable goal, constraints, and non-goals | At the start of every task |
| [`../.agent/STATE.md`](../.agent/STATE.md) | Current continuation point when consistent with Git | At the start and before every meaningful stop |
| [`../.agent/DECISIONS.md`](../.agent/DECISIONS.md) | Durable non-obvious rationale | When changing policy or interpreting state |
| [`../REJECTIONS.md`](../REJECTIONS.md) | Human rejections and superseded claims | Before reusing generated work |
| [`../VALIDATION.md`](../VALIDATION.md) | Candidate production and acceptance gates | During planning and validation |
| [`../.agents/skills/mohaa-map-builder/references/openmohaa-source-guide.md`](../.agents/skills/mohaa-map-builder/references/openmohaa-source-guide.md) | Pinned canonical engine-source routing index | Before any runtime-behavior conclusion |
| [`MAP-GENERATION-PLAYBOOK.md`](MAP-GENERATION-PLAYBOOK.md) | Normative production workflow, subject to the evidence hierarchy | Before every map task |
| [`STOCK-AA-ASSET-CATALOG.md`](STOCK-AA-ASSET-CATALOG.md) | Stock names and role-scoped observations | Before material or prop work |
| [`templates/MAP-REVISION-REPORT.md`](templates/MAP-REVISION-REPORT.md) | Repeatable evidence record | During every material iteration |
| [`MOHAA-map-generation-notes.md`](MOHAA-map-generation-notes.md) | Chronological experiments and case studies | When diagnosing or extending a rule |
| `generated/<map>/README.md` | Map-specific history, installation, limitations, and hashes | Before changing that map |

## Evidence priority

1. Explicit current user requirements and approval or rejection.
2. Original source files and directly observed engine behavior.
3. Engine, editor, and compiler source code.
4. Controlled runtime and compile experiments.
5. Original reference screenshots and geometry.
6. Verified repository documentation.
7. Codex-generated artifacts.

Human rejection supersedes automated success and earlier repository language.
The current checkpoint and `REJECTIONS.md` control map status. Historical
sections remain useful evidence but are not authoritative merely because they
are newer or describe a successful build.

Until individually audited, every existing repository document and generated
report is an untrusted index, not proof. Trace a specific claim to primary
engine/tool source, original map or asset data, a controlled runtime result, or
full-resolution human evidence as appropriate. OpenMoHAA source is authoritative
for implemented runtime semantics at the inspected commit, but cannot establish
map architecture, geometry, visual fidelity, material or lighting quality,
combat layout, enjoyment, polish, or acceptance.

## Learning flow

```text
playtest or experiment
        |
        v
revision report with scoped evidence labels
        |
        +--> map-specific result --> generated/<map>/README.md
        |
        +--> chronological evidence --> research log
        |
        +--> verified reusable rule --> playbook
        |
        +--> role-scoped asset behavior --> stock asset catalog
        |
        +--> human rejection/supersession --> REJECTIONS.md + .agent/STATE.md
```

## Current repository map line

This table is an index, not an acceptance list. `.agent/STATE.md` is the
authoritative status record. No current Codex-generated map is an accepted
baseline.

| Map | Conservatively supported state | Principal debt or status boundary |
| --- | --- | --- |
| `codex_arena01` | Experimental compiled DM/bot prototype | Prototype art/lighting; no human acceptance |
| `codex_dust2_v2` | Latest candidate, revision 10 | Positive feedback is not final approval; port fidelity and art substitutions require audit |
| `codex_cobblestone` | Candidate, revision 4 | Unresolved visual/structural defects, planar terrain, incomplete exterior boundary/skybox |
| `codex_nuke` | Experimental, revision 4 | Incomplete, empty in places, visually broken, and not accepted |
| `codex_cache` | Candidate, revision 1 | Human visual/door review, possible `-notjunc` seams, large omitted prop set |
| `codex_inferno` | Candidate, revision 5 | Improved but substantial content remains missing; not accepted |
| `codex_reactor` | REJECTED revision 1 negative case | Explicitly rejected as extremely buggy and a mess |
| `codex_v2_depot` | Experimental revision 1 | Human spawn, cover, brightness, and gameplay review pending |
| `codex_mohdm6_mirror` | Experimental revision 1 | Human rendered sweep and final approval absent |
| `codex_obj_team2_mirror` | Experimental revision 1 | Human visual/door/objective sweep and final approval absent |
| `codex_obj_team2_expanded` | REJECTED revision 4 negative case | Later human screenshot showed huge beige voids, disconnected-looking islands, crude slab/causeway work, and unfinished boundaries; automated visual conclusions are SUPERSEDED |
| `codex_obj_team4_mirror` | Experimental revision 1 | Human visual/door/bridge/objective sweep and final approval absent |
