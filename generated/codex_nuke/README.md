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

Revision 5 repairs the revision-4 regression exposed by the user's in-game
screenshots: the 4,747 world faces shipped without a lightmap (chain-link
panels, foliage cards, window backings) rendered arbitrary wrong textures in
the target renderer. Every non-sky world face now carries a valid constant
lightmap sample; see [`REVISION-5.md`](REVISION-5.md).

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

Revision 5 proves the missing final step: the renderer does not reliably
support world faces with no lightmap at all — the user's screenshots show
those faces binding stale texture state (lightmap smears on fences, the
console character set on windows, model skins on foliage cards) while
identically-shadered lit fence posts render correctly. After the final
MOHlight pass, `relight_nuke_unlit_surfaces.js` appends one constant-white
lightmap page (167 total, below the 180 limit) and points every unlit
non-sky face at it. Sampling constant white through the existing `$lightmap`
stage reproduces the intended `0.62`/`0.68` constant tints exactly, so the
shader file is unchanged and lit surfaces keep their baked shading.

See [`REVISION-4.md`](REVISION-4.md) and [`REVISION-5.md`](REVISION-5.md) for
the complete evidence and visual regression matrices.

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
- Revision-4 BSP: version 19, 47,615 draw surfaces, 166 allocated/written
  lightmap pages, 31,236,136 bytes, and SHA-256
  `675E457505389837F6F2BAA99B44A818701BA3BB9D9E68380E9D689556E2CA95`.
- Revision-4 exact isolated 26-entry PK3: OpenMoHAA parsed the BSP in
  0.158-0.166 seconds, generated Recast in 16.404-17.370 seconds across three
  match cycles, admitted eight bots per cycle, logged 263 combat/death events,
  and emitted zero fatal markers. Revision 5 changes no geometry, collision,
  entity, or navigation input, so this runtime evidence carries over; the
  revision-5 package itself has not been runtime-tested yet.
- Revision-5 relight: 4,747 unlit non-sky faces (1,408 chain-link panels,
  2,904 foliage cards, 435 window backings) now reference an appended
  constant-white page; 167 allocated/written pages; byte-precise diff proves
  every other lump and all lit surfaces are unchanged; sky faces stay on the
  dedicated sky path.
- Revision-5 inspector gate (`--require-revision-5`): zero unlit non-sky draw
  surfaces in the shipped BSP; the gate fails the revision-4 BSP with count
  4,747.
- The revision-4 fifteen-frame automated sweep predates the repair. The
  user's next in-game screenshot pass is the acceptance gate for the repaired
  fence, foliage, and window rendering.

Revision 3 remains a smaller safe fallback, but revision 5 is now the current
packaged candidate: revision 4's compiled and bot-proven artifact plus the
deterministic unlit-surface repair.
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

Copy-Item `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp" `
  "path\to\retail-stage\main\maps\dm\codex_nuke-pre-relight.bsp"

node generated/codex_nuke/tools/relight_nuke_unlit_surfaces.js `
  "path\to\retail-stage\main\maps\dm\codex_nuke-pre-relight.bsp" `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp"

node generated/codex_nuke/tools/inspect_nuke_bsp.js `
  "path\to\retail-stage\main\maps\dm\codex_nuke.bsp" `
  --require-revision-5

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
- BSP: 31,285,288 bytes; SHA-256
  `B4DB8BCD1D07A277F072BC283A82E4E7425F67D4918139455A517FF8F2E4CACA`
- PK3: 9,299,991 bytes; SHA-256
  `D95D477163C553B050408DA28F609D08720BDDF83B7FF44F2D5BFA320830A59F`