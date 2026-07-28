# Nuke revision 3: visual-regression recovery

Date: 2026-07-27

Status: compiled, full-lit, packaged, and exact-PK3 eight-bot tested; human
visual confirmation pending

Revision 3 responds to the user's 13-image review of revision 2
(`shot0000.tga` through `shot0012.tga`). The review showed that a technically
valid map can still be visually unacceptable. This build removes the entire
unsafe geometry class instead of adding more speculative fill.

## Screenshot findings

The images remain local and are not redistributed.

| Evidence | Observed result | Diagnosis | Revision-3 response |
| --- | --- | --- | --- |
| 0000-0005 | Long white floating bars, rail-like runs, poles, frames, and lattice clutter across the exterior | Aggregate autocombine hulls were mistaken for internal model topology | Remove every autocombine-derived fill |
| 0006-0007 | Reactor hall contained false rails, beams, and floating ladder pieces | Filename plus AABB did not prove local axes, offsets, or connectivity | Remove rail/ladder/support templates and restore ordinary measured-prop conversion |
| 0008-0011 | Interior rooms and passages were crossed by bright beams at arbitrary heights and directions | Principal-run inference populated empty portions of combined hulls | Remove all planar-run inference |
| 0000-0011 | Invalid detail rendered unusually white/bright | Broad `surfaceparm nolightmap` made bad geometry visually dominant | Restore normal baked lighting; validator forbids broad override |
| 0000-0005, 0012 | Exterior terrain still shows black cracks/gaps in places | Measured underlays improved but did not fully solve planar displacement boundaries | Keep measured underlays; leave coordinate-level repair open rather than add a broad floor |
| 0000-0012 | Gray sky removes the earlier yellow lower horizon but remains flat/dull | `sky/m5l2` is a provisional stock compromise | Retain provisionally; record custom/alternate sky as open art work |
| mixed | Window backing/glass and some object grounding appear improved | These changes do not depend on aggregate-hull reconstruction | Preserve pending closer review |

## Root cause and corrected rule

An embedded Source autocombine MDL may contain many separated meshes. Its
studio hull is the union envelope around them. The hull proves only an outer
bound; it does not prove:

- which axis contains a run;
- whether both axes contain geometry;
- where geometry sits inside the hull;
- how many pieces exist;
- or how pieces connect.

Revision 2 generated 803 brushes across 419 placements from those unsupported
assumptions. Compilation, lighting, navigation, and bot combat all passed, but
the human screenshots rejected the result.

Revision 3 sets a hard gate: all 710 autocombines stay omitted until actual
mesh topology, verified endpoints, or a manually authored coordinate-specific
reference proves their shape. The hull may then be used only as a containment
check.

## Geometry and generator changes

The deterministic generator now emits:

- 6,949 world brushes and 329 entities;
- 5,639 retained Source solids;
- 604 planarized displacement faces;
- 632 material-matched terrain seam underlays, expanded by measured
  displacement excursion up to 117 units;
- 638 measured ordinary prop brushes;
- 34 original hero-industrial brushes;
- four `func_rotatingdoor` entities;
- 16 Axis, 16 Allied, and 32 neutral DM spawns;
- zero autocombine fill brushes;
- zero `surfaceparm nolightmap` sides.

The removed revision-2 output was:

- 419 inferred placements;
- 803 autocombine fill brushes;
- three smaller ordinary-prop special run substitutions;
- 6,126 non-lightmapped sides.

The validator now fails if any autocombine reconstruction, autocombine fill
brush, or broad `nolightmap` side returns.

## Preserved independent changes

Revision 3 intentionally keeps:

- original `codex_nuke/window_backing` mapping for former black window
  placeholders;
- reduced and neutralized original glass alpha;
- the 15-texture original clean-industrial palette;
- source-measured displacement-underlay expansion;
- clustering of 471 Source fixture candidates to 259 retained lights;
- four generated rotating doors;
- provisional `sky/m5l2` and its neutral daylight profile.

These items do not depend on the rejected topology inference. Their final
appearance still requires human confirmation.

## Deterministic source validation

Static validation passes with:

- balanced map braces and one worldspawn;
- four rotating doors;
- 16 Axis, 16 Allied, and 32 neutral spawns;
- all 15 custom images and all required shaders present;
- no raw Source asset path;
- 710 omitted, zero reconstructed, zero skybox-skipped autocombines;
- zero autocombine fill brushes;
- zero `surfaceparm nolightmap` sides;
- maximum measured terrain-underlay expansion of 117 units;
- 259 retained lights from 471 candidates.

Fingerprints:

- MAP: 5,218,048 bytes, SHA-256
  `9C9EAB05034C35600547F805348D0C71C1A903A5D527E3776D5AB301417838F4`
- conversion report: 18,493 bytes, SHA-256
  `2D8BED5E161AC541F00C9F4877744C5CB44F0FD310B60C11946BCA836A17F7B6`

## Compile and lighting evidence

The source was compiled against retail Allied Assault data:

| Gate | Result |
| --- | --- |
| Q3map BSP | 35,149 input faces; 32,140 output faces; 3,009 removed; 2,077 seconds; empty stderr |
| Fast VIS | 154 clusters; 283 portals; 3,704 visibility bytes; 152 clusters visible on average; 1 second; empty stderr |
| MOHlight 1.48 | 1,083 seconds; empty stderr; zero fatal errors |
| MOHlight diagnostics | 16 potential hash-mismatch warnings; 28 entity-light-list clamps |

The normal-lightmapped build fits the legacy lightmap budget after the invalid
fills are removed. This supersedes revision 2's broad vertex-light workaround.

The lit BSP is 23,494,100 bytes with SHA-256
`F79BF2BDA45CA188A09A2C3D63646E3BEAD8CC1D43D4975685C7E5881B51ED97`.

## Exact-package runtime evidence

The 19-entry PK3 contains one BSP, two map scripts, one shader script, and 15
original TGA textures. An isolated OpenMoHAA homepath contained only this exact
PK3. OpenMoHAA 0.82.1-beta+5.a72bc15:

- loaded `dm/codex_nuke` from that package;
- parsed the BSP and generated Recast navigation in 9.515 seconds;
- admitted all eight configured bots;
- logged 119 combat events during a two-minute run;
- emitted zero engine/map/script error matches.

The tested PK3 is 7,093,663 bytes with SHA-256
`4790A691A592DAA7B6D35DD5BD658E02760EB994EC691152F8601D84D7FFCF63`.

This proves package loading, initialization, navigation, bot spawn, movement,
combat, death, and respawn. It does not prove final visual quality.

## Remaining debt

- Request a new screenshot sweep using this exact revision-3 PK3.
- Verify the four door panels in a human client: alignment, activation, swing
  direction, and clearance.
- Repair remaining exterior terrain cracks only from coordinate-level
  screenshot/source correlation.
- Replace or tune the flat provisional sky after the geometry recovery is
  visually confirmed.
- Correlate the 16 MOHlight hash-warning coordinates with visible surfaces.
- Inspect the 28 clamped entity-light leaves if interiors remain flat or
  overexposed.
- Keep all 710 autocombines and wires omitted until independent topology
  evidence exists.
- Curved Source terrain and the distant 3D skybox remain out of scope.

## Release checklist

- [x] Thirteen revision-2 screenshots cataloged by defect class.
- [x] Unsafe geometry rule isolated and removed.
- [x] Shared knowledge corrected.
- [x] Static validation passed.
- [x] Q3map BSP completed cleanly.
- [x] Fast VIS completed cleanly.
- [x] Full MOHlight completed with normal lightmaps.
- [x] Exact final PK3 contents and hashes verified.
- [x] Exact final PK3 passed eight-bot OpenMoHAA QA.
- [ ] Human visual review of revision 3.
- [ ] Human door interaction review.
