# Codex Inferno

> **Current status: revision 5 technically validated measured structural-prop
> fill candidate; human visual review still required.**
>
> Revision 4 is the first user-recognized geometry baseline. Revision 5 keeps
> every accepted brush and restores high-impact windows, shutters, doors,
> arches, roof detail, supports, cover, the B fountain, and the CT well from
> measured Source model bounds. It does not package Source assets.

`codex_inferno` targets Allied Assault BSP 19 and OpenMoHAA DM/TDM. The private
Source VMF supplies brush geometry and entity transforms; private BSP/VPK model
headers supply local hull metadata. The package uses original project-owned
diffuse textures and stock AA sky/utility shaders. It contains no Valve texture,
model, sound, radar, VMF, BSP, VPK, or embedded-pak bytes.

## Revision 5 inventory

- all 5,696 revision-4 world brushes preserved byte-for-byte, including 5,533
  directly reconstructed playable Source solids;
- 6,200 playable prop candidates evaluated and all resolved to one of 308 parsed
  model-bound records;
- 1,176 high-impact instances restored with 1,431 authored substitute brushes;
- 5,024 irregular, foliage, wire, vehicle, and cosmetic props explicitly
  omitted;
- 202 windows, 87 shutters, 99 doors, 65 frames, 46 arches, 69 roof pieces,
  202 pillars, 70 chimneys, 191 wood supports, 47 balcony supports, 90 cover
  props, and four landmark assemblies;
- facade/roof/detail substitutes non-solid; only measured cover and simple
  landmark bodies collide;
- 1,969 displacement-bearing sides retained as planar faces;
- distant 3D skybox and 632 associated brushes excluded;
- 55 clustered practical lights from 75 playable candidates;
- one verified rotating door translated to `func_rotatingdoor`;
- 20 Axis, 20 Allied, and 67 neutral DM spawns;
- 7,127 output world brushes and thirteen used original texture roles.

The canonical machine-readable records are
[`codex_inferno-conversion-report.json`](codex_inferno-conversion-report.json)
and [`inferno-model-bounds.json`](inferno-model-bounds.json). See
[`REVISION-5.md`](REVISION-5.md) for build/runtime evidence and
[`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md) for the private-source audit.

## Install and play

Copy `codex_inferno.pk3` into the game's `main` directory, then run:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 4
map dm/codex_inferno
```

## Regenerate

Revision 5 requires the private decompiled VMF and the compact committed model
manifest. From the repository root:

```powershell
python generated/codex_inferno/tools/build_original_textures.py

node generated/codex_inferno/tools/generate_inferno.js `
  "path/to/de_inferno_d.vmf" `
  generated/codex_inferno `
  codex_inferno

node generated/codex_inferno/tools/validate_inferno_build.js
```

To reproduce `inferno-model-bounds.json` from private inputs, first run
`audit_inferno_reference.js` with the VMF, BSP, VPK directory, and game root,
then pass its full JSON audit to `build_inferno_model_bounds.js`. The compact
manifest stores only paths, counts, hull bounds, header versions, and source
fingerprints; it was reproduced byte-for-byte in a second clean audit.

Before compiling, copy the exact generated MAP and all authored textures to a
clean Allied Assault root containing retail Pak0-Pak6, then gate stage parity:

```powershell
powershell -ExecutionPolicy Bypass `
  -File generated/codex_inferno/tools/verify_inferno_compile_stage.ps1 `
  -StageRoot "retail-stage"
```

Compile and package:

```powershell
Q3map.exe -notjunc -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

Q3map.exe -vis -fast -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

MOHlight.exe -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

powershell -ExecutionPolicy Bypass `
  -File generated/codex_inferno/tools/package_inferno.ps1
```

The `-notjunc` fallback preserves measured architecture but leaves possible
T-junction seam debt. Missing-image warnings are a failed visual build even if
Q3map emits a BSP, because fallback image dimensions may bake incorrect UV
scale.

## Validation evidence

- source regeneration reproduces the MAP, scripts, and conversion report
  byte-for-byte;
- the model-bounds manifest reproduces byte-for-byte from a second private
  audit;
- static revision-5 validation passes with no failures;
- the first 5,696 brush blocks have the same normalized SHA-256 as revision 4;
- corrected `-notjunc` BSP: 33,439 faces from 37,116 inputs, 3,677
  removed, 3,841 seconds, and no warnings or stderr errors;
- fast VIS: 49 clusters, 400 visibility bytes, and 49 clusters visible on
  average;
- full MOHlight: 339 seconds with no warnings or stderr errors;
- Q3map `-info`: 6,971 brushes, 33,445 draw surfaces, 108 lightmaps, 55 entity
  lights, and 16.55 MB against the old nominal 10.00 MB display;
- exact 19-entry PK3 OpenMoHAA load: BSP parse 0.127 seconds, Recast 5.444
  seconds, all eight bots admitted, 22 combat/death events, and zero fatal map
  errors.

## Known debt and next gate

Revision 5 is evidence-backed but not visually accepted. It retains planarized
Source displacements, excludes the distant 3D skybox, uses conservative brush
stand-ins rather than copied meshes, and deliberately omits 5,024 lower-value
props. Decorative door substitutes are non-solid; only the one genuine Source
door entity is interactive. `-notjunc` may leave cracks or seams. The valid
BSP is 6.55 MB above the old nominal display and therefore carries explicit
optimization debt.

The next decisive evidence is a new user screenshot set from T, Mid,
Apartments, A, CT, Banana, B, and a high overview. Verify filled facades,
landmark scale, roof/support placement, cover grounding, ghost doors, route
clearance, and remaining holes. Do not claim those visual defects fixed from
metadata or bot success alone.

## Artifact fingerprints

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| model-bounds manifest | 96,951 | `D4B93C2D3ACA66F9EBDB94061026C406A7925DD9E0A6BE5725E5C91635C678F7` |
| MAP | 5,628,234 | `2CC04B81668A37FE5DC17CFA3E5CB747341131FC8E0011C3F53465C944D05A2C` |
| BSP | 19,090,376 | `44F97DD9B9A522135C574D3C58A12E17731B7A93A3DED91FF78C5919BA421BB5` |
| PK3 | 7,863,439 | `B6120CACB1645A74930E4C32BE0068A23772BA8C4FD89F18D674847C319BBDF0` |

The private VMF SHA-256 is
`C37A3D3CB4EA813B0CC1B36205234A9F9CCFF258B7D69FBA8CA5C448628505D5`.