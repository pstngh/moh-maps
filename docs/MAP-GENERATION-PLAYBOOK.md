# MOHAA/OpenMoHAA map-generation playbook

Status: normative production standard

Compatibility default: Medal of Honor: Allied Assault BSP version 19 and
OpenMoHAA

Last updated: 2026-07-27

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
- For Source maps, audit both the game VPK and the BSP's embedded pak. Generated
  `autocombine` models may be absent from the ordinary VPK even when the VMF
  references them; treating the VMF as complete can remove major architecture.
- Record source asset metadata and visual roles, but never place extracted
  commercial texture/model bytes in the repository or distributable PK3.
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
  guess. Classify the playable cluster on all three axes; a one-axis cutoff
  can retain distant construction whose X/Z happen to overlap the main map.
- For large Source layouts, use an explicit structural sky shell and import
  internal geometry as detail. This preserves collision while avoiding
  MOHAA's fixed portal-data limit. Size the shell from complete retained-brush
  extents rather than brush centers alone.
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
- Do not assume an ordinary Quake `func_detail` brush entity survives MOHAA
  Q3map. The tested AA compiler stripped those brush entities and produced only
  the structural shell. Emit required authored geometry in `worldspawn`, or use a
  separately proven MOHAA-specific detail representation, and compare input
  versus emitted face/brush counts after every compiler-policy change.
- For original maps whose reference depends heavily on props, define the
  playable air/route grid first and greedily merge its complement into complete
  building masses. Add facades, windows, roofs, and trim onto those closed
  volumes. This makes omitted reference props incapable of becoming structural
  holes. Keep the authored brush budget small enough that worldspawn splitting
  remains practical.

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

Hero-scale skyline models are a distinct case. If the source name, full local
bounds, placement, and reference view all establish a simple industrial form,
an original cylinder/frustum/dome reconstruction may preserve recognition.
Keep it non-blocking until source collision or route interaction is proven;
never use one enormous model AABB as player collision through an interior.

### Screenshot-guided missing-family reconstruction

Human screenshots can prove that an omitted model family is architectural
debt even when its original mesh cannot be distributed. It does not prove what
geometry belongs in that hole.

**Hard rule:** an aggregate model AABB or hull is only an outer envelope. It
does not prove a principal run axis, internal offsets, number of elements, or
connectivity. Never generate rails, pipes, ladders, joists, curbs, ducts,
trim, fences, or supports from that box alone—even when the filename names the
family.

Nuke revision 2 is the counterexample. Its 419 aggregate-hull placements
compiled and passed bot QA, but the next human review showed 803 inferred
brushes as giant floating bars, crossed beams, false ladders, and arbitrary
frames. Technical success did not validate visual topology.

A missing-family template requires at least one independent topology source:

- parsed mesh vertices/indices;
- verified per-instance endpoints and local axes;
- a manually authored reconstruction tied to reference views and coordinates;
- or an equivalent source that proves the internal arrangement.

Use hull bounds afterward as a containment sanity check. Keep uncertain
substitutes omitted. When a template is proven, keep it nonblocking unless
verified collision says otherwise, and cap repeated elements for the legacy
compiler. Filling a visual hole is permission to restore evidenced enclosure
and silhouette, not permission to add arbitrary cover or change a route.

For every screenshot pass, record a compact matrix:

- image number or viewpoint;
- observed defect;
- inferred source class;
- implemented response;
- whether the response is technically proven or still awaits visual
  confirmation.

### Props and bot collision

- Ground props from verified model bounds or nearby support surfaces.
- Reject or specially handle large pitch/roll values; a tilted Source prop
  cannot safely use an upright AA replacement.
- Prefer static, simple cover shapes in primary bot routes.
- Avoid vehicles and dynamic obstacles in narrow circulation paths unless bot
  behavior is explicitly tested.
- A decorative panel may be non-solid, but its supporting wall must exist.
- Prefer explicit Source clip brushes for collision around non-solid hero
  reconstructions. Validate the silhouette and the route boundary separately.

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

Keep original texture generation reproducible:

- retain original raster sources and exact prompts/provenance;
- build final power-of-two assets through a deterministic script;
- guarantee edge continuity mechanically rather than trusting a visual claim
  of seamlessness;
- use source-game textures only as local role/scale references;
- validate diffuse contrast under MOHlight, because modern PBR response does
  not transfer to MOHAA.

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

- If the reference provides dedicated deathmatch spawns, preserve those
  positions as neutral AA spawns. Do not manufacture neutral spawns by
  duplicating both teams unless the source truly has no DM set.

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

Do not translate a dense Source fixture field one-for-one merely because every
light parses. Cluster or deduplicate co-located fixtures, budget lights per
room/zone, and inspect MOHlight's entity-light diagnostics. Repeated
`Num lights per leaf clamped ... to 60` messages prove that the AA runtime
cannot preserve the intended local-light list; record them as open lighting
debt and reduce the fixture set in the next measured pass.

Assign an explicit lightmap policy to reconstructed cosmetic geometry, but do
not apply `surfaceparm nolightmap` by family name or size alone. Vertex-lit
brushes can render as bright/fullbright shapes when their shader, normals, or
environmental lighting does not supply the expected modulation. Prove the
policy in engine on representative exterior, interior, and shadowed examples.
Reserve baked lightmaps for primary walls, floors, terrain, doors, and large
surfaces whose shading defines the room; prefer baked lighting for new detail
until both the budget and vertex-lit appearance are measured.

`MAX_MAP_LIGHTING exceeded from N lightmaps` is a hard failure, not a warning.
Nuke revision 2 hit it at 180 lightmaps after adding 803 invalid fill brushes.
Marking 6,126 sides non-lightmapped let MOHlight finish but caused visually
dominant white clutter. Revision 3 removed the invalid fills, restored normal
lighting, and full MOHlight completed within budget. First reduce or remove
unproven geometry; do not hide geometry debt with a broad lighting override.

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
| Long brush processing without an error | Large faithful brush set or expensive T-junction work | Record CPU time and progress; do not call duration alone a map failure or delete architecture blindly |
| `MAX_MAP_DRAWINDEXES` | Too many merged polygon indexes, often amplified by T-junction insertion | Measure faces/inserted vertices; reduce evidenced detail first; use `-notjunc` only as a documented visual-debt fallback |
| `MAX_MAP_LIGHTING` | Too many baked-lightmap surfaces | Vertex-light narrow cosmetic detail; preserve lightmaps for primary architecture |
| Patch hash warnings with correct render | Legacy tool limitation | Record and verify visually; do not assume fatal |

`-notjunc` can avoid a fixed draw-index overflow without deleting measured
brushes, but it transfers compiler work into a possible in-game crack/seam
defect. Cache revision 1 is the first evidence: normal Q3map added 84,040
T-junction vertices to a 57,622-face map and failed at 314,846 vertices;
`-notjunc` compiled the same faces. Treat this as a map-specific fallback, not
a default. It requires representative edge/seam screenshots before release.

Compiler flags do not replace source budgeting. Cache probes showed that
`-fast`, `-nosubdivide`, and `-notjunc` did not materially shorten early brush
processing, and a 9,058-brush/47,381-face normal build still exceeded the
draw-index cap. Any later reduction must classify detail by proven role and
re-check missing walls, floors, ceilings, cover, and routes.

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
| Empty authored detail despite a valid `.map` | Ordinary Quake `func_detail` brush entities stripped by MOHAA Q3map | Put required authored brushes in `worldspawn` or prove a MOHAA-specific detail form; validate emitted counts |
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

## Clone-from-scratch interpretation gate

When a user asks to clone an existing map "from scratch," the phrase describes
the construction method, not the topology target.

- Reauthor native target-engine geometry while preserving the requested map's
  actual routes, scale, elevations, site placement, openings, and defining
  landmarks.
- A reference VMF/BSP may be used as a measurement drawing. Direct brush
  conversion is also valid when the user authorizes it; never ship private
  source files or commercial texture/model/sound/radar bytes.
- Do not substitute an analogous, inspired-by, compacted, or optimized route
  graph unless the user explicitly authorizes a redesign.
- For native reauthoring, create a collision-aware route blueprint before
  facades and show that all supplied spawns connect. For direct conversion,
  keep that blueprint as an independent connectivity validator.
- Treat user rejection for non-recognition as a failed brief, not ordinary art
  debt. Mark the revision rejected and replace the public generator baseline.

**PROVEN Inferno rule:** a raw overhead floor projection is insufficient. It
can include rooftops, exterior pads, and stacked surfaces. Recover walkable
space by checking player headroom, testing neighbor transitions against solid
planes, and flood-filling from real spawns. Persist both the connected nodes
and permitted edges; wall generation must consume the edge graph so it cannot
close a real passage or invent a shortcut.

For large native reauthorings, merge visual facade runs aggressively enough to
stay within the original BSP budget, but never simplify the measured floor or
route graph merely to save brushes.

### Route graph is not architecture

Inferno revision 2 proves that a collision-correct walk graph can still produce
an unrecognizable map. Do not render every blocked occupancy-cell edge as a
facade or extend each edge into a shallow building strip.

- Use the route graph only to verify connectivity, widths, and openings.
- Author continuous callout-scale streets rather than visible grid cells.
- Fill non-playable space with complete semantic building/courtyard volumes,
  not hollow boundary extrusions.
- Group elevations into intentional stairs, ramps, floors, and roofs; do not
  expose every sampled 8-unit height change as architectural segmentation.
- Establish recognizable silhouettes and landmark compositions at each major
  callout before generating secondary windows, trim, roofs, or clutter.
- Require human ground-level and overview recognition gates before calling a
  technically playable clone a baseline.

**PROVEN recognition rule:** topology fidelity, architecture fidelity, and art
fidelity are separate gates. Compile/navigation success proves none of the
visual gates. A generator may consume a measured graph for validation, but its
rendered building grammar must be authored at the scale humans perceive.

**PROVEN radar-comparison rule:** when a source map provides an overview image
and `pos_x`/`pos_y`/`scale` metadata, transform the authored semantic plan into
that frame and compare the route outline plus spawn/site anchors before a full
compile. This independently checks macro scale and callout relationships. It
does not prove elevation, interiors, facade massing, or ground-level
recognition, and commercial radar pixels remain private reference data rather
than repository/package content.

For simple hero landmarks, parsed source-model bounds can establish original
substitute dimensions without copying a mesh. Combine local bounds, entity
origin/orientation, nearby support geometry, and a reference view. Bounds alone
still do not prove complex topology, pivot behavior, or collision.

### Direct-conversion escalation rule

Inferno revisions 1-3 prove that measured topology, official-radar alignment,
and semantic massing can all pass while the rendered architecture remains
unrecognizable. If repeated inferred/native reauthoring passes fail recognition
and the user authorizes direct conversion:

1. reconstruct the playable VMF/BSP brush architecture before optimizing it;
2. define and count included world/brush/detail/breakable classes;
3. explicitly count excluded helpers, skybox geometry, displacements, props,
   and unsupported entities;
4. substitute only original/redistributable textures and target-engine assets;
5. retain the route graph, spawns, and radar transform as independent
   validators rather than geometry generators;
6. compile the fidelity-first candidate even when it is slow, provided the
   compiler continues progressing and emits no error;
7. accept `-notjunc` only as documented seam debt when it preserves measured
   architecture and the ordinary build is impractical or exceeds fixed limits;
8. require human callout screenshots before class-based brush reduction.

**PROVEN preservation rule:** do not solve a nominal BSP-budget overage by
preemptively filtering architecture. A valid, running over-budget candidate is
more useful for the first recognition gate than a smaller unrecognizable map.
After human review, optimize only feature classes whose visual and gameplay
role is understood, then repeat compile, runtime, and fixed-view screenshot
checks.

### Measured prop-fill pass after direct conversion

When human screenshots recognize the direct brush architecture but show hollow
facades, empty sites, or a missing skyline, preserve the accepted brush layer.
Restore the visually structural model layer by measured class instead of
rewriting the layout or filling every omitted model.

1. Parse every referenced model header and persist its local hull bounds,
   reference count, source fingerprint, and parser result.
2. Place substitutes from the original entity origin, Source angles, uniform
   scale, and parsed local bounds. Keep a machine-readable record for every
   substituted instance.
3. Prioritize windows, shutters, doors and frames, arches, roof overlays,
   chimneys, structural supports, gameplay cover, and defining landmarks.
4. Make approximate facade, trim, roof, and support pieces non-solid. Give
   collision only to measured cover and simple landmark bodies whose gameplay
   role is clear.
5. Collapse duplicate multi-part landmark collision where several source
   models describe one physical body.
6. Omit foliage, wires, tiny clutter, highly irregular meshes, unknown pivot
   conventions, and strongly pitched or rolled props until a target-engine
   representation is proven.
7. Gate the pass by candidate count, bounds-resolution count, per-class
   substitutions, brush totals, compile/runtime evidence, and a new human
   screenshot set. Do not claim a visual fix from metadata alone.

**PROVEN Inferno prop-layer rule:** a direct brush conversion can be
architecturally recognizable while still appearing broken because model props
carry windows, shutters, roof edges, pillars, chimneys, cover, and site
landmarks. Parsed model bounds are sufficient for conservative box/prism
substitutes, but not for arbitrary mesh reconstruction. Keep these substitutes
separate from accepted architecture and preserve an auditable omitted set.

Generated MAP preflight must also reject literal escaped newline sequences in
brush blocks. A JavaScript `join("\\n")` emits two characters, not a line
break, and can make Q3map report an apparently unrelated incomplete line.

A clean compiler stage must also contain every authored shader image before BSP
generation. Q3map may emit a BSP after `Couldn't find image` warnings, but it
has already used fallback texture dimensions and may bake visibly wrong UV scale.
Compare staged custom-image names, counts, and hashes against the canonical
asset set before launching the expensive compile; treat any missing-image warning
as a failed build even when geometry succeeds.
