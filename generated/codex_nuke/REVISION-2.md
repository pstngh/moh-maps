# Nuke revision 2: screenshot-driven reconstruction and relight

Date: 2026-07-26

Status: compiled, full-lit, packaged, and exact-PK3 eight-bot tested

Revision 2 responds to the first 20-image human visual review of
`codex_nuke`. The user explicitly authorized filling missing decompile/model
areas with original geometry where needed. This revision therefore restores
measured industrial silhouettes rather than preserving obviously empty or
broken spaces.

The visual result still requires a new human screenshot pass. The technical
release gates in this document are proven; screenshot-specific appearance
claims remain targets until that pass is received.

## Review evidence

The review set was `shot0001.tga` through `shot0020.tga` supplied locally by
the user. The images are not redistributed in the repository.

| Evidence | Observed problem | Revision-2 response | Status |
| --- | --- | --- | --- |
| 0001, 0004, 0005 | Large industrial hall was dark, flat, and missing edge/ceiling structure | Reconstruct railing, pipe, duct, joist, ladder, and support families; cluster interior lights | Implemented; visual confirmation open |
| 0002, 0003 | Window openings rendered as black voids; adjacent office was overbright | Add original non-solid window-backing material; reduce glass opacity/blue cast; deduplicate lights | Implemented; visual confirmation open |
| 0006, 0007 | Doorway/detail region contained an implausible dark slab | Keep only four measured Source door entities functional; make cosmetic family fills nonblocking | Implemented; exact visible culprit still needs client correlation |
| 0008, 0017 | Open pits/catwalks lacked rail, ladder, and support assemblies | Reconstruct measured rail, ladder, joist, and catwalk-support envelopes as skeletal original brushwork | Implemented; visual confirmation open |
| 0009 | Glass office looked too blue and opaque | Lower original glass alpha and neutralize its color | Implemented; visual confirmation open |
| 0010-0012 | Corridors were bare; exposed openings showed the yellow sky | Use neutral gray-blue `sky/m5l2`; reconstruct bounded trim/fixture families; replace black placeholder surfaces | Implemented; visual confirmation open |
| 0013-0016, 0019, 0020 | Exterior was sparse; horizon and terrain edges exposed yellow/black gaps | Replace `mohday1`; expand each terrain underlay from measured displacement excursion; reconstruct fence, curb, pipe, and roof-trim families | Implemented; visual confirmation open |
| 0018 | Dark ceiling lacked readable industrial structure | Restore joist/duct silhouettes and rebalance fixture field | Implemented; visual confirmation open |

## Geometry reconstruction

The final deterministic generator emits:

- 7,755 world brushes and 329 entities;
- 5,639 retained Source solids;
- 604 planarized displacement faces;
- 632 material-matched terrain seam underlays;
- a maximum measured terrain-underlay expansion of 117 units;
- 642 measured ordinary prop brushes;
- 34 original hero-industrial brushes;
- four `func_rotatingdoor` entities;
- 16 Axis, 16 Allied, and 32 neutral DM spawns.

The 710 BSP-only Source autocombines are no longer treated as one undifferentiated
omission:

- 419 measured placements are reconstructed;
- 803 original, nonblocking detail brushes restore their useful silhouettes;
- 291 unsafe or ambiguous placements remain omitted;
- wires remain omitted deliberately.

Final family brush counts are:

| Family | Brushes |
| --- | ---: |
| Metal railing | 308 |
| Metal pipe | 149 |
| Metal ladder | 123 |
| Web joist | 66 |
| Curb | 54 |
| HVAC duct | 40 |
| Metal roof trim | 33 |
| Chain-link | 18 |
| Catwalk support | 12 |

Long family bounds preserve the principal run plus a small number of readable
sub-elements. They do not reproduce every Source post, rung, bend, or mesh
triangle. All reconstructed autocombine geometry is nonblocking because the
Source placements were predominantly cosmetic and the converted Source
brush/clip set remains the route authority.

## Window, glass, and material changes

- `tools/toolsblack`, `cs_italy/black`, and Source window-illumination
  placeholders now map to `codex_nuke/window_backing`.
- `window_backing.tga` is an original deterministic 512x512 blue-gray
  reflection field with a non-solid, non-lightmapped shader.
- Original glass alpha changed from 76 to 42 and its color was neutralized.
- Chain-link artwork is explicitly non-solid; measured Source clip volumes
  remain responsible for collision.
- The package now contains 15 original textures. No Valve texture, model, or
  shader asset is distributed.

## Lighting changes

World lighting changed from the revision-1 yellow-sky profile to:

```text
ambientlight 14 16 20
suncolor 132 128 118
sundirection 300 130 0
sundiffusecolor 76 84 100
sundiffuse 1.35
farplane 8000
farplane_color 0.34 0.39 0.46
sky/m5l2
```

The 471 Source point/spot fixtures are grouped into 128x128x96 cells and the
strongest fixture in each cell is retained. This produces 259 local lights,
removing 212 overlapping candidates.

Narrow cosmetic reconstruction is vertex-lit. The generated map contains
6,126 `+surfaceparm nolightmap` sides across railings, ladders, pipes, trim,
fixtures, and window dressings. Primary walls, floors, terrain, and doors keep
normal lightmaps.

## Rejected candidates and proven limits

### Dense family fill

The first family reconstruction emitted 8,314 brushes and 1,361 fill brushes.
Q3map exceeded a 3,604-second bound without returning a clean summary. That
candidate was rejected.

The accepted optimization keeps all 419 reconstructed placements but reduces
repeated intermediate rail posts, ladder rungs, and secondary cross-runs. It
emits 7,755 total brushes and 803 fill brushes.

**PROVEN:** preserving the family silhouette is affordable; reproducing every
repeated sub-element can make AA Q3map disproportionately expensive.

### Fixed lightmap budget

The first successfully compiled optimized BSP failed MOHlight immediately:

```text
MAX_MAP_LIGHTING exceeded from 180 lightmaps
```

Marking nonblocking cosmetic reconstruction as `nolightmap` preserved the
same 39,985 input and 36,976 output faces while allowing full MOHlight to
complete.

**PROVEN:** Source-model replacement detail must be assigned an explicit
lightmap policy. Narrow cosmetic brush families should default to vertex
lighting unless screenshots prove they require baked lightmaps.

## Deterministic source validation

Two consecutive generations produced byte-identical map and report outputs.
Static validation proves:

- balanced map braces;
- exactly one worldspawn;
- four rotating doors;
- 16 Axis, 16 Allied, and 32 neutral spawns;
- all 15 referenced custom images exist;
- all three required custom shaders exist;
- no raw Source material/model path appears;
- `419 reconstructed + 291 omitted + 0 skybox-skipped = 710` autocombines;
- 803 bounded family-fill brushes;
- terrain expansion remains at least 100 units;
- 259 retained lights are fewer than 471 candidates;
- at least 6,000 cosmetic sides remain outside the lightmap budget.

Fingerprints:

- MAP: 6,043,387 bytes, SHA-256
  `71AC5923FDA30A6D7E067FC625F4B6CC1F1C9267D44A50C153A3EA8541347369`
- conversion report: SHA-256
  `87E695A423854A376330C7CBD4A94C4970D9CEF950EDAE2B68494D028933231D`

## Compile and lighting evidence

The accepted source was compiled against retail Allied Assault data:

| Gate | Result |
| --- | --- |
| Q3map BSP | 39,985 input faces; 36,976 output faces; 3,009 removed; 2,886 seconds; empty stderr |
| Fast VIS | 154 clusters; 283 portals; 358 portal faces; 3,704 visibility bytes; 152 clusters visible on average |
| MOHlight 1.48 | 1,116 seconds; empty stderr; zero fatal errors |
| MOHlight diagnostics | 16 potential hash-mismatch warnings; 28 entity-light-list clamps |

The lit BSP is 25,315,896 bytes with SHA-256
`59BE0F7E9A2C5E8F173934A791C9521D4D9CDAEEFCB5DB827BE8A6914DCF5C12`.

The 16 potential-hash coordinates are non-fatal legacy-tool diagnostics. They
remain open visual-correlation debt. The light-list clamp count improved from
33 in revision 1 to 28, but further room-based light reduction may still be
useful after human review.

## Exact-package runtime evidence

The final PK3 contains 19 entries:

- one BSP;
- two map scripts;
- one shader script;
- 15 original TGA textures.

An isolated OpenMoHAA homepath contained only this exact PK3. OpenMoHAA
0.82.1-beta+5.a72bc15 loaded `dm/codex_nuke`, parsed and generated Recast
navigation in 14.754 seconds, admitted eight bots, and logged 60 combat events
with zero runtime errors before the test server was stopped.

The exact runtime-tested PK3 is 7,278,310 bytes with SHA-256
`A08EF1D4A109D2465249A116566D17CFF802B4EB0CC5214A42B6408826F632EF`.

This proves package loading, map initialization, navigation generation, bot
spawn, movement, combat, death, and respawn. It does not prove final visual
quality.

## Remaining debt

- Request a new human screenshot sweep using this exact PK3.
- Verify the four door panels visually: placement, activation, swing direction,
  and clearance.
- Correlate the 16 MOHlight hash-warning coordinates with visible surfaces.
- Inspect the 28 clamped entity-light leaves and reduce lights only where the
  new visual pass still shows flattening or overexposure.
- Keep the 291 ambiguous autocombines and wires omitted until a screenshot,
  verified mesh, or route requirement justifies a bounded template.
- Curved Source terrain and the distant 3D skybox remain intentionally out of
  scope for this revision.

## Release checklist

- [x] User screenshots cataloged by defect class.
- [x] Missing-family fill policy authorized and applied.
- [x] Deterministic generation proven.
- [x] Static validation passed.
- [x] Q3map BSP completed cleanly.
- [x] Fast VIS completed cleanly.
- [x] Full MOHlight completed after fixing the lightmap budget.
- [x] Exact final PK3 contents and hashes verified.
- [x] Exact final PK3 passed eight-bot OpenMoHAA QA.
- [ ] Human visual review of revision 2.
- [ ] Human door interaction review.
