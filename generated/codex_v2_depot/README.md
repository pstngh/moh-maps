# V2 Depot

`codex_v2_depot` is an original AA/OpenMoHAA DM and TDM map built from the measured construction grammar of `aa/obj_team2.map`. It borrows stock-map grid sizes, thicknesses, face flags, material families, lighting ratios, fixture conventions, and layered industrial composition, but does not copy the stock layout.

The map has a sunlit loading yard, three permanently open bunker entrances, a central assembly hall, two broad service loops, a rear crossover, and a U-shaped upper catwalk reached by two wide stairs. It is compact and looped for bots without becoming a corridor maze.

## Install and play

Copy `codex_v2_depot.pk3` into `main`, then run:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map dm/codex_v2_depot
```

It supplies 18 neutral DM starts, 8 Allied starts, 8 Axis starts, and one player start.

## Stock construction policy

- The real `obj_team2` source was measured for brush/face counts, alignment, thicknesses, scales, flags, entity classes, light levels, spawn conventions, patch use, and materials.
- Visible faces use an inspected stock palette. Hidden box faces default to `common/caulk`; 424 of 1,150 faces are caulked.
- Structural work uses a 16-unit grid and mostly 32-unit thickness. Stairs use 16-unit rises, 32-unit treads, and 224-unit width.
- Caged lamps, coronas, utility boxes, crates, steel, concrete, bunker panels, grates, and a grounded Opel truck establish the industrial language.
- Ambient, sky fill, sunlight, fixtures, and under-catwalk fill are separate lighting layers.

No retail asset bytes are redistributed. The three-entry PK3 contains only the BSP and two scripts; visible assets resolve from retail AA data.

## Validated revision 1

- Shell: x -1536..1536, y -1280..1280, z -64..608.
- Routes: 10 zones, 15 links, 192-unit minimum; main openings are 256 units or wider.
- Doors: none; all bot routes remain permanently open.
- Source: 189 brushes, 1,150 faces, 25 lights, 41 stock model placements, and 21 stock shaders.
- BSP: version 19, 713 surfaces, 5 lightmap pages, 1,128 visibility bytes.
- Compile: zero Q3map warnings, zero light clamps, and zero light hash warnings.
- Visual QA: 8 fixed screenshots/markers and zero script errors; only a camera script overrode the exact candidate.
- Bot QA: exact Pak0-Pak6-plus-candidate root, Recast 0.127 s, all 8 bots entered, 23 combat/death events in 40 s, and zero candidate/stock-model diagnostics.

Rebuild with `generated/codex_v2_depot/tools/build_v2_depot.ps1`; it regenerates and validates source, runs retail BSP/VIS/full light, inspects BSP 19, and requires two byte-identical packages.

## Artifact hashes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 137,984 | `61ee413bd42b3f5646fad77beed3ced395ac60737d0c28ae81fae43879a9aa5d` |
| BSP | 655,120 | `f2a5a2b920bcb418a27b146612455db11014b1b854f809c5abc8f911a48cec30` |
| PK3 | 112,494 | `a46451bc445281079b647817b4bc45ec5137b0fd15a8f16d96b6d059bb826245` |

## Known debt

This is a first release candidate, not a claim that human play has made it perfect. A longer bot match must still judge spawn fairness, cover density, and preferred brightness. There is no Objective mode. User screenshots and playtest verdicts override automated acceptance and should drive revision 2.
