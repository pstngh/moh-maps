# Codex Nuke

`codex_nuke` is a first-playable Allied Assault/OpenMoHAA deathmatch
conversion. Its target is the recognizable classic Nuke layout with a clean
modern industrial art direction, not an Allied Assault or Second World War
reskin.

Revision 1 is compiled and bot-tested. It is ready for the first human visual
and route review, but is not yet a visual-fidelity release.

## Design brief

| Decision | Current answer |
| --- | --- |
| Game target | Allied Assault BSP 19 and OpenMoHAA |
| Modes | DM/TDM first; 4-10 bots |
| Layout source | Measured CS:GO Nuke reference |
| Fidelity target | Layout-faithful, with recognizable industrial silhouette |
| Asset policy | Original bundled art plus stock AA utility shaders; no Valve assets distributed |
| Lighting | Neutral-warm daylight, cool sky fill, clean purposeful interior fixtures |
| Performance | Preserve primary architecture first; budget Source detail and prop replacements deliberately |
| Explicit omissions | Graffiti, logos, warning placards, minor signs, clutter, Source 3D skybox |

## What the audit proved

- The BSPSource 1.4.8 decompile completed without errors.
- The VMF contains 8,039 solids, 48,098 sides, 761 displacement faces, 10,488
  entities, 6,891 static props, and 471 ordinary/spot lights.
- All 121 visible brush materials resolve to VMT files in the local CS:GO VPK.
- All 1,405 referenced model files are locally measurable:
  - 695 ordinary models resolve from `pak01`;
  - 710 generated `autocombine` models resolve from the BSP's embedded pak.
- The 710 embedded models explain why a VMF-only conversion would lose large
  ventilation, façade, trim, and industrial assemblies.
- Nuke contains four real rotating-door entities. Revision 1 recreates all
  four as interactive AA doors instead of silently making them static.
- Geometry centered around Source Y 7,168-12,360 is a separate distant/skybox
  cluster and must not be imported into the playable AA shell.

See [`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) for the evidence and conversion
policy. The machine-readable derived manifest is
[`reference-audit.json`](reference-audit.json).

## First-playable implementation

The deterministic generator:

- converts 5,639 measured playable Source solids;
- planarizes 604 Source displacement faces and adds 632 material-matched seam
  underlays;
- retains two explicit player clips and 86 measured large Source clip volumes;
- reconstructs 638 simple prop footprints from measured model bounds;
- restores the large Nuke silhouette with 34 nonblocking original
  cylinder/frustum brushes for tanks and silos;
- creates four real `func_rotatingdoor` entities with hinge-origin brushes;
- emits 16 Axis, 16 Allied, and 32 neutral DM spawns;
- translates 471 restrained source fixture lights beneath an original
  neutral-warm sun and cool environment fill.

The 710 map-specific Source `autocombine` models remain explicitly omitted.
Their combined bounding boxes are not safe substitutes for their real shapes.

## Original texture palette

The first palette contains fourteen original 512×512 TGA materials:

- painted concrete, blue-painted concrete, smooth floor, and dark concrete;
- blue and gray corrugated cladding;
- asphalt, metal trim, ceiling tile, and metal grating;
- maintained grass and compact industrial gravel;
- alpha-capable glass and chain-link artwork.

Six base surfaces were generated as original raster sources, then made
deterministically tileable and converted into game-ready variants. Precise
prompts and derivation are recorded in
[`ART-PROVENANCE.md`](ART-PROVENANCE.md). A visual QA sheet is
[`texture-contact-sheet.png`](texture-contact-sheet.png).

Valve VMT/VTF/MDL files are read locally only to identify material roles,
dimensions, model bounds, pivots, and repeated placement families. They are
not copied to this repository or the PK3.

## Validation

- Deterministic regeneration reproduced the exact 5,221,665-byte `.map`,
  SHA-256
  `22D39A6E47E657F4F6B2A0FC4E9AD008DB36695E6B2119C13EC219A3C9EA91C0`.
- Q3map compiled 35,149 input faces to 32,140 output faces in 2,115 seconds
  without missing-image, malformed-brush, or fatal warnings.
- Fast VIS completed with 154 clusters, 283 portals, and 3,704 visibility
  bytes.
- Full MOHlight completed in 976 seconds. It reported 15 potential hash
  mismatches and clamped entity-light lists in 33 leaves; those diagnostics
  are open lighting debt.
- OpenMoHAA 0.82.1 loaded the exact 18-entry PK3, generated Recast navigation
  in 10.509 seconds, admitted eight bots, and logged sustained movement and
  combat.
- The lit BSP contains all four `func_rotatingdoor` classnames. A human client
  still needs to verify panel alignment, activation, swing direction, and
  clearance.

See [`REVISION-1.md`](REVISION-1.md) for the full evidence and known debt.

## Re-running the audit

Run from the repository root with legally obtained local CS:GO files:

```powershell
node generated/codex_nuke/tools/audit_nuke_reference.js `
  --vmf "path\to\de_nuke_d.vmf" `
  --vpk "path\to\csgo\pak01_dir.vpk" `
  --bsp "path\to\csgo\maps\de_nuke.bsp" `
  --out generated/codex_nuke/reference-audit.json
```

The audit commits only derived facts. It never extracts or writes Valve
assets.

To rebuild the original TGA palette:

```powershell
python generated/codex_nuke/tools/build_original_textures.py
```

## Regenerating

Run from the repository root:

```powershell
node generated/codex_nuke/tools/generate_nuke.js `
  "path\to\de_nuke_d.vmf" `
  generated/codex_nuke `
  codex_nuke

node generated/codex_nuke/tools/validate_nuke_build.js
```

Compile `main/maps/dm/codex_nuke.map` against a clean retail Allied Assault
installation in this order:

```powershell
Q3map.exe -threads 4 -gamedir "path\to\retail-stage" -moddir main `
  "path\to\retail-stage\main\maps\dm\codex_nuke.map"

Q3map.exe -vis -fast -threads 4 -gamedir "path\to\retail-stage" -moddir main `
  "path\to\retail-stage\main\maps\dm\codex_nuke.map"

MOHlight.exe -threads 4 -gamedir "path\to\retail-stage" -moddir main `
  "path\to\retail-stage\main\maps\dm\codex_nuke.map"
```

Then copy the lit BSP back into this tree and run:

```powershell
powershell -ExecutionPolicy Bypass `
  -File generated/codex_nuke/tools/package_nuke.ps1
```

## Playing

Copy [`codex_nuke.pk3`](codex_nuke.pk3) into the game's `main` directory:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 4
map dm/codex_nuke
```

## Artifact fingerprints

- BSP: 23,422,268 bytes; SHA-256
  `88EB02194D6074C429670E0B3B57E80B4D100043EFC9C3469FC987CE2601F2D4`
- PK3: 7,059,297 bytes; SHA-256
  `3E577D3711C2B3ACFA9D7665D8D7968581C90615071D145C475B221AE71AF014`
- derived reference audit: 1,899,007 bytes; SHA-256
  `427443BC161C5F07D8E440FFA653D4CBFC1DA751BF3C4E17FDD270B12723987D`
