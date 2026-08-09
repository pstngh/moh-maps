# V2 Facility: Expanded Complex

`codex_obj_team2_expanded` retains the original Allied Assault `obj_team2` map and Objective graph, expands its east service complex, and adds a complete forest-side combat loop from Allied spawn around the bunker into the rear/east yards.

Revision 4 removes the entire cooperating west/south/east fence system—not only its visible panels. The removal covers 59 untargeted fence/wire/post entities and 33 world brushes used for curbs, rails, and collision, including four invisible playerclips. Twenty-four exact foliage owners were removed where they blocked the completed route. No new fence or brick/curb boundary was reconstructed.

The route is deliberately substantial: an open Allied court, west transition, eleven-step forest climb, west ridge, 1,024-unit central causeway, east ridge, fourteen-step descent, lower forest lane, and wide annex entry. Minimum designed combat width is 320 units. The central terrain gap is now a sealed, landscaped exterior with retaining structure, tree planters, stock oaks, a finished facility facade, service doors, lights, shelters, utilities, and cover.

## Install and play

Copy `codex_obj_team2_expanded.pk3` into `main`, then use Objective mode:

```text
g_gametype 4
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

For a neutral-spawn bot-combat topology test, the same BSP can run as FFA:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

The deterministic three-entry package contains only the BSP and two thin wrapper scripts. It executes the retail `obj_team2` scripts and resolves every material/model from stock AA data; it redistributes no retail or custom asset bytes.

## Revision 4 result

- Preserves all 23 rotating doors, 88 targetnames, 16 Allied starts, 16 Axis starts, and the retail Objective graph/scripts.
- Adds 334 brushes, 152 entities, and 21 neutral deathmatch starts over the retained source.
- Removes all 59 identified fence entities, all 33 cooperating fence/curb/rail/clip brushes, all four invisible fence playerclips, and 24 route-blocking foliage entities.
- Completes a continuous Allied-spawn-to-annex forest loop with 320-unit minimum combat width and a 1,024-unit central crossing.
- Fills the original central terrain/hull gap with a joined foundation, side hulls, stock-height sky ceiling, retaining wall, landscape, and finished industrial facade.
- Fully skins ambiguous added structural faces with solid stock materials; no custom texture payload is required.
- Adds `tools/inspect_map_terrain.js` plus map-specific source, layout, validation, reporting, and compiled-zone audits.

The exact ownership inventory, hull-leak investigation, construction dimensions, QA evidence, and reusable lessons are recorded in [`REVISION-4.md`](REVISION-4.md).

## Validated revision 4

- Canonical source: `aa/obj_team2.map`, 5,478,775 bytes, unchanged.
- Generated MAP: 5,637,967 bytes; structural validation reports revision 4 valid.
- BSP19: 19,624 surfaces, 67 lightmap pages, 131,080 visibility bytes, and 35 total neutral deathmatch starts.
- Q3map/VIS/MOHlight completed in 119.793/0.398/320.630 seconds; `.prt` exists, `.lin` does not, with zero degenerates, light clamps, or light hash warnings.
- Compiled route audit: 51 Allied-perimeter, 172 west-route, 288 central-causeway, 328 east-return, and 2,036 annex surfaces.
- Objective QA: Recast 2.150 s, all eight bots admitted, five combat events in 60 s, and zero candidate diagnostics.
- FFA QA: Recast 2.134 s, all eight bots admitted, four combat events in 60 s, and zero candidate diagnostics.
- Visual QA: 28 exact-candidate screenshots cover the stock frontage, annex, entire forest loop, both transitions, central completion, and overheads; zero visual-script errors.
- Package inventory: exactly one BSP and two wrapper scripts.

Q3map's `textures/notexture` warning and stock helper/light leak classifications are inherited. They are not a structural leak: Q3map wrote the portal file, produced no line file, VIS succeeded, and the candidate emitted no runtime diagnostic.

Rebuild from the repository root with:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_obj_team2_expanded -Threads 4
```

## Artifact hashes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,637,967 | `871719b096129a5db24e94b77f5c3ba980aacdd4a796fd2fa9d48f415f2a8070` |
| BSP | 13,873,788 | `140ee2bf482ca4f83f1ecea11aee9d79d377cdf2974111a190fe1a9c1b1792eb` |
| PK3 | 2,543,033 | `4b85f8ede35726bbb6ea5f6f71480e2b8a2b10e47930f490c7082156e2833918` |
| Visual contact sheet | 13,031,828 | `fe8d438940bdd655dbbed927a2d336b9975490cc498972ce322aed07a530df62` |

## Remaining human gate

Automated tests prove deterministic generation, sealing, rendering coverage, exact-package loading, Recast generation, bot admission, and combat. They do not prove how often bots choose every branch, Objective balance, or full door/objective completion.

The next human pass should walk continuously from Allied spawn through the west forest climb, central causeway, east descent, lower lane, and annex; then exercise all original doors and complete the Objective sequence. Any human failure angle should become another named fixed regression view.
