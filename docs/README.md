# Map-generation documentation

The documentation is split by purpose so future work can find the current rule
without losing the experiments that established it.

| Document | Role | Read when |
| --- | --- | --- |
| [`MAP-GENERATION-PLAYBOOK.md`](MAP-GENERATION-PLAYBOOK.md) | Normative production workflow and release gates | Before every map task |
| [`STOCK-AA-ASSET-CATALOG.md`](STOCK-AA-ASSET-CATALOG.md) | Verified stock texture/model names and selection policy | Before material or prop work |
| [`templates/MAP-REVISION-REPORT.md`](templates/MAP-REVISION-REPORT.md) | Repeatable record for a map revision | During every material iteration |
| [`MOHAA-map-generation-notes.md`](MOHAA-map-generation-notes.md) | Chronological evidence, measurements, experiments, and case studies | When diagnosing or extending a rule |
| `generated/<map>/README.md` | Current map-specific status, installation, limitations, and hashes | Before changing or releasing that map |

## Document priority

1. Current verified engine evidence
2. The playbook
3. The target map's current README and conversion report
4. Historical research notes

If verified evidence conflicts with the playbook, update the playbook in the
same revision. Historical sections should remain intact unless they contain a
factual transcription error; they document why earlier decisions were made.

## Learning flow

```text
playtest or experiment
        |
        v
revision report with evidence
        |
        +--> map-specific result --> generated/<map>/README.md
        |
        +--> chronological evidence --> research log
        |
        +--> confirmed reusable rule --> playbook
        |
        +--> verified asset behavior --> stock asset catalog
```

This separation is what makes the repository improve future maps instead of
merely accumulating a long diary.

## Current validated map line

| Map | Current validated state | Principal remaining debt |
| --- | --- | --- |
| `codex_arena01` | Original compiled DM prototype; OpenMoHAA navigation and bot movement proven | Prototype art and lighting |
| `codex_dust2_v2` | Revision 10; full compile, displacement repair, Mediterranean relight, eight-bot QA | Port fidelity and remaining Source-to-AA art substitutions |
| `codex_cobblestone` | Revision 4; revision-3 architecture retained, planar seams underlaid, measured source clips restored, eight-bot QA | Planar terrain, incomplete exterior boundary/3D skybox, and omitted Source-only architecture |
| `codex_nuke` | Revision 1; deterministic full-layout generator, fourteen original clean-industrial textures, four functional door entities, full compile, and exact-PK3 eight-bot QA | Human visual/route review, dense-fixture light budgeting, Source-only combined prop families, curved terrain, and distant skybox |
