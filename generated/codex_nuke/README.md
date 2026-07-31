# Codex Nuke

`codex_nuke` is a layout-faithful Allied Assault/OpenMoHAA DM/TDM conversion
of the CS:GO-era Nuke layout. Its art direction is clean modern industrial,
not an Allied Assault or Second World War reskin.

Revision 4 responds to the human finding that the stable revision 3 still felt
very empty. It preserves the measured Source brush layout and adds a derived
inventory plus family-specific original reconstructions for the machinery,
site vessels, supports, ventilation, fencing, vehicles, furniture, control
rooms, and exterior dressing that make Nuke recognizable. It does not package
Valve textures, meshes, models, or other Source assets.

## Design brief

| Decision | Current answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM/TDM first; 4-10 bots |
| Layout source | Measured CS:GO Nuke VMF/BSP facts |
| Fidelity target | Recognizable rooms, routes, industrial landmarks, exterior silhouette, and clean institutional readability |
| Asset policy | Original bundled art plus stock AA utility shaders; no Valve assets distributed |
| Lighting | Neutral-warm daylight, cool sky fill, purposeful interior fixtures, baked shading on all opaque architecture and dressing |
| Explicit low-priority omissions | Graffiti, logos, warning placards, minor signs, switches/outlets, paperwork, and similar clutter |
| Known structural debt | Planarized displacement curvature, distant 3D skybox, and selected Source autocombines whose topology is not proven |

## What the reference audit proves

- The BSPSource 1.4.8 decompile completed without errors.
- The VMF contains 8,039 solids, 48,098 sides, 761 displacement faces, 10,488
  entities, 6,891 static props, and 471 ordinary/spot lights.
- All 121 visible brush materials resolve in the user's local CS:GO data.
- All 1,405 referenced model files are locally measurable: 695 ordinary models
  resolve from `pak01`, and 710 generated `autocombine` models resolve from the
  BSP embedded pak.
- Four real Source rotating-door entities exist and are converted to AA
  `func_rotatingdoor` entities.
- The distant Source Y 7,168-12,360 cluster is skybox scenery and is excluded
  from the playable AA shell.

See [`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) and the derived
[`reference-audit.json`](reference-audit.json).

## Revision-4 fidelity layer

[`fidelity-manifest.json`](fidelity-manifest.json) records derived facts for
4,687 model instances in the playable envelope: model-family identifier,
entity class, transform, scale, Source solid setting, and measured studio
header bounds. Bounds remain envelopes, not proof that the model is a filled
box.

The generator restores 1,932 ordinary placements using 2,855 original
family-specific brushes. Major groups include:

- 242 foliage placements, 236 chain-link components, and 216 ventilation
  pieces;
- 178 cover pieces, 137 structural supports, 137 furniture pieces, 83
  electrical assemblies, and 76 windows;
- 59 control-room displays, 44 static doors, 35 chairs, 24 industrial rails,
  22 transformers, 17 cars, 8 forklifts, and 8 cargo-crane components;
- the defining A-site silo/vessel, upper crane, B-site reactor head and fuel
  racks, core crane/computers, platforms, columns, consoles, and equipment.

Frame-like machinery uses sparse beams, vessels use cylinders/frustums,
vehicles use recognizable multi-box silhouettes, and foliage uses non-solid
alpha cross-cards. Collision comes only from measured Source solid intent or
existing brush/clip geometry. All 710 autocombines remain explicitly omitted;
revision 2 proved that their aggregate bounding boxes do not reveal internal
mesh topology.

The deterministic source contains 9,448 world brushes, 329 entities, 16 Axis,
16 Allied, and 32 neutral DM spawns. It converts 5,639 measured playable
Source solids, planarizes 604 displacement faces, retains measured clip
volumes, adds 632 bounded seam underlays, keeps four interactive doors, and
clusters 471 Source fixture candidates to 259 local lights.

## Original texture palette

The package contains 22 original 512x512 TGA materials. Revision 4 adds clean
white machinery metal, yellow/red safety paint, blue equipment, rubber,
control-panel material, and alpha-tested foliage to the previous concrete,
cladding, floor, asphalt, metal, grass/gravel, glass, chain-link, and window
materials.

Precise creation and derivation records are in
[`ART-PROVENANCE.md`](ART-PROVENANCE.md); the generated visual inventory is
[`texture-contact-sheet.png`](texture-contact-sheet.png). Valve files are read
locally only for material roles, dimensions, transforms, pivots, and repeated
placement families.

## Lighting-budget policy

The first full revision-4 BSP was valid, but MOHlight requested 210 lightmap
pages against Allied Assault's hard limit of 180. The bundled MOHTools 1.48
executables do not implement modern `q3map_lightmapSampleSize`, and a
`-samplesize` light probe waits at zero CPU instead of changing the atlas.

The corrected source excludes exactly 4,320 alpha-detail sides from the
lightmap atlas: 2,904 foliage-card sides and 1,416 chain-link-panel sides.
Fence posts and every opaque architectural, machinery, vehicle, furniture,
cover, and support face retain baked lighting. Static validation enforces the
exact count and material allow-list. Renderer-supported constant tint keeps
the two alpha materials deliberately dark when no lightmap is present.

That targeted change reduced the compiler allocation to 194 pages but did not
clear the hard gate. Adding a shader-level `nolightmap` flag to already
allocated glass changed neither the 194 pages nor MOHlight's result, proving
that page ownership lives in each draw surface's allocation fields.

Revision 4 therefore adds a deterministic post-VIS BSP 19 atlas repacker. It
preserves all 42,815 baked-surface rectangles and their original dimensions,
globally skyline-packs them with a one-pixel gutter, updates each draw
surface's page/X/Y, and translates its owned draw vertices' normalized
lightmap UVs by the exact placement delta. It reduced 194 pages to 166 without
removing baked lighting from opaque detail. The BSP inspector verifies both
the allocated and written page counts before and after MOHlight.

See [`REVISION-4.md`](REVISION-4.md) for the complete evidence and visual
regression matrix.

## Local CS2 topology pilot

Revision 5 adds an opt-in, local-only path that replaces selected conservative
brush stand-ins with their actual CS2 Nuke topology and base-color textures.
The public revision-4 MAP and PK3 remain redistributable and unchanged. Valve
mesh and image bytes are never committed or published.

The pilot retains topology from 12 map-embedded world aggregates: the
forklifts, outside cargo cranes, B-site reactor head, industrial catwalk and
support, control-room tables, and merge-safe control-display geometry. The two
catwalk resources are combined, yielding 11 model assets: ten static-lit plus
one runtime-lit control-room table. Twenty-three covered Source 1 proxy
placements are suppressed only when the replacement is present. The local MAP
retains 9,407 world brushes, all four rotating doors, and the complete 16/16/32
Axis/Allied/neutral spawn set.

The conversion is geometry-backed rather than bounds-backed:

- ValveResourceFormat exports each allow-listed CS2 `vmdl_c` to GLB.
- The converter applies the complete glTF node transform and maps VRF's
  metre/Y-up coordinates back to Source/MOHAA units and Z-up.
- It emits retail SKD v5, SKC v13, and TIKI files with one static root bone,
  splits surfaces below the original 1,000-vertex/2,000-triangle limits, and
  writes the collapse arrays required by the original Q3map loader.
- It converts only referenced base-color images to local TGA files.
- For a combined model, it resolves each material image relative to that
  material's exact source GLB and rejects conflicting pixels for one shader.
- Lossless welding shares only identical position/normal/UV vertices.
- Original MOHlight lights the final ten-static-model, 71,507-vertex set; the
  5,226-vertex table remains present as a stock-compatible `script_model`.
- Runtime aggregate vertices are recentered around their source bounds and the
  entity is placed at that world origin, so OpenMoHAA samples its light grid
  near the model rather than at map origin.
- The generated precache script caches each runtime manifest model exactly
  once; an isolated OpenMoHAA probe loaded the table, generated Recast, and
  admitted a bot without a source-model load or precache diagnostic.

A separate safe-extended proof, run before the two catwalk resources were
combined into one TIKI, loaded 15/15 pilot-plus-roof-HVAC model definitions.
That historical proof caught and excluded the large airduct aggregate: its 224
retail-safe mesh splits exceed the original TIKI parser's fixed 24-surface
setup array. The converter now fails that case explicitly until multi-model
partitioning is implemented.

A wider identifier-only inventory found 806 Nuke model resources, including
352 `agg_merge`, `agg_nomerge`, and `agg_prop` world aggregates. Ten additional
high-impact world-aggregate candidates were conversion-probed. Tank-top,
ventilation-exhaust, office-desk, metal-ladder, window, and secondary-airduct
sets all stayed within the 24-surface limit and loaded together as six unique
origin-zero BSP static models in original Q3map. Both silo sets, the office-
chair set, and the large roll-up-door set require 25, 27, 41, and 53 surfaces
respectively and remain partitioning debt. These are measured next-pass
candidates, not part of the current 11-model manifest.

Original MOHlight 1.48 has a separate cumulative static-vertex buffer limit.
An 11-model/75,555-vertex proof passed at 228,513 bytes, while the complete
81,002-vertex set crashed. Twelve lightweight definitions passed, disproving a
simple model-count limit. The builder now rejects more than 75,000 statically
lit vertices before long Q3map. Q3map `-onlyents` cannot change static/runtime
classification because it leaves static-model lumps stale; use a full Q3map
pass.

`agg_merge` and `agg_nomerge` resources in this pilot contain world-space
vertices and are placed at origin zero. `agg_prop` resources are deliberately
excluded: their vertices are instance-local and require a still-unimplemented
Source 2 instance-transform reconstruction. Existing brush/clip geometry
remains collision authority, so no approximate model collision is added.

See [`REVISION-5.md`](REVISION-5.md) and
[`tools/cs2-nuke-topology-allowlist.json`](tools/cs2-nuke-topology-allowlist.json).

## Current validation

- Deterministic MAP: 8,195,795 bytes; SHA-256
  `5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040`.
- Static validation resolves all 22 custom materials, balances all 710
  autocombines as omitted, requires at least 1,900 fidelity instances and
  2,800 fidelity brushes, rejects aggregate fill, gates all four doors and the
  complete spawn set, and verifies the exact alpha-lighting policy.
- Canonical Q3map: 50,669 input faces, 47,591 output faces, 3,078 removed,
  5,285 seconds, and empty stderr.
- Fast VIS: 154 clusters, 283 portals, 3,704 visibility bytes, one second, and
  empty stderr.
- Alpha-only MOHlight candidate: correctly rejected at 194 allocated pages.
- Lossless atlas repack: all 42,815 baked surfaces retained; 194 pages reduced
  to 166 with one-pixel gutters.
- Final MOHlight: succeeded in 1,581 seconds with empty stderr. Twenty-eight
  entity-light leaves were clamped to the retail maximum of 60 lights; this is
  recorded density debt, not a BSP/lightmap failure.
- Final BSP: version 19, 47,615 draw surfaces, 166 allocated/written lightmap
  pages, 31,236,136 bytes, and SHA-256
  `675E457505389837F6F2BAA99B44A818701BA3BB9D9E68380E9D689556E2CA95`.
- Exact isolated 26-entry PK3: OpenMoHAA parsed the BSP in 0.158-0.166 seconds,
  generated Recast in 16.404-17.370 seconds across three match cycles,
  admitted eight bots per cycle, logged 263 combat/death events, and emitted
  zero fatal markers.
- Fifteen fixed-camera frames were generated in the exact-package client. The
  usable views confirm the filled Outside/yard silhouette and lower-site
  crane/platform/equipment layer; obstructed camera placements, the
  provisional sky, and conservative blocky substitutes remain human-review
  debt rather than claimed pixel-perfect fidelity.

Revision 3 remains a smaller safe fallback, while revision 4 remains the
current redistributable compiled, packaged, and bot-proven candidate.

### Local CS2 pilot validation

- Original Q3map completed in 5,572 seconds, produced 47,329 output surfaces,
  and emitted only the expected ten animation downgrades and ten optional
  model-collision-helper warnings.
- VIS produced 154 clusters, 283 portals, and 3,704 visibility bytes.
- The lossless atlas repack retained 42,559 lightmapped surfaces and reduced
  192 allocated pages to 165.
- Original MOHlight completed in 4,749 seconds, lit all ten static Source2
  models / 71,507 vertices, and reported zero vertices in solid leaves.
- The final runtime table origin was applied entity-only; all 27 non-entity
  BSP lumps remained byte-identical.
- Final local BSP: 31,279,504 bytes; SHA-256
  `150E6E27A3969493706130C82591E27E346E52CB7426D8F3F490CB207F9A7CF0`.
- The deterministic 70-entry local PK3 reproduced twice at 14,877,947 bytes;
  SHA-256
  `5391F57425E3E27F271876F90E42433EF58DE369A3B11F23D8A2B379DE2B7C0D`.
- In an exact seven-retail-pack-plus-candidate root, OpenMoHAA completed two
  map cycles and two Recast builds, admitted eight bots per cycle, and logged
  154 combat/death events with zero candidate-specific Source2 model,
  runtime-table, fatal-map, or precache diagnostics.

Revision 5 is therefore a compiled and bot-proven local enhanced candidate.
Human screenshot comparison and collision-feel review remain required before
visual fidelity is accepted.

## Rebuilding derived inputs

Run from the repository root with legally obtained local CS:GO files:

```powershell
node generated/codex_nuke/tools/audit_nuke_reference.js `
  --vmf "path\to\de_nuke_d.vmf" `
  --vpk "path\to\csgo\pak01_dir.vpk" `
  --bsp "path\to\csgo\maps\de_nuke.bsp" `
  --out generated/codex_nuke/reference-audit.json

node generated/codex_nuke/tools/build_nuke_fidelity_manifest.js `
  "path\to\de_nuke_d.vmf" `
  generated/codex_nuke/reference-audit.json `
  generated/codex_nuke/fidelity-manifest.json

python generated/codex_nuke/tools/build_original_textures.py
```

These tools commit only derived facts and original project art. They do not
extract Valve assets into the repository.

### Building the local CS2-enhanced variant

With a legally obtained local CS2 installation:

```powershell
powershell -ExecutionPolicy Bypass `
  -File generated/codex_nuke/tools/extract_cs2_nuke_assets.ps1 `
  -Cs2Root "path\to\Counter-Strike Global Offensive" `
  -DownloadVrf

powershell -ExecutionPolicy Bypass `
  -File generated/codex_nuke/tools/build_cs2_nuke_local.ps1 `
  -Vmf "path\to\de_nuke_d.vmf" `
  -RetailRoot "path\to\Allied Assault" `
  -Threads 4
```

The extractor pins ValveResourceFormat 19.2 by archive and executable SHA-256.
The build requires a retail Allied Assault root containing `main/Pak0.pk3`
through `main/Pak6.pk3`; it stages hard links (or copy fallbacks) inside the
ignored compiler root so stock common, clip, origin, and sky shaders resolve.
The enhanced build is written below ignored `.local-source2`, and its local
package is `generated/codex_nuke/codex_nuke-source2-local.pk3`. Do not commit,
publish, or redistribute that package. A custom `-LocalRoot` is accepted only
outside the Git worktree; inside the worktree, the exact ignored
`.local-source2` directory is mandatory. Use `-PrepareOnly` to regenerate and
validate the staged MAP/models/textures without compiling. Use `-PreflightOnly`
to add the retail-pack Q3map resolution proof while still avoiding the long
full BSP/light compile. Both modes enforce the 75,000 static-vertex budget.

## Regenerating and compiling

```powershell
node generated/codex_nuke/tools/generate_nuke.js `
  "path\to\de_nuke_d.vmf" `
  generated/codex_nuke `
  codex_nuke

node generated/codex_nuke/tools/validate_nuke_build.js

Q3map.exe -threads 4 -gamedir "path\to\retail-stage" -moddir main `
  "path\to\retail-stage\main\maps\dm\codex_nuke.map"

Q3map.exe -vis -fast -threads 4 -gamedir "path\to\retail-stage" -moddir main `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp"

Copy-Item `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp" `
  "path\to\retail-stage\main\maps\dm\codex_nuke-pre-repack.bsp"

node generated/codex_nuke/tools/repack_nuke_bsp_lightmaps.js `
  "path\to\retail-stage\main\maps\dm\codex_nuke-pre-repack.bsp" `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp"

node generated/codex_nuke/tools/inspect_nuke_bsp.js `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp" `
  --require-revision-4 --allow-unlit

MOHlight.exe -threads 4 -gamedir "path\to\retail-stage" -moddir main `
  "path\to\retail-stage\main\maps\dm\codex_nuke.map"

node generated/codex_nuke/tools/inspect_nuke_bsp.js `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp" `
  --require-revision-4

powershell -ExecutionPolicy Bypass `
  -File generated/codex_nuke/tools/package_nuke.ps1
```

## Playing

Copy [`codex_nuke.pk3`](codex_nuke.pk3) into the game's `main` directory:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map dm/codex_nuke
```

## Artifact fingerprints

- MAP: 8,195,795 bytes; SHA-256
  `5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040`
- derived fidelity manifest: 2,931,826 bytes; SHA-256
  `F232A9DC88703F7A09446DAB2650FDBA51C21BF139F8C4123EF2652C323976C4`
- texture contact sheet: 837,518 bytes; SHA-256
  `A663EC4E7A9CDCF94C797B35075CDFB508E5543C665206B63E3D9D86A21A4C62`
- BSP: 31,236,136 bytes; SHA-256
  `675E457505389837F6F2BAA99B44A818701BA3BB9D9E68380E9D689556E2CA95`
- PK3: 9,567,575 bytes; SHA-256
  `214F0EAD023D754F5FA199A9C9F8E5A66E6C0AC9F89EF0A6DA6B53A1834E067F`