# V2 Facility: East Annex revision 3

## Identity

- Date: 2026-08-09
- Commit before work: `e7d275516de9045d850fcbaf360cb8687529b17c`
- Goal: make the annex substantially larger, remove the complete eastern fence/curb system, and connect Allied spawn to the yards behind the bunker
- User evidence: the revision-2 screenshot showed a small addition behind a chain-link fence and concrete/brick curb
- Compatibility: retail Allied Assault data plus OpenMoHAA; Objective mode remains authoritative, with FFA used for bot-topology exercise

## Baseline and defect inventory

| ID | Location | Symptom | Cause |
| --- | --- | --- | --- |
| R3-1 | Entire east frontage | Fence, posts, wire, rails, and bottom curb still separated the stock grounds from the annex | Revision 2 removed only two narrow connector owners instead of treating the boundary as one cooperating system |
| R3-2 | East annex | Addition still read as a small platform/facade | Footprint and frontage were too limited |
| R3-3 | Allied spawn exterior | No outdoor route reached the rear bunker yards | West fence, curb, rails, player clip, and foliage remained continuous |
| R3-4 | Initial larger north footprint | Q3map produced a structural leak | Apparently empty outdoor terrain extended beyond the stock map's direction-dependent sealed sky hull |
| R3-5 | First revision-3 fixed views | Two frontage cameras were embedded in the new apron steps | Camera origins were not revalidated after geometry expansion |

## Cause-level changes

- Removed stock east boundary entities 666-684, world brushes 1109-1115 and 1124, and nine footprint foliage entities.
- Replaced the two small approaches with one 1,824-unit-wide, six-step apron across the full playable frontage.
- Expanded the annex to an L-shaped deck with a three-bay south workshop, three-bay north workshop, four-bay main hall, internal partitions, catwalk, canopy, west arcade, roof plant, utilities, cover, 23 fixture/light groups, and 12 neutral DM starts.
- Opened a 326-unit Allied gate by removing entity owners 442 and 444, world curb/rail/player-clip brushes 819, 3224, 3228, and 3229, plus foliage entity 453.
- Added a 320-unit-wide L-shaped exterior route from Allied spawn to the rear bunker yard. Neighboring fence panels remain at the sides; no fence panel spans the opening. The old wire is overhead with 234 units of clearance above the route floor.
- Rejected the first rectangular north extension after focused Q3map leak probes. The final footprint keeps construction west of X=3584 south of Y=2208; only the eastern wing continues to Y=2496.
- Moved the two step-embedded cameras back to X=2944 and repeated the complete 18-view capture.

## Inventory and preservation

| Item | Revision 2 | Revision 3 |
| --- | ---: | ---: |
| Added brushes | 156 | 205 |
| Added entities | 53 | 94 |
| Neutral DM starts | 8 | 12 |
| Added fixture/light groups | 12 | 23 |
| Main-hall bays | 3 | 4 |
| Open frontage | two 288-unit connectors | one continuous 1,824-unit apron |
| Allied exterior gate | none | 326 units |

All 205 added brushes have six solid visible face materials. No added construction uses caulk, nodraw, or alpha grate materials. The original 23 rotating doors, 88 targetnames, Objective graph, and 16 Allied plus 16 Axis starts remain intact. Validation proves the retained serialization equals the canonical source minus exactly 31 untargeted entities and 12 documented world brushes.

## Compile and regional evidence

| Gate | Result |
| --- | --- |
| Q3map | 119.673 s; 19,224 final BSP surfaces; 151 classified warnings; zero degenerates; `.prt` written and no `.lin` |
| VIS | 0.297 s; 68,840 visibility bytes |
| MOHlight | 356.013 s, one thread; 66 lightmap pages; zero clamps/hash warnings |
| East BSP region | 280 surfaces inspected; zero `secfence`/`barbwire` surfaces and no old bottom curb in the removed boundary zone |
| Allied BSP region | 205 surfaces inspected; no fence panel spans Y=344..670; only the deliberately retained overhead wire crosses the gate volume |

The single `textures/notexture` image warning is inherited from `obj_team2`. Q3map also labels four unchanged stock `static_corona_orange` helpers as leaked lights (source entities 379-382 at `648 57 -90`, `1157 2490 167`, `1174 1598 -329`, and `1360 2432 -281`). They are not a structural leak: Q3map wrote the portal file, produced no leak line file, and VIS completed successfully.

## Runtime, bot, and visual validation

| Gate | Result |
| --- | --- |
| Objective | Exact 8-PK3 root; BSP 0.137 s; Recast 2.224 s; 8 bots; 2 combat events/40 s; zero candidate diagnostics; five inherited script errors |
| FFA topology | Exact 8-PK3 root; BSP 0.122 s; Recast 2.125 s; 8 bots; 3 combat events/45 s; zero candidate diagnostics; seven inherited script errors |
| Visual | 18 named exact-candidate views; zero script errors; full frontage, workshops, hall/catwalk, overhead, both Allied gate directions, outer lane, and rear turn inspected |

Automated runtime proves package loading, navigation generation, bot admission, and combat. It does not prove that bots select every new route or that the original Objective sequence remains balanced. Human walking, door/objective completion, and visual judgment remain authoritative.

## Artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,598,022 | `b601d530d86f6b113af38e0ad9e57178c5bb69b5320670f304dc67976ce2553d` |
| BSP | 13,328,296 | `425490de3ee0520facaf0b08edf9f8376fd1875ab023a41abdb280be520927f1` |
| PK3 | 2,387,483 | `93390daf91f49b03712685539eb194ff4db15629d78ada9bbfa95031d87c9394` |
| Visual contact sheet | 1,051,206 | `6273284f84b245b9aad80adeee7cfecad77db42ea2cb08757d076e81ddbda7e1` |

The three-entry PK3 contains only the BSP and two thin wrapper scripts and reproduced byte-identically twice.

## Knowledge promotion and remaining gate

- Added reusable MAP entity/world-brush and BSP19 regional-surface inspectors.
- Promoted complete boundary-system ownership, outdoor stock-hull probing, and post-geometry camera-origin validation to the playbook.
- Recorded the failed rectangular footprint and the proven safe L-shaped hull constraint in the research log.
- Human revision-3 retest must confirm the east fence/curb removal, walk the grand apron and every annex bay, enter the new Allied gate, follow the outer lane into the rear bunker yard, and exercise original doors/objectives.

- [x] Deterministic source and validator
- [x] Full BSP, VIS, and MOHlight against retail data
- [x] Exact-package Objective and FFA bot tests
- [x] Compiled regional fence/curb audit
- [x] Eighteen corrected visual views inspected
- [x] Artifact hashes recorded
- [ ] Human revision-3 playtest
