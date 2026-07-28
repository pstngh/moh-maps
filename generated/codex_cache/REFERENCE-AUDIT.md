# Cache reference audit

Date: 2026-07-27

This audit records derived facts used to create `codex_cache`. The local
decompiled VMF, Source BSP, embedded pak, and Valve assets are not distributed.

## Source inventory

- BSPSource VMF: 45,755,859 bytes
- Source BSP version: 21
- Source BSP size: 486,323,964 bytes
- world solids: 13,227
- total solids: 16,508
- total sides: 99,612
- displacement sides: 10,952
- entities: 7,643
- unique brush materials: 154
- static-prop placements: 4,113
- total ordinary prop placements: 4,170
- unique prop models: 647
- ordinary lights: 191
- spot lights: 76
- `func_detail`: 2,575
- `func_breakable`: 149
- `func_brush`: 52

The Source BSP contains a 446,865,276-byte embedded pak with 6,963 entries.
It was inspected locally to derive facts only.

## Playable-cluster boundary

The real multiplayer space is centered near Source Z 1,600-2,300. Separate
distant construction and 3D-skybox clusters extend to Y -13,700 and include a
sky camera at `-9364 3627 2483`.

The generator accepts brush centers and gameplay entities only inside:

```text
-3000 < X < 4000
-2500 < Y < 3000
 1300 < Z < 2800
```

The structural AA sky shell is slightly larger so complete retained brushes,
not just their centers, remain enclosed:

```text
min -3072 -2688 1280
max  4800  3200 3456
```

Revision 1 excludes 3,800 brush solids outside the playable filter.

## Spawn evidence

- 20 Terrorist spawns become `info_player_axis`.
- 20 Counter-Terrorist spawns become `info_player_allied`.
- 24 dedicated deathmatch spawns become `info_player_deathmatch`.
- The first dedicated deathmatch spawn also supplies `info_player_start`.

The dedicated DM positions are preserved rather than manufacturing neutral
spawns by duplicating both teams.

## Door evidence

Cache contains one real `prop_door_rotating`:

```text
origin 199 2058 1688
angles 0 180 0
model models/newcache/nc_bluedoor/nc_bluedoor.mdl
distance 90
forceclosed 1
```

The embedded MDL is an IDST version-49 file. Its studio hull is:

```text
hullMin -56.2491 -3.8992 -0.2552
hullMax   0.2491  3.8992 110.25
```

Revision 1 uses those exact hull bounds and the Source pivot to create one AA
`func_rotatingdoor`. No other model name is treated as proof of a door.

## Prop policy

Cache has no `autocombine` placements, but it does have thousands of ordinary
Source-only props. A model filename and aggregate hull do not prove internal
mesh topology, orientation, or useful collision.

Revision 1 omits all 2,588 unverified prop placements inside the playable
filter. It deliberately does not generate bounding-box crates, railings,
foliage, awnings, pipes, or architectural fill. Later revisions may restore a
family only from actual mesh topology, a verified simple measured hull, or a
coordinate-specific manual reconstruction.

## Geometry and lighting policy

- Preserve measured playable world, `func_detail`, `func_brush`, and
  `func_breakable` solids.
- Treat imported geometry as detail inside an explicit six-brush structural
  shell to protect the AA visibility compiler.
- Keep Source displacement backing brushes planar in the baseline.
- Add material-matched seam underlays only beneath traversable displacement
  families.
- Retain measured large Source clip volumes; omit small helper-only brushes.
- Cluster playable Source fixtures in 128×128×96 cells and retain the
  strongest candidate per cell.
- Use an original clean-industrial material palette and stock AA sky/utility
  shaders. Do not package Valve art.
