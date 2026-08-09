# V2 Facility: East Annex revision 2

## Trigger and verdict

- Date: 2026-08-09
- Trigger: the first human screenshot showed that revision 1 was visually incomplete and exposed invisible/backfacing construction surfaces
- Status: technically and fixed-view validated; human re-test remains authoritative

Revision 1's interior-focused contact sheet missed the stock-side view from which several new hall, lintel, retaining-wall, and trim faces used `common/caulk`. Those faces were only hidden under the original camera assumptions. Once the stock boundary became playable, they appeared as holes. The addition also read as a sparse platform and facade rather than a finished compound.

## Cause-level repairs

| Failure | Revision 2 repair |
| --- | --- |
| Caulked faces became visible from the newly opened side | every face of every added brush now receives a visible solid stock material |
| Alpha grate construction disappeared or read as an invisible edge | removed both `deckgrate` materials from all added construction; the canopy and mezzanine are solid |
| Visual QA omitted the user's outside angle | added `reported_stock_side` and `stock_side_overview` as the first two mandatory views |
| Annex looked like one unfinished platform/building | added two finished two-bay service sheds, roof/parapets, facade awnings, six ceiling ribs, three roof vents/caps, a dispatch island, eight bollards, more utility banks, crates, starts, and shed lighting |
| Revision 1 was described too positively | demoted revision 1 in the README/knowledge base and made human screenshots an explicit acceptance override |

The new validator rejects `common/caulk`, `common/nodraw`, `deckgrate_set1a`, or `deckgrate_set1b` anywhere in the marked expansion geometry. It also requires six recorded face materials for every added brush, both service sheds, all three facade awnings, and all six ceiling beams.

## Inventory and preservation

| Item | Revision 1 | Revision 2 |
| --- | ---: | ---: |
| Added brushes | 102 | 156 |
| Added entities | 35 | 53 |
| Neutral DM starts | 6 | 8 |
| Added light groups | 8 | 12 |
| Fully solid-skinned added brushes | not guaranteed | 156 / 156 |
| Transparent added construction materials | 2 | 0 |

The expansion still removes only the same nine untargeted footprint foliage entities and five untargeted connector obstructions. The original 23 rotating doors, 88 targetnamed entities, Objective graph, and 16 Allied plus 16 Axis starts remain preserved. The source-stripped equality gate still passes.

## Build and runtime evidence

| Gate | Revision 2 result |
| --- | --- |
| Q3map | 121.914 s; 19,053 surfaces; 136 classified warnings; zero leaks/degenerates |
| Fast VIS | 0.287 s; 58,528 visibility bytes |
| Full MOHlight | 376.547 s, one thread; 63 pages; zero clamps/hash warnings |
| Objective runtime | BSP 0.120 s; Recast 2.065 s; 8 bots; 2 combat events/35 s; zero candidate diagnostics; 5 inherited script errors |
| FFA runtime | BSP 0.135 s; Recast 2.091 s; 8 bots; 2 combat events/45 s; zero candidate diagnostics; 7 inherited script errors |
| Fixed views | 14 screenshots/markers including the reported outside angle; zero script errors |

The warning delta is understood: revision 2 adds four more stock corona helpers than revision 1, so Q3map reports 136 warnings instead of 132. The extra notices are optional static `.map` helpers; the exact runtime package emits no candidate diagnostic.

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| Generated MAP | 5,585,462 | `398f42625ea2970fbca01607c9c72ebf05465ec003fb6abdecf6214b42b231fc` |
| BSP | 13,000,688 | `48d0a46bee62f51db8164641bcc99fb26ddf5d005cce808673fe6a3e00811ba0` |
| PK3 | 2,317,942 | `b7c55baf2002aee31c8c53c322ba3289779f55053afc6bf69ce9ae7630a2a19e` |

The map-size value is verified from the final build report before publication. The deterministic package contains only the BSP and two thin wrapper scripts and was reproduced byte-identically twice.

## Remaining human gate

Revision 2 fixes the reported cause and is visibly fuller in the exact outside-angle regression frame, but it is not called perfect. Human play must verify the same viewpoint in the user's renderer/settings, walk both service sheds and all hall/mezzanine routes, exercise the original doors/objective sequence, and judge whether the enlarged Axis-side annex is fun and balanced.

- [x] User failure reproduced as a mandatory camera angle
- [x] No invisible/alpha material in added construction
- [x] 156/156 expansion brushes have six visible face materials
- [x] Compound substantially expanded and dressed
- [x] Full compile, VIS, and light
- [x] Exact Objective and FFA eight-bot QA
- [x] Fourteen-view contact sheet inspected
- [ ] Human revision 2 re-test
