# Cobblestone revision 3 report

Status: validated and packaged

Date: 2026-07-26

## Identity

- Map: `codex_cobblestone`
- Target: Allied Assault BSP 19 and OpenMoHAA
- Modes: DM/TDM
- Baseline: revision 2, commit `638ecd9`
- Reference: legally obtained `de_cbble_reference.vmf`, not redistributed

## User evidence

The input set contains 19 1920x1080 screenshots, `shot0000.tga` through
`shot0018.tga`. They cover high exterior views, courtyards, roofs, repeated
castle modules, façades, displacement edges, and bots in live play.

### Defect matrix

| Screenshots | Visible symptom | Cause classification |
| --- | --- | --- |
| 0002-0004, 0007-0012, 0016 | Repeated floating U shapes, ribs, towers, and malformed arcades | **PROVEN:** generic three-brush replacements for Source `arch_*`, `port_*`, and `port_sect_*` models |
| 0000-0001, 0005-0006, 0013-0015, 0017 | Floating or offset shutters, doors, narrow black rectangles, and pillars | **PROVEN:** guessed façade-panel/model dimensions and origin conventions |
| 0000, 0009-0010, 0018 | Bright triangular floor holes, open bridge/support sides, and exposed map-edge strips | **OBSERVED:** Source nodraw support faces remain caulk when their Source displacement/model cover is unavailable |
| 0000, 0007, 0011 | Ground cover, foliage, or terrain appears detached at displacement edges | **OBSERVED:** retained props use the sculpted Source height while the playable conversion uses planar backing surfaces |
| 0013-0015 | Bright plaster-like vertical strips dominate stone façades | **PROVEN:** `de_cbble/outwall02` and `de_cbble/trimwall01` reached the generic bright-plaster fallback |

## Shared causes

Revision 2 correctly restored missing brush architecture, but it also retained
two unsafe revision-1 assumptions:

1. 299 Source architectural model instances were replaced without real model
   bounds, meshes, pivot conventions, or per-model measurements.
2. Mixed-material Source brushes preserved `tools/toolsnodraw` as AA caulk
   even when the missing Source cover made that support face visible.

The screenshots prove that widening one generic placeholder cannot repair
multiple model families. A clean omission is preferable to conspicuous,
incorrect geometry until real model bounds or a measured per-family
reconstruction exists.

## Revision-3 candidate

- omit all 299 unmeasured architectural placeholders by default;
- retain the old behavior only behind
  `--legacy-architectural-placeholders` for controlled comparisons;
- use each mixed brush's own visible material on exposed nodraw support faces;
- omit cobweb surfaces and translate Source glass to stock
  `mohcommon/window5`;
- find planar backing quads for Source displacements and ground retained cover
  and foliage by at most 64 units;
- retain all 4,653 converted brush solids and the structural sky shell.

Initial generation measurements:

- 4,782 generated brushes;
- 5,682 nodraw faces assigned a material-matched fallback;
- 299 unsafe architectural props omitted;
- 448 usable planar displacement support surfaces;
- 117 retained prop origins adjusted, with a maximum 63.999-unit correction;
- 123 generated cover brushes and 74 stock vegetation entities;
- 44 neutral, 22 Axis, and 22 Allied spawns.

## Validation

### Structural candidate

The first candidate passed all three compile stages:

- Q3map: 1,061 seconds, 28,947 input faces, 27,079 output faces, no warning
  matches, 12,840,080-byte unlit BSP;
- fast VIS: 90 clusters, 161 portals, 1,448 visibility bytes;
- full MOHlight: 431 seconds and a 19,726,656-byte lit BSP.

Its isolated three-entry PK3 had SHA-256
`2315CE5DAC34B0495F05C4CBB71397DB25D7EC0171F5A88E828DE170E1E968D1`.
OpenMoHAA 0.82.1 loaded that exact file, built Recast navigation in 5.098
seconds, created eight bots, and recorded multiple kills.

Eight bot-follow screenshots and ten fixed-camera architectural screenshots
confirmed:

- the repeated U-frame/rib fields are gone;
- floating shutters, doors, and black façade rectangles are gone;
- tested courtyard and transition floor cuts are closed;
- cover and vegetation remain grounded in the tested routes;
- interiors, roofs, arches, and stock daylight still render coherently.

The fixed-camera set also proved the material issue: pale vertical strips
remained where `de_cbble/outwall02` and `de_cbble/trimwall01` reached the
generic plaster fallback. The final build maps only those two source families
to the established stock stone material.

### Final build

- Q3map: 1,056 seconds, 28,947 input faces, 27,062 output faces, no warning
  or error matches, and a 12,829,772-byte unlit BSP;
- fast VIS: 90 clusters, 161 portals, and 1,448 visibility bytes;
- full MOHlight: 449 seconds, empty stderr, a 19,716,348-byte lit BSP, and
  only two benign per-leaf light clamps;
- package: exactly three forward-slash entries: BSP, map script, and precache
  script.

Regenerating from the reference VMF into a separate output directory produced
a byte-identical `.map` with SHA-256
`67FE961857CBA827E93D5327C11455AE591F94A08B566F36969F7B6087770171`.

OpenMoHAA 0.82.1 loaded the exact final PK3, generated Recast navigation in
4.971 seconds, created eight bots, and recorded seven kills during the
scripted run. The packaged and tested PK3 hashes matched exactly. Eight
bot-follow views and ten fixed-camera views confirmed:

- the final stone mapping removes the pale facade strips;
- the repeated U frames, ribs, floating shutters, doors, and black panels do
  not return;
- the sampled courtyard, corridor, roof, and transition surfaces remain
  coherent;
- bots render, move, fight, and use both exterior and interior routes.

Known fidelity debt remains explicit: Source displacements are planarized,
some Source-model-only decorative architecture is cleanly omitted, and the
distant 3D skybox is not converted. These are omissions, not guessed release
geometry.

## Artifact fingerprints

- BSP: 19,716,348 bytes; SHA-256
  `43BF77D445D00842165CBD9C62DA9FBFE36E30CD2F575E6F263CDE0894203A69`
- PK3: 3,877,188 bytes; SHA-256
  `A0452E095D4E7A0AFC82A6DDCFAFF211A223C16A5FD9D54F273B4499B9CB4651`
- source ZIP: 412,016 bytes; SHA-256
  `ACF14BA0DE9C9998B66BED045D09174AFE8618D849A81E978A32BBC4EB2471D8`
