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
| `codex_nuke` | Revision 4 measured visual-fidelity layer; 1,932 ordinary prop placements / 2,855 original brushes, 22 original textures, lossless 194-to-166-page atlas repack, full compile/light, fifteen-frame renderer QA, and exact-PK3 three-cycle eight-bot combat QA | Human revision-4 visual/door review, conservative blocky substitutes, exterior terrain cracks, provisional sky, 28 clamped light leaves, 710 omitted autocombines, curved terrain, and distant skybox |
| `codex_cache` | Revision 1 first-playable; full measured brush cluster compiled with documented `-notjunc` draw-index fallback, nineteen original clean-industrial textures, one measured door, full light, exact-PK3 Recast, and eight-bot combat QA | Human map-view/door review, possible T-junction cracks, six clamped light leaves, planar terrain, 2,588 omitted Source props, and distant skybox |
| `codex_inferno` | Revision 5 technically validated measured prop-fill candidate; all 5,696 recognized rev4 brushes preserved, 1,176 high-impact prop substitutes added, full corrected `-notjunc` compile/light, and exact-PK3 eight-bot combat QA | Human rev5 visual/door review, planarized displacements, 5,024 omitted lower-value props, possible T-junction seams, distant skybox, and 6.55 MB nominal BSP-budget overage |
| `codex_reactor` | User-rejected revision 1 retained as a negative case; technical gates passed, but it was reported buggy and messy and is not a visual baseline | Substantial cause-level redesign; do not base future geometry or visual claims on it |
| `codex_v2_depot` | Revision 1 original DM/TDM map from measured `obj_team2` grammar; stock-only palette, zero-warning full compile/light, eight fixed views, exact-PK3 eight-bot QA | Human review of spawn fairness, cover density, and brightness |
| `codex_mohdm6_mirror` | Revision 1 complete X-axis reflection of AA `mohdm6`; deterministic brush/patch/terrain/entity transform, full compile/light, exact-PK3 Recast, and eight-bot combat | Human rendered sweep; stock-source helper/leak warnings and three light clamps |
| `codex_obj_team2_mirror` | Revision 1 complete X-axis reflection of AA `obj_team2`; 23 doors and objective graph retained, full single-thread light, exact Objective boot/Recast plus FFA bot combat | Human visual/door/objective-completion sweep; stock-source warnings and retail-baseline `obj_dm.scr` diagnostics |
| `codex_obj_team2_expanded` | Revision 3; complete east fence/curb removal, 1,824-unit frontage, 205 fully skinned brushes, 326-unit Allied gate and exterior rear-yard route, preserved Objective graph/23 doors/team starts, full compile/light, 18-view QA, Objective plus FFA bot QA | Human revision-3 route/visual re-test, door/objective-completion and balance sweep; annex adds combat space but no new objective |
| `codex_obj_team4_mirror` | Revision 1 complete X-axis reflection of AA `obj_team4`; corrected cell-owned terrain controls, 13 doors and bridge objective graph retained, full single-thread light, exact Objective boot/Recast plus FFA bot combat | Human visual/door/bridge-destruction/objective-completion sweep; inherited warnings, five light clamps, and retail-baseline bridge script diagnostics |
