# MOHAA map candidate validation gates

A candidate is not complete until every applicable gate passes. Passing a
technical gate never substitutes for visual inspection or explicit human
acceptance.

## 1. Source gate

- Retain reproducible editable source and generator inputs.
- Record tools, versions, provenance, and transformations.
- Permit no undocumented transformation.

## 2. Geometry gate

- Require convex valid brushes, correct winding, and valid face construction.
- Reject leaks, void exposure, missing walls, disconnected terrain islands,
  crude visible sealing slabs, z-fighting, accidental holes, and floating
  buildings, props, cars, or cover.
- Never infer geometry from filenames or aggregate bounds alone.
- Inspect every changed viewing domain.

## 3. Material gate

- Reject missing or unsupported visible textures, accidental caulk/nodraw,
  unintended transparency, and incorrect scale, orientation, alignment, or
  tiling.
- Make original textures reproducible, power-of-two, redistributable, and
  tested under MOHlight.
- Commit no proprietary source-game art.

## 4. Lighting gate

- Give sun, sky fill, ambient floor, and local fixtures distinct purposes.
- Reject flat tan wash, crushed interiors, architecture-disconnected lights,
  and darkness or fog used to conceal missing construction.
- Inspect exterior and interior lighting in-engine.

## 5. Compile gate

- Complete BSP, VIS, and full MOHlight with the intended AA toolchain.
- Classify every warning from direct evidence; do not excuse it because another
  map emitted it.
- Record exact source/output hashes when useful.

## 6. Package and runtime gate

- Test the exact PK3 in isolation with no loose files masking omissions.
- Verify package contents and paths, scripts, spawns, and intended mode loading.

## 7. Bot and gameplay gate

- Observe bots spawning, moving, fighting, and respawning.
- Verify multiple meaningful routes, appropriate widths, and collision.
- Test doors and dynamic obstacles when present.
- Do not infer bot compatibility from navigation generation alone, and do not
  make an unverified dynamic obstacle part of a primary route.

## 8. Visual gate

Inspect full-resolution evidence for player-height views, high-angle overview,
map edges and boundaries, every major route in both directions, interiors,
exteriors, transitions, long sightlines, changed areas, previously hidden
areas, and exact user-reported failure viewpoints. A convenient automated
camera suite cannot replace the angle that exposed the real defect.

## 9. Human acceptance gate

- State all known debt honestly.
- Provide the exact candidate for user testing and record feedback.
- Require explicit approval of the tested revision.
- Only then update the map status to `accepted` and promote it to
  `accepted_baseline`.

## Elaborate-map process gate

1. Measure and audit the source or reference.
2. Build a structural shell or one representative zone.
3. Compile and inspect it.
4. Validate geometry, materials, scale, and lighting.
5. Correct the process from evidence.
6. Expand zone by zone.

Do not generate or transform an entire detailed map from unverified assumptions.
