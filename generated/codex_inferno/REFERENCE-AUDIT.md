# Inferno reference audit

The supplied/restored CS:GO files are private conversion and comparison
inputs. The VMF, BSP, logs, radar image, Valve textures, Valve models, and
embedded content are not included in the repository or PK3.

## Restored source set

| Source | Evidence |
| --- | --- |
| `de_inferno_d.vmf` | 20,869,971 bytes; SHA-256 `C37A3D3CB4EA813B0CC1B36205234A9F9CCFF258B7D69FBA8CA5C448628505D5` |
| `de_inferno.bsp` | 102,233,048 bytes; Source BSP version 21; SHA-256 `4C29B4B6AE35CE1DCA3F56439876014E09BAECDC25AD0146A865DA6072FC60E6` |
| `de_inferno_radar.dds` | SHA-256 `A91896C4C51E2F9379DCB6EC0DC778B429C798CD39F4A0D335A24A70B1F47948` |
| overview transform | `pos_x -2087`, `pos_y 3870`, `scale 4.9` |
| overview anchors | CT `(0.90,0.35)`, T `(0.10,0.67)`, A `(0.81,0.69)`, B `(0.49,0.22)` |
| `pak01_dir.vpk` | version 2; 133,676 indexed entries |
| BSP embedded pak | 78,122,090 bytes; 7,309 entries |

The semantic plan was compared against the official radar using its overview
transform. The route outline and T/A/B/CT placement align strongly; this is a
reference-comparison gate, not permission to ship radar pixels.

## Source measurements

| Measurement | Value |
| --- | ---: |
| World solids | 5,510 |
| Total reconstructed solids | 7,921 |
| Failed solid reconstructions | 0 |
| Total sides | 47,260 |
| Displacement sides | 2,223 |
| Entities | 9,934 |
| `prop_static` entities | 6,974 |
| `func_detail` entities | 2,252 |
| T / CT / dedicated-DM spawns | 20 / 20 / 67 |
| Light-related entities selected | 109 |
| A target bounds | `(1792,160,160)` to `(2160,708,200)` |
| B target bounds | `(144,2544,160)` to `(592,3008,224)` |

The measured spawn/play cluster is approximately X `-849..2656`, Y
`-768..3576`, Z `-16..272`. T is west, A southeast, CT east, and B north.

## Material and model resolution

The VMF contains 47,260 material references, 102 unique material names, and 82
unique visible materials. All 82 visible VMTs resolve through the restored
game data. The source contains 7,036 model references and 308 unique model
paths; all 308 resolve and parse. These results are audit evidence only. None
of those commercial assets is copied to the authored map.

Verified landmark model envelopes used to size original AA-native substitutes:

- B fountain basin radius about 156 units and height about 29;
- B fountain center radius about 43 units and height about 133;
- CT well base radius about 59 units and height about 40;
- CT well wood assembly about 104 x 147 x 141 units;
- large arch about 24 x 160 x 81 units;
- coffin about 19 x 43 x 100 units.

The audit found one genuine `prop_door_rotating` at Source origin
`(300.25,-324,96)`, yaw 270, speed 200, distance 90. Its model envelope is
approximately 8.6 x 55.5 x 111.6 units. Revision 4 uses those verified local
bounds and properties to translate one AA `func_rotatingdoor`. The exact PK3
loads with bot navigation and combat; human swing/clearance review remains
pending.

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

`inferno-layout-reference-audit.json` is the durable machine-readable
blueprint. Its SHA-256 is
`D5C30783387415C9C57CDB1608B07F8C04CC5DF4A460A8BD4ED3ADD5F8AFF8B0`.
`inferno-walk-grid-reference.svg` is its clean plan view.

## Revision 4 direct-conversion scope

After revisions 1-3 remained unrecognizable, the user explicitly authorized a
direct conversion from the original VMF. Revision 4:

- reconstructs and emits 5,533 playable Source brush solids;
- preserves world architecture and solids owned by `func_detail`,
  `func_brush`, and `func_breakable`;
- retains verified large/player clips while excluding 1,476 helper-only
  brushes;
- excludes 632 distant 3D-skybox brushes;
- planarizes 1,969 displacement-bearing sides for the first fidelity baseline;
- maps Source material roles to original project-owned Inferno textures;
- translates spawns, clustered light coordinates, and one verified rotating
  door;
- omits 6,200 unverified Source model props.

Geometry, coordinates, and topology are therefore derived directly from the
private VMF. The package still contains no Source texture, model, sound, radar,
VMF, VPK, BSP, or embedded-pak bytes. The original texture provenance is
documented separately in [`ART-PROVENANCE.md`](ART-PROVENANCE.md).

The older collision graph and radar transform remain useful independent
validators. They are no longer used to generate architecture.
