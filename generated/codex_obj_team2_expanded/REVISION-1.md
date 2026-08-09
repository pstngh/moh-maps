# V2 Facility: East Annex revision 1

## Identity and goal

- Map/revision/date: `codex_obj_team2_expanded` / 1 / 2026-08-09
- Editable baseline: `aa/obj_team2.map`
- Goal: expand the real stock map without disturbing its Objective gameplay graph
- Target: Allied Assault BSP 19 and OpenMoHAA

The expansion occupies the eastern wooded boundary and adds a close-range service annex connected at two points. It deliberately reuses the retail map and scripts instead of approximating `obj_team2` from scratch.

## Preservation contract

| Item | Result |
| --- | ---: |
| Original rotating doors retained | 23 |
| Original targetnamed entities retained | 88 |
| Original Allied / Axis starts retained | 16 / 16 |
| Untargeted footprint foliage removed | 9 |
| Untargeted connector obstructions removed | 5 |
| New brushes / entities | 102 / 35 |
| New neutral DM starts | 6 |
| New objective links or moving doors | 0 |

Validation strips marked additions and compares the remaining serialized source byte-for-byte with the original minus exactly the 14 allowlisted untargeted decorative entities. This prevents an additive edit from silently altering stock doors, objectives, targets, spawns, geometry, or scripts.

## Defects and repairs

| ID | Symptom | Cause | Repair |
| --- | --- | --- | --- |
| E1 | Empty source-space analysis suggested both approaches were open | one-sided stock boundary dressing occupied the compiled route despite sparse entity occupancy | added BSP-surface bounds inspection and examined both sides of each proposed connection |
| E2 | Fence and barbwire visibly/physically blocked the new steps | five untargeted detail/group entities formed the old map boundary | removed only those five exact entity blocks; retained fence segments outside the openings |
| E3 | A new wing could accidentally disturb stock Objective behavior | ordinary source editing provides no preservation proof | marked every addition/removal and required retained-source byte equality plus door/target/team-spawn counts |
| E4 | A single attachment could become a dead end | the annex footprint sits beyond the original perimeter | supplied two 288-unit-wide stepped connections and an internal return route |
| E5 | Props/lights could add custom dependencies | decorative expansion invites bundled art | used only stock AA materials/models and required zero custom asset bytes |

## Construction and visual evidence

The raised deck spans the uneven terrain, so the new play floor is continuous and supports every spawn and prop. Three open bays lead into the hall; a 128-unit-wide stair reaches the mezzanine. Concrete, bunker panels, structural metal, grates, utility boxes, crates, an Opel truck, caged lamps, coronas, and local lights follow the stock facility vocabulary.

Ten exact-candidate views cover both connectors, the facade, both yard lanes, hall center, stair, mezzanine, east return, and an oblique overview. The first pass exposed the stock fence/wire obstruction; the final contact sheet shows clean openings, supported props, readable interior circulation, and no obvious black wedge or missing boundary in those views.

## Compile and runtime evidence

| Gate | Result |
| --- | --- |
| Q3map | 110.543 s; 18,735 BSP surfaces; 132 classified warnings; zero leaks/degenerates |
| Fast VIS | 0.264 s; 47,448 visibility bytes |
| Full MOHlight | 342.057 s, one thread; 62 pages; zero clamps/hash warnings |
| Objective runtime | BSP 0.122 s; Recast 1.957 s; 8 bots; zero candidate diagnostics; 5 inherited stock script errors |
| FFA runtime | BSP 0.120 s; Recast 1.973 s; 8 bots; 4 events/45 s; zero candidate diagnostics; 7 inherited script errors |
| Fixed views | 10 screenshots/markers; zero visual-QA script errors |

The 132 Q3map warnings are classified rather than hidden: 127 optional `.map` helper notices (119 in the stock mirror plus eight new corona helpers), one inherited `textures/notexture` image warning, and the same four other stock helper notices. The final package was reproduced byte-identically twice and contains exactly three files.

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| Original source | 5,478,775 | `04cbee45bb4d94d5289d52b51e302984e3f6ce8843d7bdd0194500f4be35ee2f` |
| Generated MAP | 5,544,555 | `3a7fd859484b6392a54812f21eb12155ad624a56f77e202ad32ad0cf749148ce` |
| BSP | 12,779,232 | `7d01a19b7354278a990d940528d4666c52ced196c788a3648589feb22c9b1239` |
| PK3 | 2,280,274 | `f7aa8769474666a16d588280c44a025b811af14dc2374993d917f59e6fca6ea7` |

## Outcome and remaining debt

The stock facility now has a connected, lit, bot-navigable east annex while the original Objective graph remains structurally unchanged. The work also established a reusable additive-expansion validator and a compiled-BSP boundary audit.

Human play remains authoritative. It must verify the complete original door/objective sequence, assess route and spawn balance—especially the annex's natural proximity to the Axis side—and report views outside the fixed-camera set. The new area deliberately contains no objective target.

- [x] Original source preserved outside exact documented decorative removals
- [x] Two broad connections and no annex dead end
- [x] BSP, VIS, and full light
- [x] Exact isolated Objective and FFA bot runs
- [x] Fixed views inspected and initial obstruction repaired
- [x] Deterministic three-entry package
- [x] Hashes, debt, and reusable knowledge documented
- [ ] Human door/objective/balance playtest
