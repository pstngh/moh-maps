# Nuke revision 1 report

Status: first playable; awaiting human visual and route review

Date: 2026-07-26

## Identity

- Map: `codex_nuke`
- Target: Allied Assault BSP 19 and OpenMoHAA
- Modes: DM/TDM
- Reference: legally obtained `de_nuke_d.vmf`, not redistributed
- Art direction: original clean modern industrial material set

## Source evidence

The clean BSPSource decompile contains 8,039 solids, 48,098 sides, 761
displacement faces, 10,488 entities, 6,891 static props, 471 ordinary/spot
lights, 32 team spawns, and four real rotating-door entities.

All 121 visible brush materials resolve in the local Source 1 VPK. Of 1,405
unique referenced model files, 695 resolve in the ordinary VPK and 710
map-specific `autocombine` models resolve only in the BSP's embedded pak. The
audit reads metadata and records derived measurements; no Valve texture or
model bytes are committed or packaged.

The high-Y cluster containing 900 solids is distant/3D-skybox construction.
Revision 1 retains the measured playable cluster and omits that cosmetic
cluster.

## Revision-1 implementation

- 6,949 generated world brushes;
- 5,639 converted source solids;
- 604 planarized displacement faces;
- 632 material-matched displacement seam underlays;
- two explicit Source player-clip brushes and 86 large general clips;
- 638 simple measured prop replacements;
- 34 nonblocking original hero-industrial brushes representing ten medium
  silos, seven water tanks, two reactor/silo forms, and one process silo;
- four `func_rotatingdoor` entities with measured panels and origin brushes;
- 16 Axis, 16 Allied, and 32 neutral DM spawns;
- 471 restrained source-derived fixture lights plus original outdoor sun/fill;
- fourteen original 512×512 TGA materials.

The six generated raster sources, exact prompts, deterministic derivations, and
four-edge continuity validation are recorded in `ART-PROVENANCE.md`. The
distributable palette contains no Valve texture pixels.

## Compile validation

Q3map compiled 35,149 input faces to 32,140 output faces in 2,115 seconds. It
removed 3,009 faces and wrote a 14,676,312-byte unlit BSP. No missing-image,
malformed-brush, or fatal warning appeared.

Fast VIS completed in under one second:

- 154 portal clusters;
- 283 portals;
- 358 portal faces;
- 3,704 visibility bytes;
- average 153 clusters visible.

MOHlight 1.48 completed in 976 seconds and wrote the 23,422,268-byte lit BSP.
It reported:

- 15 `potential hash mismatch` warnings, all preserved for screenshot-guided
  follow-up;
- 33 entity-light-list clamps to the engine limit of 60 lights per leaf;
- no fatal error.

The build is valid, but the clamp count proves that translating every Source
fixture is not an ideal final policy. Revision 2 should spatially deduplicate
and budget fixtures, then compare the resulting interior illumination.

## Runtime validation

The final 18-entry PK3 was copied into a fresh isolated OpenMoHAA home path.
Its SHA-256 matched the repository package.

OpenMoHAA 0.82.1:

- loaded `dm/codex_nuke`;
- parsed the BSP in 0.118 seconds;
- generated Recast navigation in 10.509 seconds;
- admitted all eight configured bots;
- logged 27 kills during the 30-second smoke test, proving navigation,
  movement, combat, death, and respawn activity.

The lit BSP contains four `func_rotatingdoor` classname records. Dedicated
server evidence cannot prove visible panel alignment or player activation, so
door swing direction and clearance remain a human-client check.

## Reproducibility

A separate regeneration produced the same 5,221,665-byte `.map`, SHA-256
`22D39A6E47E657F4F6B2A0FC4E9AD008DB36695E6B2119C13EC219A3C9EA91C0`.
The validator found all fourteen custom materials, all four doors, all 64 DM
spawns, balanced syntax, and no Source asset path.

## Release fingerprints

- MAP: 5,221,665 bytes; SHA-256
  `22D39A6E47E657F4F6B2A0FC4E9AD008DB36695E6B2119C13EC219A3C9EA91C0`
- BSP: 23,422,268 bytes; SHA-256
  `88EB02194D6074C429670E0B3B57E80B4D100043EFC9C3469FC987CE2601F2D4`
- PK3: 7,059,297 bytes; SHA-256
  `3E577D3711C2B3ACFA9D7665D8D7968581C90615071D145C475B221AE71AF014`
- derived reference audit: 1,899,007 bytes; SHA-256
  `427443BC161C5F07D8E440FFA653D4CBFC1DA751BF3C4E17FDD270B12723987D`

## Known remaining debt

- Human visual and route QA has not yet happened.
- The 710 Source-only combined prop assemblies are omitted. Important HVAC,
  pipe, joist, rail, ladder, curb, fence, and trim families need bounded
  original procedural templates rather than solid combined AABBs.
- Source displacement terrain is planar rather than fully sculpted.
- The distant/3D-skybox cluster is omitted.
- Fifteen MOHlight hash-mismatch coordinates need screenshot correlation.
- The 471 translated fixture lights cause 33 entity-light clamps and should be
  pruned or clustered in a later lighting pass.
- Door activation, panel alignment, direction, and swing clearance need a
  human client check.
- Fourteen source `func_breakable` solids remain static in revision 1.
- Source overlays, cubemaps, decals, graffiti, warning placards, minor signs,
  and clutter are intentionally omitted.

## Knowledge promotion

- The audit rule now requires both the ordinary VPK and BSP embedded pak.
- The playbook now prohibits redistributing commercial asset bytes while
  permitting recorded roles, bounds, and derived measurements.
- Original texture work retains its source images, exact prompts,
  deterministic build, edge validation, and contact sheet.
- Simple hero-scale industrial silhouettes may be rebuilt as original
  nonblocking geometry when names, placements, and measured bounds agree.
- Dense Source fixture fields require an explicit MOHAA light budget rather
  than one-for-one translation.

## Release checklist

- [x] Clean VMF/VPK/BSP-pak audit completed.
- [x] Original texture sources, prompts, derivations, and edge tests retained.
- [x] Generator reproduces a byte-identical `.map`.
- [x] Q3map BSP, fast VIS, and full MOHlight completed.
- [x] Final package contains no Source asset paths or Valve assets.
- [x] Exact isolated PK3 loaded in OpenMoHAA.
- [x] Eight bots spawned, navigated, fought, died, and respawned.
- [x] Four door entities are present in the BSP.
- [ ] Human client visual, route, material-scale, lighting, and door review.
- [ ] Screenshot-guided repair of remaining visual defects.
