# Geometry and visual quality

## Evidence-first construction

For elaborate work, measure the source/reference, build a shell or one
representative zone, compile and inspect it, correct assumptions, and expand
zone by zone. Do not infer detailed geometry from filenames, aggregate bounds,
or a radar image alone.

## Geometry checks

- Require convex brushes, correct winding, valid faces, and reproducible source.
- Reject leaks, exposed void, missing walls, disconnected terrain islands,
  visible sealing slabs, accidental holes, z-fighting, and floating structures,
  props, vehicles, or cover.
- Distinguish rendered terrain from the sealed hull. Join floor/foundation,
  side enclosure, and ceiling at every expanded boundary.
- Treat a visible perimeter as a full ownership system: models, wire, posts,
  curbs, rails, collision/playerclip, foliage, and structural boundaries.
- Inspect every changed viewing domain and both directions of each connection.

## Materials and lighting

- Verify actual shader/image behavior; filenames are not visual evidence.
- Reject missing/unsupported visible textures, ambiguous caulk/nodraw,
  unintended transparency, and bad scale, orientation, alignment, or tiling.
- Use original redistributable power-of-two art when stock assets are inadequate;
  test it under MOHlight and record provenance.
- Give sun, sky fill, ambient floor, and fixtures distinct jobs. Reject flat tan
  wash, crushed interiors, arbitrary lights, and darkness/fog that hides debt.

## Visual evidence matrix

Retain full-resolution evidence for:

- player-height routes in both directions;
- high-angle overview;
- edges, boundaries, and newly exposed areas;
- interiors, exteriors, and transitions;
- long sightlines and changed zones;
- every exact user-reported failure viewpoint.

Bind each view ID to explicit categories in an exact-hash evidence plan. Require
fixed origins/angles for matrix coverage; spectator-follow and bot-follow images
may show activity but do not satisfy fixed-view categories. Hash each screenshot
and inspect it at full resolution before recording a semantic conclusion.

Validate camera origins after geometry changes. A captured image from inside a
wall, step, roof, clip, or unrepresentative location is a failed QA sample.
Automated capture count and script success do not establish visual coherence.

Convert human screenshot feedback into a named regression viewpoint, diagnose
the shared cause from source and engine evidence, and re-inspect all affected
viewing domains. Never use lighting, fog, or camera selection to conceal missing
construction.

For autonomous capture, review records, and regression comparison, follow
[autonomous-evidence-loop.md](autonomous-evidence-loop.md).
