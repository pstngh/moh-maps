# Codex Reactor revision 1

## Identity

- Map: `codex_reactor`
- Revision: 1
- Date: 2026-08-08
- Commit before work: `c9e45636dbd68dd0cdb681467292ecdd99c1cc1f`
- Goal: author an original Nuke-inspired AA/OpenMoHAA deathmatch map for
  predominantly close-range bot action without making the routes narrow
- User evidence: preference for clean modern industrial art, compiled AA
  compatibility, bot-first DM play, and repository knowledge that improves
  subsequent generated maps
- Compatibility target: Allied Assault BSP 19 and OpenMoHAA

## Baseline

- Previous PK3 SHA-256: none; this is a new map
- Previous BSP size/faces/clusters: none
- Known debt entering revision: original layout, lighting, material staging,
  bot topology, compiled package, and all QA had to be established
- Fixed regression viewpoints: loading yard, building threshold, reactor core,
  west/east lower service loops, rear crossover, upper loop, high core view

## Input measurements

This map imports no Source/Valve geometry. The measurements below describe the
authored result.

| Measurement | Value |
| --- | ---: |
| World brushes | 132 |
| Detail solids | 0 |
| Patches/displacements | 0 |
| Point entities | 65 |
| Imported props/models | 0 |
| Custom materials | 16 |
| Neutral/Allied/Axis spawns | 20 / 10 / 10 |
| Lights | 23 |

## Defect inventory

| ID | Location/view | Visible symptom | Suspected shared cause | Confidence |
| --- | --- | --- | --- | --- |
| R1 | First source validation | two spawn sets intersected stair brush volumes | stair-adjacent spawn centers were inside the 224-unit steps | proven |
| R2 | First BSP compile | five reactor-cover brushes used `undefined` | incorrect material property alias | proven |
| R3 | First BSP compile | sixteen high interior lights reported leaked | retail flood rejected fixture-adjacent point origins at z=316/324 | proven by controlled compile |
| R4 | Yard/threshold fixed views | decorative pier split the nominal 320-unit center entrance | facade decoration ignored the route opening | proven visually |
| R5 | West/east lower fixed views | broad under-mezzanine loops were too dim | ceiling point lights sat above solid mezzanine decks | proven visually |

## Planned changes

| Defect IDs | Cause-level change | Expected count/visual effect | Risk |
| --- | --- | --- | --- |
| R1 | move two lower spawn centers outside stair X bounds | zero spawn-hull collisions | low |
| R2 | use the defined `panel` material role | zero undefined-image warnings | low |
| R3 | place indoor point origins on the compiler-proven z=200 plane | zero light leak warnings while retaining visible fixtures | medium; required visual check |
| R4 | remove the x=0 facade pier | restore one continuous center entrance | low |
| R5 | add four underslung fixtures and z=112 point lights | readable lower loops without global overlighting | low |

## Material and asset decisions

| Surface/prop role | Candidates inspected | Selected asset or original art | Reason |
| --- | --- | --- | --- |
| Exterior yard | stock industrial surfaces; project palette | original `codex_nuke/asphalt` | clean modern ground, already licensed and validated |
| Walls/cladding | stock AA and original palette | painted concrete, blue/gray corrugated steel | modern facility identity without WWII styling |
| Catwalks/stairs | original palette | metal grating and metal trim | clear industrial circulation language |
| Reactor/safety bands | original palette | clean white metal, equipment blue, safety red/yellow, rubber | distinct central landmark and close-range orientation cues |
| Sky | retail shaders | `sky/mohday1` | stock AA shader behavior; no redistributed EA bytes |

No Valve image, mesh, map brush, or model byte enters the source or package.
See `ART-PROVENANCE.md`.

## Conversion result

- Generated world brushes: 132
- Converted/skipped source solids by class: 0 / 0; original construction
- Patches/displacements/backings/skirts: 0 / 0 / 0 / 0
- Prop substitutions: 0 imported models; cover and landmark are authored
  brush systems
- Spawn entities: 20 DM, 10 Allied, 10 Axis, one start
- Lights: 23
- Route graph: 8 zones, 17 edges, 192-unit minimum declared width
- Moving doors: 0
- Warnings: zero after the controlled material/light-origin repairs

Two clean generator roots reproduced the final MAP, scripts, and design report
byte-for-byte. The canonical validator reports zero collisions across all 40
DM/team spawn hulls.

## Compile result

| Stage | Result | Duration | Key counts/warnings |
| --- | --- | ---: | --- |
| Q3map BSP | passed | 0.454 s | 662 surfaces; no warning, leak, missing image, invalid brush, or incomplete line |
| Q3map fast VIS | passed | 0.412 s | 39,536 visibility bytes |
| Full MOHlight | passed | 1.332 s | 6 allocated/written lightmap pages; zero clamps/hash warnings |

The final BSP inspector confirms ident `0x35313032`, version 19, 23 retained
light entities, and the complete 20/10/10/1 spawn set.

## Runtime and bot validation

- Exact isolated PK3 tested: yes; retail Pak0-Pak6 plus only the candidate
- OpenMoHAA version: `0.82.1-beta+5.a72bc15` win_msvc64-x86_64
- Engine SHA-256: `ddb7d12666560701d914ff0d26b5082d686c1cc027407a929fb4950d24fbdafb`
- Bot configuration: DM, 16 clients, 8 max bots, 8 requested bots
- Navigation-build result: BSP parse 0.003 s; Recast 0.190 s
- Spawn/respawn result: all eight bots entered
- Routes observed: a separate QA-only position probe sampled all eight bots
  twelve times at two-second intervals; 96 samples covered all eight designed
  zones, including both lower loops, both mezzanines, the rear catwalk, rear
  service, reactor hall, and loading yard
- Combat/kills observed: 11 events in the final exact-package 30-second sample;
  15 events during the separate instrumented route sample
- Stalls or collision defects: none observed; every bot changed position and
  each covered 2-5 classified zones during the route sample
- Candidate-specific fatal/missing diagnostics: 0 / 0

The stock-only test root reports eight calls to the absent optional
`global/bot_run.scr`. Native Recast bots still moved across all zones and
fought; no map-local substitute was added.

## Visual regression matrix

| View | Baseline defect | Result | Evidence |
| --- | --- | --- | --- |
| Spawn route / yard | no prior rendered baseline | passed | warm sky/direct light, staggered cover, continuous ground |
| High core view | camera initially intersected the reactor | fixed | offset high view shows reactor, cover ring, floor, and upper edges |
| Long exterior | center pier created two small lanes | fixed | final yard frame shows a continuous center opening |
| Deep interior | under-mezzanine routes too dim | fixed | final west/east frames show floor, cover, supports, and dedicated fixtures |
| Transition | threshold was visually blocked by the center pier | fixed | reactor landmark reads directly from the yard entrance |
| Map edge | sealed shell required confirmation | passed | yard/facade and rear/side surveys show no void or missing wall |
| Displacement boundary | not applicable | passed by omission | no displacement or patch geometry exists |
| Repeated modules | bilateral facility system risked monotony | accepted | blue/gray cladding, yellow center bay, staggered yard cover, and asymmetric machinery break the repetition |

The eight camera-only screenshots used the exact final BSP and texture package
plus a loose QA script that changed only player origin/viewangles and issued
screenshot commands. They are local evidence, not distributed payload.

## Outcome

- Fixed: spawn/stair overlap, undefined material, light-origin leak warnings,
  false center-entry choke, and dark under-mezzanine routes
- Improved: close-range readability, three-entrance approach choice, vertical
  circulation, and purposeful modern-industrial lighting
- Unchanged: static no-door policy and original/project-owned art policy
- Regressed: none found in the final fixed-view, compile, or bot samples
- Newly exposed: retail camera harness leaves normal spectator/HUD text in QA
  captures; it does not affect map rendering or play
- Remaining known debt: longer human matches may suggest spawn or cover tuning;
  the compact authored architecture is intentionally simpler than Valve's Nuke

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| MAP | 90,402 | `889a84e7a4a7712502ab9b186ac27760100a197168386b6d6025bb606055339f` |
| BSP | 774,508 | `4a7ede5d74338d01e26c0cc0ae3beba2462ede46baec3f63a7c36a943f540d57` |
| PK3 | 3,290,168 | `3287d9c12ad1311f7cc871aff551431e7d7fbdc911d20195dc41b453c429f6e1` |

The 19-entry PK3 was built twice to identical bytes and every reopened entry
was decompressed and hash-checked against its source.

## Knowledge promotion

- Map README updates: identity, design metrics, rebuild, QA, hashes, and debt
- Research-log evidence added: original close-range topology, retail light
  flood experiment, underslung-fixture visual repair, deterministic package,
  exact bot run, and position-sampled route coverage
- Playbook rule added: solid mezzanine decks require under-deck lighting to be
  evaluated separately; ceiling lights above them do not prove lower-route
  readability
- Asset-catalog entries added: none; no new stock asset was characterized
- Open questions/hypotheses: human brightness preference and long-session
  spawn fairness remain subjective follow-up gates

## Release checklist

- [x] Source/generator is reproducible.
- [x] BSP, VIS, and full light succeeded against retail AA data.
- [x] Exact isolated PK3 loaded.
- [x] Required spawn classes/scripts are present.
- [x] Bots spawned, moved, and fought.
- [x] Regression views were inspected.
- [x] Known debt is documented honestly.
- [x] Hashes match repository artifacts.
- [x] Documentation is updated.
- [x] Commit is pushed.
