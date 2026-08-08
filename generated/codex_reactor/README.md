# Codex Reactor

`codex_reactor` is an original, Nuke-inspired modern industrial deathmatch
map for Medal of Honor: Allied Assault and OpenMoHAA. It was authored from
scratch for close-range bot combat; it is not a conversion of Valve geometry.

The layout combines an open loading yard, three permanently open building
entrances, a central reactor hall, two broad lower service loops, a rear
crossover, two 224-unit stairs, and a connected upper U-route. The narrowest
declared route is 192 units, moving doors are intentionally absent, and the
reactor/equipment/container masses interrupt map-wide firing lanes.

## Install and play

Copy `codex_reactor.pk3` into the game's `main` directory, then run:

```text
sv_maxbots 8
sv_numbots 8
g_gametype 1
map dm/codex_reactor
```

The package supplies 20 neutral deathmatch spawns, 10 Allied spawns, 10 Axis
spawns, one start, the map scripts, and 16 project-owned original textures.
Retail Pak0-Pak6 are still required for the stock sky, multiplayer scripts,
players, weapons, sounds, and effects.

## Design and bot policy

- Footprint: 3,072 x 2,560 units, enclosed from z=-64 through z=576.
- Topology: eight connected zones and seventeen declared route links.
- Close-range target: mostly 256-1,050-unit engagements, with central and
  staggered cover preventing one dominant cross-map sightline.
- Route floor: 192 units; lower entrances/openings are generally 256-416.
- Vertical circulation: two 224-unit-wide stairs with 32-unit treads and
  16-unit rises.
- Doors: zero. Every gameplay opening remains permanently traversable.
- Lighting: warm daylight and sky fill outdoors; restrained cool fixtures in
  the hall and upper level; dedicated underslung lights beneath both solid
  mezzanine decks.

## Source and rebuild

The deterministic source is under `main/maps/dm`; generation, validation, BSP
inspection, and the full build/package pipeline are under `tools`.

```powershell
.\tools\build_reactor.ps1 `
  -NodePath "C:\path\to\node.exe" `
  -RetailRoot "C:\path\to\retail-aa-root" `
  -MOHToolsDir "C:\path\to\MOHTools"
```

The script regenerates and validates the MAP, stages retail Pak0-Pak6 and the
exact 16-texture palette, runs retail Q3map, fast VIS, and full MOHlight,
inspects BSP 19 counts, creates the 19-entry PK3 twice, requires identical
bytes, then reopens the archive and hashes every decompressed entry.

The EA compilers and retail game data are not included in this repository.

## Validated revision 1

- Final source: 132 world brushes, 65 point entities, 23 purposeful lights.
- BSP: version 19, 662 surfaces, 6 allocated/written lightmap pages, 39,536
  visibility bytes.
- Compile: Q3map 0.454 s, fast VIS 0.412 s, full MOHlight 1.332 s.
- Diagnostics: zero Q3map warnings, zero light clamps, zero light hash
  warnings, and no missing custom image.
- Final package: 19 entries, 3,290,168 bytes; internally reproduced twice.
- Exact-package runtime: retail Pak0-Pak6 plus only this candidate; BSP parse
  0.003 s, Recast 0.190 s, all eight bots entered, 11 bot combat/death events
  in 30 seconds, and zero candidate-specific missing/fatal diagnostics.
- Visual regression: eight fixed in-engine views covered the yard, threshold,
  reactor core, both lower loops, rear crossover, upper loop, and high core
  overview. That pass removed a decorative center-entry choke and added four
  under-mezzanine fixtures before final validation.

OpenMoHAA's retail-only test root reports the known absent optional
`global/bot_run.scr`; native Recast bots still moved and fought, so the map does
not fabricate a replacement for that unrelated stock-environment message.

## Artifact hashes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 90,402 | `889a84e7a4a7712502ab9b186ac27760100a197168386b6d6025bb606055339f` |
| BSP | 774,508 | `4a7ede5d74338d01e26c0cc0ae3beba2462ede46baec3f63a7c36a943f540d57` |
| PK3 | 3,290,168 | `3287d9c12ad1311f7cc871aff551431e7d7fbdc911d20195dc41b453c429f6e1` |

## Known debt

This is a compact original arena, not a one-to-one Nuke clone. It deliberately
omits moving doors, vents, elevators, dynamic machinery, complex curved props,
and Valve assets. The geometry and lighting passed automated and fixed-camera
gates, but longer human matches may still suggest cover, spawn, or brightness
tuning. The package reuses the project's original Nuke-inspired diffuse
palette; see `ART-PROVENANCE.md` for scope and licensing boundaries.
