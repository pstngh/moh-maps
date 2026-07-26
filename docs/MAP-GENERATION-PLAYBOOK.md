# MOHAA/OpenMoHAA map-generation playbook

Status: normative production standard

Compatibility default: Medal of Honor: Allied Assault BSP version 19 and
OpenMoHAA

Last updated: 2026-07-26

## Mission

Create maps that are not merely compilable, but installable, visually
coherent, navigable by OpenMoHAA bots, reproducible from source, and honest
about remaining debt. Every revision must make the next map easier to build
correctly.

The research log explains how rules were discovered. This playbook states what
future work must do.

## Evidence labels

Use these labels when adding uncertain knowledge:

- **PROVEN**: repeated compile/runtime evidence or directly verified source
  behavior.
- **OBSERVED**: seen in one or more concrete tests but not generalized fully.
- **HYPOTHESIS**: plausible cause or technique awaiting an isolated test.
- **OPEN**: known gap with no selected solution.

Promote a hypothesis into a rule only after a controlled compile or engine
test. Record failed experiments; they prevent future repetition.

## Release-ready definition

A release candidate must pass every applicable gate:

1. **Source gate**: deterministic source/generator, scripts, material mapping,
   and conversion report exist.
2. **Geometry gate**: no leaks, invalid brushes, missing structural surfaces,
   obvious z-fighting, or inaccessible primary routes.
3. **Compile gate**: BSP, VIS, and full MOHlight succeed against retail AA
   shader data.
4. **Runtime gate**: the exact PK3 loads from an isolated OpenMoHAA home with
   no loose copy masking package errors.
5. **Multiplayer gate**: neutral, Allied, Axis, and spectator spawns work as
   required by the intended modes.
6. **Bot gate**: bots spawn, move, fight, respawn, and use more than one route.
7. **Visual gate**: exterior, interior, transition, long-sightline, high-angle,
   and map-edge views are inspected.
8. **Artifact gate**: canonical PK3 entries, sizes, hashes, README, and known
   debt are current.
9. **Knowledge gate**: revision report, research evidence, and reusable rules
   are updated.

Passing Q3map alone satisfies only part of gate 3.

## Non-negotiable production rules

- Compile against a clean retail AA `main` data set. An empty staging
  directory can make `common/caulk`, stock skies, and other shaders compile
  with incorrect flags.
- Use the original AA Q3map/VIS/MOHlight toolchain for AA packages.
- Run full MOHlight for the distributed package. Fast light is for iteration.
- Test the exact packaged PK3 in isolation.
- Use forward slashes in ZIP/PK3 entry names.
- Keep reference VMFs, retail textures, and Source model files out of the
  repository and package.
- Do not choose a stock palette merely because a previous map used it.
- Do not use a geometric volume threshold to classify Source detail as
  cosmetic. Thin walls, floors, and ceilings can have small volume and large
  visible area.
- Do not substitute props until their origin convention, orientation, size,
  and architectural role are understood.
- Do not claim bot compatibility because navigation generation completed.
  Observe bots moving and fighting.
- Do not solve a visual hole by hiding it with darkness or fog when structural
  geometry is missing.

## Phase 0: design brief

Record this before implementation:

| Decision | Required answer |
| --- | --- |
| Game target | AA only, AA plus OpenMoHAA, SH, or BT |
| Modes | DM, TDM, objective, round-based, or combination |
| Player/bot count | Intended minimum and maximum |
| Layout source | Original design, measured reference, or conversion |
| Fidelity target | Inspired, layout-faithful, or near-remake |
| Asset policy | Stock AA only, expansion assets, and/or original bundled art |
| Lighting direction | Time, weather, direct/fill relationship, interior mood |
| Performance budget | Expected brushes, patches, surfaces, lights, compile time |
| Explicit omissions | Detail categories that are intentionally out of scope |

For reference conversions, measure the source before choosing it. Record file
size, world/total solids, sides, displacements, entities, props, unique models,
materials, bounds, spawn counts, and light counts. Select the simpler reference
when fidelity value is otherwise similar.

## Phase 1: source and risk audit

### Original maps

- Define a connected circulation graph before decorative modeling.
- Provide at least two useful routes between major combat spaces.
- Establish scale with player width, headroom, stair rise, cover height, and
  sightline length.
- Build sealed structural space first; mark non-sealing detail deliberately.

### Source/VMF conversions

- Separate world brushes, `func_detail`, `func_brush`, displacements, gameplay
  helpers, point entities, and model props.
- Exclude the distant 3D skybox by verified bounds, not an arbitrary visual
  guess.
- For large Source layouts, use an explicit structural sky shell and import
  internal geometry as detail. This preserves collision while avoiding
  MOHAA's fixed portal-data limit.
- Preserve all architectural detail initially. Optimize only after identifying
  specific cosmetic classes by material, role, placement, or visibility.
- Audit mixed-material brushes before preserving Source nodraw as AA caulk.
  If the Source model, displacement, or overlay that covered a support face is
  omitted, that nodraw face may become a literal sky hole and needs a
  material-matched fallback.
- Classify helper brushes by gameplay role before omission. Preserve explicit
  player clips and measured large collision volumes when they define routes
  or containment; editor hints, skips, areaportals, and triggers are not
  equivalent to collision.
- Record every skipped class and count in the conversion report.

## Phase 2: geometry construction

### Brushes

- A brush must be convex and have consistent outward plane winding.
- Use tested helpers for boxes, cylinders, panels, and oriented planes.
- Use `common/caulk` on genuinely invisible faces only after verifying retail
  shader resolution.
- Use detail flags for internal geometry that should not split the BSP tree.
- Keep collision simpler than decorative surfaces.

### Displacements and curved terrain

Ordinary BSPSource displacement reconstruction requires:

1. recover backing-brush vertices by intersecting its planes when
   `vertices_plus` is absent;
2. identify and order the four displacement-side vertices from
   `startposition`;
3. treat absent `offsets` rows as zero;
4. combine bilinear base, offset, and `normal * distance`;
5. orient patch winding toward playable air;
6. preserve a backing hull for sealing/collision;
7. add material-matched boundary skirts where displacement lift exposes edges.

Do not build displacement surfaces as touching triangle micro-prisms. AA
Q3map can discard shared faces unpredictably. Joined patch meshes with simple
collision backings are the proven direction.

Raw Source samples are not automatically valid quadratic patch controls.
Midpoint-expanded bilinear controls avoid the bowed or pinched terrain seen in
early Dust II iterations.

Patch count is a compile budget. Full Source displacement conversion can be
correct but impractical for the legacy compiler. If simplification is needed,
prioritize traversable terrain, preserve collision, and document exactly which
surfaces remain planar.

When full displacement patches exceed that budget, a lowered,
material-matched visual underlay may cover narrow XY seams between traversable
planar backing faces. Keep the original backing brushes as collision, expand
the underlay only enough to cover the measured gap, and validate that it does
not bridge an intentional opening.

### Architectural Source models

VMF prop entities name model files but do not contain the model geometry.
Before substituting an architectural model:

- group placements by model;
- measure repeated center spacing and orientation;
- infer base/top origin convention from neighbors and nearby brush surfaces;
- distinguish a complete wall module from decorative trim;
- use non-solid visual substitutes only when visual dimensions are measured
  but the collision role remains uncertain;
- validate the longest repeated row from a distant viewpoint.

Do not infer interactivity from a model name. A static prop whose path contains
`door` is not a functional door entity. Add AA door behavior only after
verifying source entity intent, pivot, travel or swing clearance, collision,
and bot route value.

One generic arch size is not adequate for every `arch_*`, `port_*`, or façade
model. Cobblestone proved that major ports repeat at 256 units while port
sections repeat near 128.

Revision-3 evidence narrows that rule further: repeated center spacing does
not establish a model's width, height, pivot, shape, or architectural role.
If a model family cannot be reconstructed from its mesh, verified bounds, or
measured surrounding opening, omit it from the release build. Keep guessed
placeholders behind an explicit diagnostic flag; never emit one generic
three-brush frame for an entire `arch_*` or `port_*` class.

### Props and bot collision

- Ground props from verified model bounds or nearby support surfaces.
- Reject or specially handle large pitch/roll values; a tilted Source prop
  cannot safely use an upright AA replacement.
- Prefer static, simple cover shapes in primary bot routes.
- Avoid vehicles and dynamic obstacles in narrow circulation paths unless bot
  behavior is explicitly tested.
- A decorative panel may be non-solid, but its supporting wall must exist.

## Phase 3: materials and original textures

Follow this order:

1. Inventory actual stock shader and image names.
2. Extract candidate images for visual inspection when needed.
3. Build contact sheets by category: stone, plaster, brick, cobble, wood, roof,
   metal, doors/windows, foliage, sky, and utility.
4. Map each source material or authored surface role to two or three candidates.
5. Compare scale, color, contrast, weathering, and directional features.
6. Test candidates in engine under the map's actual lighting.
7. Record the selected asset and why in the map README/catalog.

Broad regex classification is acceptable for an initial diagnostic build, not
for final art. Important façades and landmarks require deliberate per-material
mapping.

When stock AA has no close match, create original game-ready art:

- power-of-two TGA/JPG, normally 256 or 512 pixels;
- seamless edges for tiling materials;
- controlled contrast that survives AA lightmaps;
- alpha masks only where the shader requires them;
- original or redistributable content only;
- in-engine scale and seam validation.

MOHAA primarily needs diffuse/color textures and shader behavior, not a modern
PBR set.

## Phase 4: multiplayer entities and scripts

For ordinary DM/TDM compatibility include:

- `info_player_deathmatch`;
- `info_player_allied`;
- `info_player_axis`;
- `info_player_start`;
- same-named `.scr`;
- `<name>_precache.scr`;
- `global/DMprecache.scr`.

Stock maps commonly use roughly 11-25 neutral DM spawns. Count is not enough:

- raise origins above the floor;
- keep hull clearance from walls and props;
- prevent immediate mutual sight where possible;
- distribute spawns across useful circulation;
- aim players toward playable space;
- test actual respawns with multiple bots.

For OpenMoHAA bots, configure both:

```text
sv_maxbots 8
sv_numbots 8
```

`bot_enable` alone does not spawn bots.

## Phase 5: lighting

Treat lighting as four coordinated roles:

1. direct sun or principal directional light;
2. sky/diffuse fill;
3. low ambient floor;
4. local fixtures with spatial purpose.

Proven visual direction for outdoor AA work:

- warm or neutral direct light;
- cooler diffuse fill so shadows separate chromatically;
- low ambient rather than a bright global wash;
- restrained local fixtures;
- sky and farplane colors designed with the lighting.

Do not place strong fill lights over multiplayer spawns. They flatten surfaces,
create a tan wash, and disconnect lighting from architecture.

Source and MOHlight intensity scales differ. Translate source fixtures into a
restrained AA range, preserve colors/origins, and inspect the darkest playable
interior. A formula that worked in the current conversions is
`clamp(source * 0.9 + 15, 10, 200)`, but it is an example to validate, not a
universal constant.

Lighting QA must cover:

- full-sun exterior;
- shadowed exterior;
- deepest interior;
- interior/exterior transition;
- player silhouette against both bright and dark backgrounds;
- long sightline and map edge.

## Phase 6: compile

Typical commands:

```powershell
Q3map.exe -fast -threads 4 -gamedir "retailRoot" -moddir main "map.map"
Q3map.exe -vis -fast -threads 4 -gamedir "retailRoot" -moddir main "map.bsp"
MOHlight.exe -threads 4 -gamedir "retailRoot" -moddir main "map.map"
```

Interpret failures by stage:

| Symptom | Likely cause | Required response |
| --- | --- | --- |
| Leak | Structural void reaches outside | Fix sealing before VIS/light |
| Invalid/degenerate brush | Winding or geometry bug | Isolate and repair generator |
| Missing/black materials | Shader data absent or wrong name | Compile against retail data and verify asset |
| Portal-data overflow | Too many structural split planes | Structural shell plus internal detail; do not hide geometry |
| BSP compile stalls | Excessive structural brushes or patches | Measure cost by class; simplify selectively |
| Patch hash warnings with correct render | Legacy tool limitation | Record and verify visually; do not assume fatal |

Record input/output face counts, clusters, portals, compile duration, warnings,
and final BSP size.

## Phase 7: package and runtime test

The runtime PK3 normally contains:

```text
maps/dm/<map>.bsp
maps/dm/<map>.scr
maps/dm/<map>_precache.scr
textures/...          # only original bundled textures
scripts/...           # only required custom shaders
models/...            # only original/redistributable models
```

Do not package `.prt`, `.vis`, logs, retail assets, or reference VMFs.

Runtime procedure:

1. Create a fresh isolated OpenMoHAA home.
2. Copy only the candidate PK3 and required key/config files.
3. Launch against retail base data.
4. Load the map by its final name.
5. Spawn the intended bot count.
6. Capture logs and screenshots.
7. Confirm the package hash matches the repository artifact.

## Phase 8: visual and bot QA

Use a repeatable viewpoint matrix:

| View | What it catches |
| --- | --- |
| Spawn-level route | collision, scale, props, ordinary lighting |
| High/spectator overview | missing roofs, open shells, floating props |
| Long exterior sightline | unsupported modular models, farplane/sky |
| Deep interior | missing ceilings/floors, black lighting |
| Interior/exterior threshold | exposure contrast and leaks |
| Map perimeter | sky-shell mistakes and distant geometry |
| Displacement edge | seams, holes, winding, backing visibility |
| Repeated façade/module row | wrong model spacing or generic substitutes |

Run at least one controlled before/after comparison from the same viewpoint
for every visual repair. Random bot-follow screenshots are useful coverage but
do not replace deterministic regression views.

For scripted OpenMoHAA player cameras, `origin` sets position but ordinary
entity `angles` is not the rendered player view. Use the player `viewangles`
event immediately before capture, because a later client input frame can
overwrite it, or use a dedicated camera entity. Log `viewpos` during harness
development. A survey that misses the reported ground-level angle is useful
regression coverage, not proof that the reported defect is fixed.

Bot acceptance:

- all requested bots enter;
- bots leave spawn;
- bots traverse multiple spaces;
- bots fight and score kills;
- no dominant stuck cluster is observed;
- bots use interior and exterior routes where both exist;
- collision substitutions do not create one-way traps.

## Common failure patterns already learned

| Failure | Root cause | Proven lesson |
| --- | --- | --- |
| Black void/missing stock textures | Compiled without retail shaders | Always compile against real AA data |
| Floating cars/props | Source origin is not AA ground origin | Use verified bounds/support surface |
| Empty windows or floating shutters | Prop substitute without backing architecture | Restore/back the wall before decoration |
| Large sky holes and missing interiors | Small-volume `func_detail` filter | Never classify architecture by volume alone |
| Missing displacement triangles | Touching micro-brushes/shared faces | Use joined patches plus collision backing |
| Bowed terrain | Raw samples used as quadratic controls | Generate midpoint-expanded bilinear controls |
| Open displacement edges | Patch without backing/skirt | Preserve hull and material-matched boundaries |
| Triangular sky cuts in floors/walls | Exposed Source nodraw support face | Material-match only the exposed support of mixed brushes |
| Bright ribbons between planar terrain faces | Horizontal Source offsets exceed the backing polygons | Use a lowered material-matched seam underlay or reconstruct that bounded terrain group |
| Portal overflow | Source walls imported as structural BSP | Structural sky shell plus internal detail |
| Floating ribs and malformed arcades | Generic placeholder used for unrelated Source model families | Require per-family mesh/bounds/opening measurements or omit |
| Bots reach exterior terrain islands | Collision helpers omitted with editor helpers, or exterior boundary topology is incomplete | Preserve explicit player clips and measured route clips, then verify containment; clips alone do not replace a missing boundary |
| Flat tan scene | Oversized global/spawn lights | Low ambient, warm direct, cool fill, real fixtures |
| No bots despite bot support | Only `bot_enable` set | Set `sv_maxbots` and `sv_numbots` |
| Eight identical QA frames | No bots available to follow | Verify bot creation before screenshot cycling |

## Revision loop

For each playtest:

1. Archive and label the input screenshots.
2. List each defect by location and visible symptom.
3. Group defects by probable shared cause.
4. Inspect source data before editing.
5. Make the smallest cause-level change.
6. Regenerate and compare conversion counts.
7. Compile with a bounded but realistic time allowance.
8. Re-test the same viewpoints plus general bot coverage.
9. Record fixed, improved, unchanged, regressed, and newly exposed issues.
10. Update the revision report, map README, research log, and any reusable rule.
11. Package, hash, commit, and push the exact tested state.

Do not stack unrelated geometry, prop, lighting, and texture experiments into
one revision unless the user explicitly requests a broad rebuild.

## Remaining system investments

These are the highest-value improvements for better first builds:

- generate a visual catalog/contact sheets for all stock AA textures;
- create deterministic camera/viewpoint scripts per generated map;
- add automated brush bounds, winding, minimum-thickness, and spawn-clearance
  validation;
- emit material- and prop-mapping manifests instead of embedding all policy in
  regexes;
- parse compiler logs into machine-readable release gates;
- compare before/after screenshots at fixed cameras;
- build a reusable library of measured AA-native prop bounds;
- separate layout/topology generation from theme/material application.
