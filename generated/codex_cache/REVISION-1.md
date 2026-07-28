# Cache revision 1: measured playable baseline

Date: 2026-07-27

Status: compiled, full-lit, packaged, and exact-PK3 eight-bot tested; human
map-view and door review pending

## Goal

Create a recognizable, modern/clean Cache DM baseline for Allied Assault and
OpenMoHAA without repeating Nuke revision 2’s model-hull inference failure.
Preserve measured layout and gameplay entities first; keep unsupported prop
geometry as explicit debt.

## Source and geometry evidence

- The 45,755,859-byte VMF contains 16,508 solids, 99,612 sides, 10,952
  displacement sides, and 7,643 entities.
- A three-axis playable filter excludes separate construction/skybox clusters.
- The generator emits 10,876 world-brush entries and 268 entities.
- It preserves 10,787 measured solids, planarizes 8,165 displacement faces,
  adds 83 traversable-terrain seam underlays, and retains 138 measured large
  clip volumes.
- It skips 1,379 small helper brushes and 3,800 distant-cluster solids.
- Zero brushes are reported invalid.

## Prop and door policy

All 2,588 ordinary Source prop placements inside the playable cluster remain
omitted unless their topology and pivot are independently established.
Model-name boxes, generic railings, facade fill, and guessed cover are
forbidden.

One actual `prop_door_rotating` is reconstructed as `func_rotatingdoor` using
its embedded IDST-v49 hull bounds and Source origin. Human interaction testing
is still required.

## Multiplayer and lighting

- 20 Terrorist spawns become Axis.
- 20 Counter-Terrorist spawns become Allied.
- 24 dedicated Source deathmatch spawns become neutral AA spawns.
- 232 playable light candidates are clustered to 201 retained fixtures.
- World lighting uses low ambient, neutral-warm direct sun, cool environment
  fill, and provisional stock `sky/m5l2`.

## Original art

The package uses 19 original 512×512 TGA surfaces. New Cache source art covers
muted industrial brick, weathered plywood, and cool blue-gray painted steel.
Shared project-owned sources cover concrete, asphalt, corrugated metal, grass,
and gravel. Five additional surfaces are generated procedurally.

All source art is made deterministically tileable and edge-verified. No Valve
image/model bytes are included.

## Static validation

- balanced map braces and one worldspawn;
- one measured rotating door;
- 20 Axis, 20 Allied, and 24 neutral DM spawns;
- all 17 referenced custom material names resolve to generated TGA images;
- all three custom shader definitions are present;
- no raw Source asset path;
- zero broad `surfaceparm nolightmap` sides;
- explicit omission policy and safety-count thresholds pass.

MAP fingerprint before retail compile:

- 8,482,127 bytes
- SHA-256
  `9966961E5C1D52B65D6BBB300699FF24E2EF3BDCBC6B4BB90619ABF8794DBEDC`

## Compile-budget evidence

The complete normal Q3map build reached:

- 63,578 input faces;
- 57,622 merged output faces;
- 84,040 vertices added during T-junction repair;
- 314,846 total vertices;
- then fatal `MAX_MAP_DRAWINDEXES`.

Compiler switches `-fast`, `-notjunc`, and `-nosubdivide` were isolated in
separate stages. Early processing remained expensive, proving that the brush
inventory—not only one cleanup stage—dominates compile time.

An optional `--compile-budget` generator probe kept broad/hero-scale
`func_detail` and omitted compact narrow trim. It produced 9,058 brush entries
but a normal Q3map build still failed `MAX_MAP_DRAWINDEXES` after 6,498 seconds
and 47,381 merged faces. It is not the release source.

The least destructive successful path is full geometry with Q3map
`-notjunc`. It retains all 10,876 brush entries and 57,622 merged faces, writes
the BSP in 10,895 seconds, and avoids only the 84,040 inserted T-junction
vertices. This is a technical success with explicit crack/seam visual debt,
not a general recommendation to disable T-junction repair.

Fast VIS completed with:

- 56 clusters;
- 97 portals;
- 456 visibility bytes;
- all 56 clusters visible on average.

Full MOHlight completed in 1,743 seconds. It reported:

- one potential hash mismatch near
  `(-20.0704 -81.628 1601) - (-163.523 -81.0403 1601)`;
- six entity-light leaves clamped from 63-103 lights to AA's cap of 60.

The lit BSP is 32,125,316 bytes with SHA-256
`653AEF5E9AE82FEA5FD68307CD67F1842E424DC611758875CB8EA779E16EE94C`.

## Exact-package runtime evidence

The 23-entry PK3 contains one BSP, two map scripts, one shader, and 19
original TGA textures. A fresh OpenMoHAA home contained only that package; its
clean base contained only retail Pak0-Pak6.

OpenMoHAA 0.82.1:

- loaded `dm/codex_cache` from the exact package;
- parsed the BSP in 0.180 seconds;
- generated Recast navigation in 3.567 seconds;
- admitted all eight bots;
- logged 55 combat/death events during the retained run;
- emitted zero Cache map/script/package/navigation/gameplay error matches.

The startup log also contains missing fresh-user config files, a stock
`allied_pilot.skd` box warning, and one 4.483-second navigation-build hitch.
Those are not Cache content failures.

The PK3 is 10,127,241 bytes with SHA-256
`90477F688E4115400813B119A2061434A1F62324381B3CC864FA7BAB29084C53`.

## Visual inspection status

The 19-material contact sheet was inspected and shows a coherent clean
industrial palette with no obvious stored-edge seam, text, or logo.

An automated OpenMoHAA client window was successfully launched and targeted,
but every captured application frame was black except for the OpenMoHAA
cursor. Console and Escape checks did not expose a usable renderer/menu state.
Those frames are not accepted as map evidence. Human exterior, interior,
transition, long-sightline, map-edge, lighting, door, and `-notjunc` crack
inspection remain mandatory.

## Pending gates

- [x] Deterministic generation
- [x] Original texture edge validation
- [x] Static map/material/entity validation
- [x] Retail AA Q3map BSP using documented `-notjunc` fallback
- [x] Fast VIS
- [x] Full MOHlight
- [x] Canonical PK3 packaging and fingerprints
- [x] Isolated exact-PK3 OpenMoHAA load
- [x] Recast navigation generation
- [x] Bots spawn, move, fight, die, and respawn
- [ ] Exterior/interior/transition/sightline/map-edge visual review
- [ ] Human door interaction review

## Known visual debt

- Source-only foliage, railings, pipes, awnings, small cover, and facade props
  are absent.
- Curved Source terrain remains planar.
- The distant 3D skybox is omitted.
- The sky and lighting profile have no Cache-specific human screenshots yet.
- `-notjunc` may expose cracks that normal Q3map would repair.
- Six runtime leaves exceed the entity-light list cap.
- Screenshot review may reveal coordinate-specific missing enclosure or
  material-role mistakes; repairs must be based on source/screenshot evidence.
