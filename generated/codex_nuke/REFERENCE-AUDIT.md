# Nuke reference audit

Status: **OBSERVED preproduction evidence**

Date: 2026-07-26

## Reference health

The supplied BSPSource 1.4.8 log identifies a CS:GO BSP version 21 file and
reports a clean completion:

- 8,228 exact brush-side/original-face matches (17.5%);
- 837 partial matches (1.8%);
- all 761 displacement original faces retained;
- no logged decompile error.

This is usable source evidence, but a decompiled VMF is not the complete
rendered map. Nuke relies heavily on model geometry.

## Measured source

| Measurement | Value |
| --- | ---: |
| VMF bytes | 19,262,971 |
| World solids | 5,282 |
| Total solids | 8,039 |
| Sides | 48,098 |
| Displacement sides | 761 |
| Entities | 10,488 |
| `func_detail` entities | 2,567 |
| `func_brush` entities | 94 |
| Static props | 6,891 |
| Unique referenced models | 1,405 |
| `light` entities | 249 |
| `light_spot` entities | 222 |
| T spawns | 16 |
| CT spawns | 16 |
| Rotating doors | 4 |
| Visible material references | 17,761 |
| Unique visible materials | 121 |

World plane/vertex bounds are `[-6240, -5408, -6400]` through
`[6560, 12360, 3456]`. Team spawns occupy a compact band from
`[-2134, -1160, -400.634]` through `[2704, -336, -335]`.

The solid-center histogram has 6,929 solids between Y -3,072 and 1,023, then
separate clusters containing 900 solids between Y 7,168 and 12,360. The
spawn-expanded preliminary playable envelope intersects 7,010 solids and
excludes 1,029 outliers. This is a classifier candidate, not yet a proof that
every excluded solid is skybox-only; final import must inspect boundary cases.

The Source `sky_camera` is at `-56 -500 -6192` with scale 16. The distant
cluster and sky camera must be interpreted together rather than using one
hard-coded coordinate from an earlier map.

## Local archive resolution

The local Source 1 VPK is version 2 and contains 133,676 directory entries.
All 121 visible VMF materials resolve to VMT files. The audit reads VMT text
and VTF headers to record shader role, dependency path, and source resolution;
it does not export the textures.

The Nuke BSP contains a 254,024,965-byte embedded ZIP pak with 9,307 entries.
Model resolution is exact:

| Model source | Unique MDLs resolved |
| --- | ---: |
| Ordinary `pak01` entries | 695 |
| BSP-embedded `autocombine` entries | 710 |
| Total | 1,405 / 1,405 |

All 1,405 studio headers parse. Their local hull/view bounds establish only
scale and orientation envelopes. They do not prove a mesh's internal shape,
principal run, sub-element count, or placement inside the aggregate box.

The embedded autocombines are essential reference evidence. They are generated
map assets, not reusable public-package content. A VMF-only port that ignores
them will omit parts of ventilation systems, façades, roof assemblies, trim,
and other industrial silhouettes.

Revision 2 attempted bounded original templates for 419 placements using model
name, aggregate hull bounds, placement, orientation, and repeated role. The
next 13-image human review rejected that result: 803 generated brushes became
giant floating bars, crossed beams, false ladders, and arbitrary frames.
Revision 3 therefore omits all 710 autocombine placements. A family becomes
eligible only when actual mesh topology, verified per-instance endpoints, or a
manually authored reference reconstruction proves its internal arrangement.

Revision 4 separately inventories 4,687 model entities inside the playable
envelope in `fidelity-manifest.json`. It restores 1,932 ordinary instances
using family-specific original brush templates at measured transforms while
leaving all 710 autocombines untouched. Ordinary model identity plus measured
bounds can establish conservative family silhouettes; it still cannot prove
the topology of a combined model.

This establishes the conversion policy:

- never infer a principal axis or internal run from an aggregate hull;
- use a hull only as an outer rejection/containment check after topology is
  established independently;
- keep uncertain model substitutes nonblocking and retain Source clips as
  collision authority;
- cap repeated posts, rungs, and cross-runs for the legacy compiler;
- choose baked versus vertex lighting per proven material/template and confirm
  it visually in engine;
- keep any family without sufficient evidence explicitly omitted.

## Dominant material roles

The top visible material references are:

| Source role | References | Representative source resolution | Original target |
| --- | ---: | ---: | --- |
| Light concrete wall | 2,596 | 1024² | `codex_nuke/painted_concrete` |
| Blue/gray corrugated metal | 1,869 combined | 1024² / 1024×256 | `codex_nuke/corrugated_blue` or `_gray` |
| Metal trim | 1,636 combined | 1024×128 | `codex_nuke/metal_trim` |
| Concrete wall variant | 914 | 1024² | painted or dark concrete, by area |
| Asphalt/blends | 1,191 combined | 1024² | `codex_nuke/asphalt` |
| Concrete floor/stair | 1,977 combined | 512² / 1024² | `codex_nuke/concrete_floor` |
| Concrete trim | 708 | 256×64 | concrete or metal trim |
| Chain-link card | 277 | 1024×512 | `codex_nuke/chainlink` plus solid clip |
| Window/frame glass | 260 | 256×128 | `codex_nuke/glass` plus brush frame |
| Ground/grass/mulch blends | 1,032+ | 1024² | `codex_nuke/grass` or `codex_nuke/gravel` |
| Ceiling tile | 164 | source 1024-class | `codex_nuke/ceiling_tile` |
| Metal grating | 160+ | source role | `codex_nuke/metal_grating` |

The 121 source materials should not become 121 new assets. They reduce to a
small functional palette with controlled variants. Source blend shaders must
be resolved by surface role because MOHAA does not reproduce Source vertex
transition materials directly.

## Dominant prop families

Repeated Source props identify the minimum silhouette kit:

- 160 railing segments;
- 151 fluorescent fixtures plus 108 attachments and 65 cables;
- 120 roof-trim segments;
- 70 straight pipes plus many bends, supports, and end caps;
- 67 bell fixtures;
- 67 roof AC units and 62 small fans;
- 48 chain-link panels;
- 47 metal door frames;
- 45 exterior vent panels;
- 45 recessed 32×32 fixtures;
- 41 concrete barriers;
- 30+ curb segments and multiple window families.

First-playable priority is:

1. **Route/containment:** walls, floors, stairs, doors, frames, windows,
   railings, fences, barriers, and clips.
2. **Recognition:** roof trim, large ducts/vents, pipes, AC units, joists, and
   major exterior equipment.
3. **Lighting cues:** fluorescent/recessed/bell fixtures paired with real AA
   lights.
4. **Cosmetic omission:** outlets, wires, extinguisher details, rubbish,
   signs, decals, and small clutter until release gates are otherwise satisfied.
   Measured furniture and original non-solid foliage cards are eligible when
   their target-engine representation is conservative and auditable.

The user also permits filling visually missing areas with original geometry.
That permission does not authorize arbitrary route changes: additions should
restore enclosure, safety edges, supports, and silhouette first; new solid
cover or blockers still require source collision evidence and bot testing.

The user explicitly does not require graffiti, warning signs, or similar
surface storytelling. Excluding them improves clarity and avoids needless
source-art imitation.

## Doors

The VMF includes four `prop_door_rotating` entities using the same metal-door
family:

- paired doors at `1047 -1040 -768` and `1047 -920 -768`;
- one door at `305 -1350 -767.99`;
- one door at `257 -1310 -416`.

All specify a 89-degree swing and speed 200. Two are source-forced closed; the
paired set uses a slave relationship. The AA conversion must make an explicit
choice per door:

- measured interactive rotating door with swing clearance and bot test; or
- intentionally open/static doorway for flow.

Silently placing a nonfunctional closed panel is not acceptable.

## Lighting evidence

Source outdoor lighting is a useful color-direction reference, not an
intensity copy:

- direct light: `255 240 206`, azimuth 26°, pitch -60°;
- ambient light: `101 139 182`;
- sun sprite color: `255 238 170`.

This supports the established warm-direct/cool-fill approach. Source
intensities do not transfer numerically to MOHlight. Interior fixtures should
be retained selectively and translated to restrained AA light values, with
darkness used only where spatially intended—not to conceal missing geometry.

## Provenance rule

Valve VMF, VMT, VTF, MDL, VTX, VVD, BSP pak, sounds, and other game files stay
outside the repository and final PK3. They may be read locally to derive
factual measurements and visual roles. Public output contains:

- newly generated map geometry and scripts;
- original bundled diffuse/alpha art;
- stock MOHAA shader/model references;
- factual manifests and reproducible analysis tools.

This allows a clean/source-like visual direction without redistributing the
original Nuke asset set.
