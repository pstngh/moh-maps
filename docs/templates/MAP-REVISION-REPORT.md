# Map revision report template

Copy this file into the working notes for every material map revision.

## Identity

- Map:
- Revision:
- Date:
- Commit before work:
- Goal:
- User evidence:
- Compatibility target:

## Baseline

- Previous PK3 SHA-256:
- Previous BSP size/faces/clusters:
- Known debt entering revision:
- Fixed regression viewpoints:

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

| ID | Location/view | Visible symptom | Suspected shared cause | Confidence |
| --- | --- | --- | --- | --- |
| | | | | |

## Planned changes

| Defect IDs | Cause-level change | Expected count/visual effect | Risk |
| --- | --- | --- | --- |
| | | | |

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

## Runtime and bot validation

- Exact isolated PK3 tested:
- OpenMoHAA version:
- Bot configuration:
- Navigation-build result:
- Spawn/respawn result:
- Routes observed:
- Combat/kills observed:
- Stalls or collision defects:

## Visual regression matrix

| View | Baseline defect | Result: fixed/improved/unchanged/regressed | Evidence |
| --- | --- | --- | --- |
| Spawn route | | | |
| High overview | | | |
| Long exterior | | | |
| Deep interior | | | |
| Transition | | | |
| Map edge | | | |
| Displacement boundary | | | |
| Repeated modules | | | |

## Outcome

- Fixed:
- Improved:
- Unchanged:
- Regressed:
- Newly exposed:
- Remaining known debt:

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| BSP | | |
| PK3 | | |
| Source archive | | |

## Knowledge promotion

- Map README updates:
- Research-log evidence added:
- Playbook rules added or changed:
- Asset-catalog entries added:
- Open questions/hypotheses:

## Release checklist

- [ ] Source/generator is reproducible.
- [ ] BSP, VIS, and full light succeeded against retail AA data.
- [ ] Exact isolated PK3 loaded.
- [ ] Required spawn classes/scripts are present.
- [ ] Bots spawned, moved, and fought.
- [ ] Regression views were inspected.
- [ ] Known debt is documented honestly.
- [ ] Hashes match repository artifacts.
- [ ] Documentation is updated.
- [ ] Commit is pushed.
