# Codex Nuke

`codex_nuke` is a first-playable Allied Assault/OpenMoHAA deathmatch
conversion. Its target is the recognizable classic Nuke layout with a clean
modern industrial art direction, not an Allied Assault or Second World War
reskin.

Revision 3 is compiled, full-lit, packaged, and eight-bot tested. It is a
regression-recovery build based on the second 13-image human review. It removes
revision 2's visually rejected inferred beams, rails, ladders, and trim while
retaining the independently supported window, terrain-underlay, sky, glass,
and light-clustering changes. It is ready for another screenshot and
door-interaction pass, but is not a final visual-fidelity release.

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
  ventilation, facade, trim, and industrial assemblies. Their aggregate hull
  bounds do not reveal the mesh's internal topology or run direction.
- Nuke contains four real rotating-door entities. Revision 3 recreates all
  four as interactive AA doors instead of silently making them static.
- Geometry centered around Source Y 7,168-12,360 is a separate distant/skybox
  cluster and must not be imported into the playable AA shell.

See [`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) for the evidence and conversion
policy. The machine-readable derived manifest is
[`reference-audit.json`](reference-audit.json).

## Revision-3 implementation

The deterministic generator:

- converts 5,639 measured playable Source solids;
- planarizes 604 Source displacement faces and adds 632 material-matched seam
  underlays expanded from measured displacement excursion, up to 117 units;
- retains two explicit player clips and 86 measured large Source clip volumes;
- reconstructs 638 simple prop brushes from measured model bounds;
- restores the large Nuke silhouette with 34 nonblocking original
  cylinder/frustum brushes for tanks and silos;
- explicitly omits all 710 BSP-only autocombine placements until actual mesh
  topology or manually verified endpoints are available;
- creates four real `func_rotatingdoor` entities with hinge-origin brushes;
- emits 16 Axis, 16 Allied, and 32 neutral DM spawns;
- clusters 471 Source fixture candidates to 259 purposeful local lights;
- uses stock `sky/m5l2`, a neutral-warm sun, cool environment fill, and low
  ambient instead of the yellow `mohday1` horizon;
- maps black window placeholders to an original non-solid backing material
  and reduces the original glass texture's blue cast and opacity.

All map-specific autocombines and wires stay explicitly omitted. Revision-2
screenshots proved that a combined model's bounding box is only an envelope:
it cannot establish which axes contain geometry, how many runs exist, or where
they sit inside the box. The converted Source brushes and clips remain the
collision authority.

## Original texture palette

The palette contains fifteen original 512×512 TGA materials:

- painted concrete, blue-painted concrete, smooth floor, and dark concrete;
- blue and gray corrugated cladding;
- asphalt, metal trim, ceiling tile, and metal grating;
- maintained grass and compact industrial gravel;
- alpha-capable glass and chain-link artwork;
- a restrained blue-gray window backing for former black placeholder panes.

Six base surfaces were generated as original raster sources, then made
deterministically tileable and converted into game-ready variants. Precise
prompts and derivation are recorded in
[`ART-PROVENANCE.md`](ART-PROVENANCE.md). A visual QA sheet is
[`texture-contact-sheet.png`](texture-contact-sheet.png).

Valve VMT/VTF/MDL files are read locally only to identify material roles,
dimensions, model bounds, pivots, and repeated placement families. They are
not copied to this repository or the PK3.

## Validation

- Deterministic regeneration produced the exact 5,218,048-byte `.map`,
  SHA-256
  `9C9EAB05034C35600547F805348D0C71C1A903A5D527E3776D5AB301417838F4`.
- Static validation resolves all 15 custom materials, balances the complete
  710-autocombine inventory as explicitly omitted, and fails if inferred
  autocombine fills or broad `nolightmap` sides return.
- Q3map compiled 35,149 input faces to 32,140 output faces in 2,077 seconds
  without missing-image, malformed-brush, or fatal warnings.
- Fast VIS completed with 154 clusters, 283 portals, and 3,704 visibility
  bytes.
- Full MOHlight completed in 1,083 seconds. It reported 16 potential hash
  mismatches and clamped entity-light lists in 28 leaves; those diagnostics
  remain open visual-correlation debt.
- OpenMoHAA 0.82.1 loaded the exact 19-entry PK3, generated Recast navigation
  in 9.515 seconds, admitted eight bots, and logged 119 combat events with
  zero runtime errors.
- The lit BSP contains all four `func_rotatingdoor` classnames. A human client
  still needs to verify panel alignment, activation, swing direction, and
  clearance.

See [`REVISION-3.md`](REVISION-3.md) for the screenshot matrix, regression
analysis, rollback evidence, and known debt. [`REVISION-2.md`](REVISION-2.md)
is retained as a technically successful but visually rejected experiment.
Revision-1 evidence remains in [`REVISION-1.md`](REVISION-1.md).

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

- BSP: 23,494,100 bytes; SHA-256
  `F79BF2BDA45CA188A09A2C3D63646E3BEAD8CC1D43D4975685C7E5881B51ED97`
- PK3: 7,093,663 bytes; SHA-256
  `4790A691A592DAA7B6D35DD5BD658E02760EB994EC691152F8601D84D7FFCF63`
- derived reference audit: 1,899,007 bytes; SHA-256
  `427443BC161C5F07D8E440FFA653D4CBFC1DA751BF3C4E17FDD270B12723987D`
