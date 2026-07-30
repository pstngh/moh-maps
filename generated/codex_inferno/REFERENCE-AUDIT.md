# Inferno reference audit

The local CS:GO files are measurement and visual-role references only. The
VMF, BSP, Valve textures, and Valve models are not repository or PK3 content.

## Files inspected

| File | Size | Use |
| --- | ---: | --- |
| `de_inferno_d.vmf` | 20,869,971 bytes | Counts, spawn distribution, material roles, route scale |
| `de_inferno.bsp` | 102,233,048 bytes | Confirms the decompile's source identity |
| `de_inferno_d.log` | 888 bytes | BSPSource record |

## Source complexity

| Measurement | Value |
| --- | ---: |
| World solids | 5,510 |
| Total solids | 7,921 |
| Sides | 47,260 |
| Displacement sides | 2,223 |
| Entities | 9,934 |
| `func_detail` entities | 2,252 |
| Static props | 6,974 |
| Terrorist spawns | 20 |
| Counter-Terrorist spawns | 20 |
| Dedicated deathmatch spawns | 67 |
| Point/spot lights | 75 |

The decompile spans `(-8208 -11072 -464)` to `(13680 9232 3280)`, including
non-playable and skybox construction. Dedicated deathmatch origins occupy a
much narrower playable cluster, roughly X `-849..2656`, Y `-768..3576`, and Z
`-16..272`.

## Why a direct conversion is rejected

The visible Source result depends heavily on content outside ordinary brushes:

- 2,223 displacement sides;
- 6,974 static-prop placements;
- repeated roof caps, flowers, wood supports, stone/concrete trim, windows,
  gutters, shutters, pillars, railings, and foliage models;
- high-resolution blended plaster, brick, cobble, roof, wood, and terrain
  materials.

Importing the brushes while omitting those dependencies would reproduce the
failure mode seen in earlier dense conversions: structurally compilable but
visually incomplete streets, facades, roofs, and boundaries. Revision 1 uses
none of the Source solids. The reference instead informs:

- the two-team plus dedicated-DM spawn scale;
- the connected Mid/Alt Mid/Apartments/A and Banana/B/CT route graph;
- the importance of plaster facades, terracotta roofs, cobble streets, arches,
  shutters, a fountain, and a bell-tower silhouette;
- restrained exterior vertical range suitable for AA movement.

## Legal/content boundary

No source-game image, mesh, sound, VMF, BSP, or embedded file is copied into
the generated map. New art is original project-owned material, and the stock
sky reference resolves from the player's retail AA installation.
