# V2 Facility: Expanded Complex

`codex_obj_team2_expanded` keeps the original Allied Assault `obj_team2` Objective map and adds a large playable east service complex plus an Allied-spawn exterior route into the yards behind the bunker. Revision 3 removes the complete old east fence/curb system and replaces the two small entries with a continuous 1,824-unit-wide, six-step apron.

The L-shaped annex now contains south and north three-bay workshops, a four-bay main hall with partitions and catwalk, canopy, west arcade, roof plant, utilities, cover, 23 fixture/light groups, and 12 neutral DM starts. The Allied route opens a 326-unit gate and supplies a 320-unit-wide outer lane and rear link. The original Objective graph, 23 rotating doors, 88 targetnames, and 16 Allied plus 16 Axis starts remain intact.

## Install and play

Copy `codex_obj_team2_expanded.pk3` into `main`, then use Objective mode:

```text
g_gametype 4
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

For bot-combat topology testing, the same BSP can run as FFA:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

The deterministic three-entry package contains only the BSP and two thin wrapper scripts. It executes the retail `obj_team2` scripts and resolves every material/model from stock AA data; it redistributes no retail or custom asset bytes.

## Revision 3

- Removed the entire eastern boundary system: 19 fence/post/wire entities, eight world fence/rail/curb brushes, and nine footprint foliage entities.
- Expanded the addition to 205 fully solid-skinned brushes and 94 entities. Added construction contains no caulk, nodraw, or alpha grate material.
- Replaced the two 288-unit entries with one continuous 1,824-unit grand apron.
- Added the finished north workshop and enlarged the main hall to four bays, with more circulation, catwalk structure, roof plant, cover, utilities, props, lights, and starts.
- Opened the Allied spawn perimeter by removing one fence panel/post, the continuous curb/rails/player clip, and one route tree, then rebuilding the adjacent boundary as split solid sections.
- Added a broad L-shaped exterior route from Allied spawn to the rear bunker yard. Neighboring fence remains on the sides of the 326-unit opening; no fence panel spans the gate.
- Added generic MAP owner and BSP19 regional-surface inspection tools so later boundary changes can be audited before and after compile.

Exact ownership, the rejected leaking footprint, hull constraints, QA, and artifact evidence are recorded in [`REVISION-3.md`](REVISION-3.md).

## Validated revision 3

- Canonical source: `aa/obj_team2.map`, 5,478,775 bytes, unchanged.
- Generated MAP: 5,598,022 bytes; 205 added brushes and 94 added entities.
- Preservation: 23 doors, 88 targetnames, 16 Allied starts, and 16 Axis starts retained; exact equality after 31 documented untargeted entity removals and 12 world-brush removals.
- BSP 19: 19,224 surfaces, 66 lightmap pages, 68,840 visibility bytes, and 26 total neutral DM starts.
- Q3map/VIS/MOHlight: full compile succeeded; portal file written; no line file, degenerates, light clamps, or light hash warnings.
- Compiled east-boundary audit: zero `secfence`/`barbwire` surfaces and no original bottom curb in the removed zone.
- Objective QA: exact eight-package root, Recast 2.224 s, all 8 bots admitted, combat observed, and zero candidate diagnostics.
- FFA QA: exact eight-package root, Recast 2.125 s, all 8 bots admitted, 3 combat events in 45 s, and zero candidate diagnostics.
- Visual QA: 18 exact-candidate screenshots covering the old-side frontage, both workshops, hall/catwalk, overview, Allied gate from both directions, outer lane, and rear turn; zero script errors.

Q3map's one `textures/notexture` image warning and four messages labeling unchanged stock corona helpers as leaked lights are inherited/classified. This is not a structural leak: Q3map wrote the `.prt`, no `.lin` exists, and VIS completed. Runtime emitted no candidate diagnostic.

Rebuild from the repository root with:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_obj_team2_expanded -Threads 4
```

## Artifact hashes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,598,022 | `b601d530d86f6b113af38e0ad9e57178c5bb69b5320670f304dc67976ce2553d` |
| BSP | 13,328,296 | `425490de3ee0520facaf0b08edf9f8376fd1875ab023a41abdb280be520927f1` |
| PK3 | 2,387,483 | `93390daf91f49b03712685539eb194ff4db15629d78ada9bbfa95031d87c9394` |
| Visual contact sheet | 1,051,206 | `6273284f84b245b9aad80adeee7cfecad77db42ea2cb08757d076e81ddbda7e1` |

## Known debt and human gate

The automated gates prove deterministic generation, structural sealing, rendering coverage, exact-package loading, Recast generation, bot admission, and combat. They do not prove that bots choose every new route or that the original Objective sequence remains balanced.

Human revision-3 testing remains authoritative. Please verify the removed east fence/curb from the same stock-side viewpoint, traverse the full apron and every bay/catwalk route, enter the new Allied gate and follow the outside lane into the rear bunker yard, then exercise the original doors and Objective sequence. The retained side fence panels and overhead wire frame the Allied opening without spanning its walkable gate; their appearance can be revised after the in-game route test if desired.
