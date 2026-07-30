# Codex Inferno revision 4

Date: 2026-07-30

Status: **direct-VMF playable candidate; technical gates pass; human visual
recognition review pending**

## Why the construction method changed

The user's screenshots `shot0022.tga` through `shot0038.tga` rejected revision
3 as completely unrecognizable. Repeated roof slabs, narrow trench-like
routes, blank masses, and an almost uniform roof field showed that procedural
dilation and greedy village massing had erased Inferno's architecture. Adding
facades, props, or textures could not repair that root cause.

The user then explicitly authorized direct conversion from the original VMF.
Revision 4 discards the rendered geometry of revisions 1-3. Their graph, radar,
and audit artifacts remain validators and historical evidence only.

## Direct conversion policy

The generator parses the private VMF, reconstructs convex solids from their
brush planes, filters the playable cluster, maps Source material roles to the
original Inferno texture palette, and emits target-engine brushes.

| Conversion result | Count |
| --- | ---: |
| Output world brushes | 5,696 |
| Directly converted Source solids | 5,533 |
| Invalid reconstructed solids | 0 |
| Helper-only brushes excluded | 1,476 |
| Distant 3D-skybox brushes excluded | 632 |
| Displacement-bearing sides planarized | 1,969 |
| Unverified Source model props omitted | 6,200 |
| Playable light candidates / emitted lights | 75 / 55 |
| Rotating doors translated | 1 |
| Axis / Allied / neutral spawns | 20 / 20 / 67 |
| Total entities | 165 |

Playable architectural solids from worldspawn, `func_detail`, `func_brush`, and
`func_breakable` are retained. Imported internal brushes are placed in
worldspawn with MOHAA `+surfaceparm detail`, while a six-brush structural sky
shell controls portals. The playable filter is X `-2400..3200`, Y
`-1350..4200`, Z `-320..960`; the distant Source skybox cluster is excluded.

The one real Source rotating door uses its verified approximately
8.6 x 55.5 x 111.6-unit local envelope, 90-degree travel, and speed 200 to
produce an AA `func_rotatingdoor`. Door swing and bot clearance still require
human playtest review.

No Source texture, model, sound, radar, VMF, BSP, VPK, or embedded-pak bytes
are packaged. Thirteen original Inferno material roles are used in the emitted
map. A clean temporary regeneration reproduced the MAP, both scripts, and the
machine-independent conversion report byte-for-byte.

## Compiler evidence

An ordinary Q3map run was manually stopped after more than five CPU minutes
without an error. Because the fully direct brush set is intentionally being
preserved for the recognition gate, the documented `-notjunc` fallback was
used rather than deleting architecture.

- Q3map `-notjunc`: 24,633 faces from 28,310 inputs, 3,677 removed (13.0%),
  1,910 seconds, no invalid brush, leak, or stderr error;
- fast VIS: 49 clusters, 400 visibility bytes, 49 clusters visible on average;
- full MOHlight: 222 seconds and zero stderr output;
- Q3map `-info`: 2 models, 21 shaders, 5,540 brushes, 39,090 brush sides,
  14,158 planes, 165 entities, 174 nodes, 177 leafs, 99,799 draw vertices,
  149,415 draw indexes, 24,639 draw surfaces, and 82 lightmaps;
- BSP budget display: 12.34 MB of a nominal 10.00 MB.

MOHlight reported two nonfatal potential-hash-mismatch warnings at:

- `(1514.77 171.202 116)` to `(1845.23 171.202 116)`;
- `(2794.08 1914.22 116)` to `(2548.05 1915.19 116)`.

The over-budget display and `-notjunc` use are explicit optimization/seam debt.
The compiler emitted a valid BSP, so geometry will not be reduced until the
user confirms which architecture is visually correct.

## Exact-package OpenMoHAA evidence

The final 19-entry PK3 was loaded in an isolated OpenMoHAA 0.82.1 home backed
by retail Pak0-Pak6. The engine:

- parsed the BSP in 0.097 seconds;
- generated Recast navigation in 3.858 seconds;
- admitted all eight requested bots;
- logged 23 combat/death events in the recorded sample;
- reported zero fatal runtime map errors.

The test server launched solely for validation was stopped afterward.

## Artifact fingerprints

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 4,092,209 | `2B68A264448F674DEE2F852FE99834A0EEBB0748FEBA38DD819002C7C213FB2E` |
| BSP | 14,221,508 | `6B984142E4C687EBC031C035E400619345CDA1FEBE08D06541EC0427196C46D2` |
| PK3 | 7,045,046 | `6F1F9A5568D5C2C2873E8424D6AFF4CAE52F02A1EFD61556778315E7CB6AA441` |

The private VMF is 20,869,971 bytes with SHA-256
`C37A3D3CB4EA813B0CC1B36205234A9F9CCFF258B7D69FBA8CA5C448628505D5`.

## Acceptance state

Technical gates pass. Recognition does not yet pass because this revision has
not received the user's screenshot verdict. The required views are T spawn,
Mid, Apartments, A, CT, Banana, B, and a high overview.

If recognition passes, repair visible planar displacement, omitted-prop,
material, lighting, door, and T-junction seam issues in that order of observed
impact. If a location still fails recognition, inspect its source brush/entity
class and conversion filter before inventing replacement geometry.
