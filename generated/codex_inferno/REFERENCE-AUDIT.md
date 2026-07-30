# Inferno reference audit

The supplied `de_inferno_d.vmf` is a private measurement/reference input. The
VMF, BSP, log, Valve textures, Valve models, and embedded content are not
included in the repository or PK3.

## Source measurements

| Measurement | Value |
| --- | ---: |
| VMF bytes | 20,869,971 |
| World solids | 5,510 |
| Total reconstructed solids | 7,921 |
| Failed solid reconstructions | 0 |
| Floor-like faces | 2,654 |
| Entities | 9,934 |
| Static props in reference | 6,974 |
| T / CT / dedicated-DM spawns | 20 / 20 / 67 |
| A target bounds | `(1792,160,160)` to `(2160,708,200)` |
| B target bounds | `(144,2544,160)` to `(592,3008,224)` |

The measured spawn/play cluster is approximately X `-849..2656`, Y
`-768..3576`, Z `-16..272`. T is west, A southeast, CT east, and B north.

## Collision-aware blueprint

The audit does not treat every horizontal Source face as playable. It:

- intersects brush planes to recover convex solids;
- buckets collision volumes spatially;
- samples 32-unit floor nodes;
- rejects nodes without player-sized headroom;
- rejects neighbor transitions cut by a collision plane;
- seeds traversal from all team and DM spawns;
- retains only spawn-connected nodes and edges.

| Grid evidence | Value |
| --- | ---: |
| Candidate XY cells | 12,485 |
| Candidate nodes | 13,372 |
| Rejected headroom nodes | 5,397 |
| Collision buckets | 2,602 |
| Seed nodes | 107 |
| Connected nodes | 6,997 |
| Connected edges | 13,420 |
| Unmatched spawns | 0 |

`inferno-layout-reference-audit.json` is the durable machine-readable blueprint.
`inferno-walk-grid-reference.svg` is its clean plan view.

## What is and is not copied

Copied as measurements:

- route coordinates and connectivity;
- floor elevations and source material roles;
- spawn and bomb-target positions;
- selected landmark origins such as the B fountain and coffins.

Not copied:

- Source brushes as output brushes;
- displacements;
- textures, materials, models, sounds, or embedded files;
- prop meshes or Valve-authored raster art.

Revision 2 builds new axis-aligned MOHAA floor/facade masses and original
project-owned textures from those measurements. This produces a recognizable
clone without repeating the incomplete raw-conversion failure mode.
