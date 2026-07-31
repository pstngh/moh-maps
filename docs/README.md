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
| `codex_nuke` | Revision 5 unlit-surface repair on the revision-4 fidelity layer; 4,747 unlit fence/foliage/window faces relit onto an appended constant page (167 total) after user screenshots proved undefined texture binding; 1,932 ordinary prop placements / 2,855 original brushes, 22 original textures, lossless 194-to-166-page atlas repack, full compile/light, and exact-PK3 three-cycle eight-bot combat QA on the identical geometry | Human revision-5 screenshot review, conservative blocky substitutes, exterior terrain cracks, provisional sky, 28 clamped light leaves, 710 omitted autocombines, curved terrain, and distant skybox |
| `codex_cache` | Revision 1 first-playable; full measured brush cluster compiled with documented `-notjunc` draw-index fallback, nineteen original clean-industrial textures, one measured door, full light, exact-PK3 Recast, and eight-bot combat QA | Human map-view/door review, possible T-junction cracks, six clamped light leaves, planar terrain, 2,588 omitted Source props, and distant skybox |
| `codex_inferno` | Revision 5 technically validated measured prop-fill candidate; all 5,696 recognized rev4 brushes preserved, 1,176 high-impact prop substitutes added, full corrected `-notjunc` compile/light, and exact-PK3 eight-bot combat QA | Human rev5 visual/door review, planarized displacements, 5,024 omitted lower-value props, possible T-junction seams, distant skybox, and 6.55 MB nominal BSP-budget overage |
