# Codex Cache

> **Evidence status (2026-08-10):** this map is an unaccepted candidate, not an
> accepted baseline or release-ready build. The historical technical, bot,
> visual, door, fidelity, and acceptance claims below are scoped and labeled in
> [CLAIM-AUDIT.md](CLAIM-AUDIT.md).

`codex_cache` is a first-playable Allied Assault/OpenMoHAA deathmatch
conversion of the classic Cache layout. The target is clean modern industrial
architecture, not a Second World War reskin.

Revision 1 preserves the measured playable brush layout, dedicated Source
deathmatch spawns, local fixture placement, and one verified interactive
door. It deliberately omits all unverified Source-only props. Human visual
review is still required and the build must not be described as polished.

The revision is compiled, full-lit, packaged, and exact-PK3 eight-bot tested.
Normal Q3map T-junction insertion exceeds AA's fixed draw-index budget, so the
distributed BSP uses `-notjunc` while retaining the complete measured brush
set. That makes human crack/seam inspection a mandatory next gate.

## Design brief

| Decision | Current answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM/TDM first; simple bot matches |
| Layout source | Measured CS:GO Cache reference |
| Asset policy | Original bundled art plus stock AA sky/utility shaders |
| Lighting | Neutral-warm daylight, cool environment fill, clustered real fixtures |
| Prop policy | Omit unless shape and pivot are independently verified |
| Explicit omissions | Graffiti, logos, signs, clutter, ordinary Source props, distant 3D skybox |

## Current generated inventory

- 10,876 world-brush entries;
- 10,787 retained measured Source solids;
- 8,165 planarized displacement faces;
- 83 material-matched displacement seam underlays;
- 138 retained measured large clip volumes;
- 1,379 small helper brushes omitted;
- 3,800 distant-cluster solids excluded;
- 2,588 playable unverified props explicitly omitted;
- one measured `func_rotatingdoor`;
- 20 Axis, 20 Allied, and 24 dedicated neutral DM spawns;
- 201 local lights retained from 232 playable candidates;
- 19 original 512×512 textures;
- zero invalid brushes and zero broad `surfaceparm nolightmap` sides.

See [`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) for source measurements and
policy, and [`ART-PROVENANCE.md`](ART-PROVENANCE.md) for original texture
provenance.

## Regenerating

From the repository root:

```powershell
python generated/codex_cache/tools/build_original_textures.py

node generated/codex_cache/tools/generate_cache.js `
  "path\to\de_cache_d.vmf" `
  generated/codex_cache `
  codex_cache

node generated/codex_cache/tools/validate_cache_build.js
```

Compile the generated map against a clean retail Allied Assault installation
in BSP, fast-VIS, and full-MOHlight order, then package:

```powershell
Q3map.exe -notjunc -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_cache.map"

Q3map.exe -vis -fast -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_cache.map"

MOHlight.exe -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_cache.map"

powershell -ExecutionPolicy Bypass `
  -File generated/codex_cache/tools/package_cache.ps1
```

Do not omit `-notjunc` from the current revision. A normal build merges 63,578
input faces to 57,622, adds 84,040 T-junction vertices, reaches 314,846 total
vertices, and fails with `MAX_MAP_DRAWINDEXES`. A 9,058-brush diagnostic still
fails the same limit after merging to 47,381 faces.

## Validation evidence

- Static validation passes all material, shader, spawn, door, omission, and
  raw-Source-path checks.
- Q3map `-notjunc` compiled 63,578 input faces to 57,622 output faces in
  10,895 seconds. One duplicate-plane diagnostic was non-fatal.
- Fast VIS completed with 56 clusters, 97 portals, and 456 visibility bytes.
- Full MOHlight completed in 1,743 seconds with one potential hash warning and
  six entity-light leaf clamps to AA's 60-light cap.
- The exact 23-entry PK3 loaded from a fresh OpenMoHAA home backed only by
  retail Pak0-Pak6.
- OpenMoHAA parsed the BSP in 0.180 seconds, generated Recast navigation in
  3.567 seconds, admitted all eight bots, and logged 55 combat/death events.
- No Cache map, script, package, navigation, or gameplay error was logged.
  Fresh-user config misses and a stock Allied pilot box warning are unrelated
  to the map.
- The 19-texture contact sheet passed visual art inspection. Automated client
  capture produced only a black application frame/cursor, so map-view visual
  inspection remains pending rather than being counted as passed.

## Playing

Copy `codex_cache.pk3` into the game’s `main` directory:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 4
map dm/codex_cache
```

## Known debt

- Human exterior, interior, transition, sightline, and map-edge screenshots
  have not yet been reviewed.
- Ordinary Source props remain absent, including foliage, railings, awnings,
  pipes, and small cover.
- Planar Source displacement backing preserves sealing and collision but not
  curved terrain fidelity.
- The real blue door needs human alignment, swing, activation, and clearance
  testing.
- The provisional stock `sky/m5l2` needs visual review with the new daylight
  profile.
- Because the BSP requires `-notjunc`, inspect exterior, interior, transition,
  long-sightline, and map-edge views specifically for cracks.
- Six light leaves clamp 63-103 candidate entity lights down to 60; reduce
  fixture density if interiors appear flat or inconsistent.

## Artifact fingerprints

- MAP: 8,482,127 bytes; SHA-256
  `9966961E5C1D52B65D6BBB300699FF24E2EF3BDCBC6B4BB90619ABF8794DBEDC`
- conversion report: 26,102 bytes; SHA-256
  `FEEEABB1A44FAD14954317973378CBAF9B21A5AC0A6644438A4F5056F889122B`
- BSP: 32,125,316 bytes; SHA-256
  `653AEF5E9AE82FEA5FD68307CD67F1842E424DC611758875CB8EA779E16EE94C`
- PK3: 10,127,241 bytes; SHA-256
  `90477F688E4115400813B119A2061434A1F62324381B3CC864FA7BAB29084C53`
