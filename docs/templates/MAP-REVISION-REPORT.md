# Map revision report template

Copy this file into the working notes for every material map revision.

## Identity and status

- Map:
- Revision:
- Date:
- Commit before work:
- Goal:
- User evidence:
- Compatibility target:
- Status (`candidate`, `experimental`, `rejected`, `unknown`, or `archived`):
- Accepted revision (only after explicit approval):
- Explicit user approval evidence:

Do not use `accepted` status without explicit approval of the exact tested
revision. Automated technical or visual gates are never approval evidence.

## Baseline

- Previous PK3 SHA-256:
- Previous BSP size/faces/clusters:
- Known debt entering revision:
- Fixed regression viewpoints:
- Accepted baseline, if any:
- Latest candidate:

## Input measurements

| Measurement | Value |
| --- | ---: |
| World solids | |
| Detail solids | |
| Displacements/patches | |
| Entities | |
| Props/unique models | |
| Materials | |
| Neutral/Allied/Axis spawns | |
| Lights | |

## Defect inventory

| ID | Location/view | Visible symptom | Suspected shared cause | Evidence label/confidence |
| --- | --- | --- | --- | --- |
| | | | | |

## Planned changes

| Defect IDs | Cause-level change | Expected count/visual effect | Risk |
| --- | --- | --- | --- |
| | | | |

## Evidence record

| Question | Sources and exact paths | Relevant lines/entities/coordinates/views | Conclusion | Label | Remaining uncertainty |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Material and asset decisions

| Surface/prop role | Candidates inspected | Selected asset or original art | Reason |
| --- | --- | --- | --- |
| | | | |

## Conversion result

- Generated brushes:
- Converted/skipped source solids by class:
- Patches/displacements/backings/skirts:
- Prop substitutions:
- Spawn entities:
- Lights:
- Warnings:

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP | | | |
| Q3map VIS | | | |
| MOHlight | | | |

## Package, runtime, and bot validation

- Exact isolated PK3 tested:
- Package inventory verified:
- Loose-file masking excluded:
- OpenMoHAA version:
- Intended mode and scripts:
- Bot configuration:
- Navigation-build result:
- Spawn/respawn result:
- Routes observed:
- Combat/kills observed:
- Doors/dynamic obstacles tested:
- Stalls or collision defects:

## Visual regression matrix

| View | Baseline defect | Result: fixed/improved/unchanged/regressed | Full-resolution evidence |
| --- | --- | --- | --- |
| Exact user failure angle | | | |
| Spawn route both directions | | | |
| High overview | | | |
| Long exterior | | | |
| Deep interior | | | |
| Transition | | | |
| Map edge/boundary | | | |
| Displacement boundary | | | |
| Repeated modules | | | |
| Previously hidden area | | | |

## Outcome

- Fixed:
- Improved:
- Unchanged:
- Regressed:
- Newly exposed:
- Remaining known debt:
- Claims marked `SUPERSEDED` or `REJECTED`:

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| MAP/source | | |
| BSP | | |
| PK3 | | |
| Full-resolution visual evidence | | |

## Knowledge and checkpoint

- Map README updates:
- Research-log evidence added:
- Playbook rules added or changed:
- Asset-catalog entries added:
- Decisions/rejections updated:
- Open questions/hypotheses:
- Exact next action:
- Stopping condition:

## Candidate checklist

- [ ] Source/generator is reproducible with recorded provenance.
- [ ] Geometry, materials, and lighting passed their applicable gates.
- [ ] BSP, VIS, and full light succeeded against retail AA data.
- [ ] Every warning is classified from evidence.
- [ ] Exact isolated PK3 contents and loading were verified.
- [ ] Required spawn classes/scripts are present.
- [ ] Bots spawned, moved, fought, respawned, and used multiple routes.
- [ ] Applicable doors/dynamic obstacles were tested.
- [ ] Exact failure angles and all changed viewing domains were inspected.
- [ ] Known debt is documented honestly.
- [ ] Hashes match repository artifacts.
- [ ] Documentation and `PROJECT_STATE.json` are current.
- [ ] User feedback is recorded; explicit approval is still separate.
- [ ] Explicit paths were staged and the staged diff inspected.
- [ ] Commit is pushed and local HEAD equals upstream.

## Human acceptance gate

- [ ] Exact candidate was provided for human testing.
- [ ] Feedback was recorded with provenance.
- [ ] User explicitly approved this exact revision.
- [ ] Only after approval: map status and `accepted_baseline` were updated.
