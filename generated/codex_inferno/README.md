# Codex Inferno

> **Current status: revision 4 direct-VMF playable candidate; human visual
> recognition review pending.**
>
> Revisions 1-3 were visually rejected. Revision 4 discards their inferred
> architecture and directly converts the supplied CS:GO Inferno VMF's playable
> brush solids. It compiles, lights, packages, builds OpenMoHAA navigation, and
> supports sustained eight-bot combat. It is not a visually accepted baseline
> until the user's ground-level and overview screenshots confirm recognition.

`codex_inferno` targets Allied Assault BSP 19 and OpenMoHAA DM/TDM. The private
Source VMF supplies brush geometry, entity coordinates, and broad material
roles. The package substitutes original project-owned diffuse textures and
stock AA sky/utility shaders; it contains no Valve texture, model, sound,
radar, or embedded asset bytes.

## Revision 4 inventory

- 5,533 directly reconstructed Source solids from the playable world,
  `func_detail`, `func_brush`, and `func_breakable` classes;
- zero invalid reconstructed solids;
- an explicit six-brush structural sky shell, with imported architecture kept
  as colliding/lightmapped worldspawn detail;
- 1,969 displacement-bearing sides retained as planar faces for this first
  direct baseline;
- the distant 3D skybox cluster and 632 associated brushes excluded;
- 1,476 helper-only brushes excluded while verified large/player clips are
  retained;
- 6,200 unverified Source model props deliberately omitted rather than replaced
  with misleading guesses;
- 55 clustered practical lights from 75 playable Source light candidates;
- the one verified rotating door translated to an AA `func_rotatingdoor`;
- 20 Axis, 20 Allied, and 67 neutral DM spawns from the VMF;
- thirteen used original texture roles plus stock AA sky/utility shaders;
- 5,696 output world brushes, 24,639 draw surfaces, and 165 entities.

The canonical machine-readable record is
[`codex_inferno-conversion-report.json`](codex_inferno-conversion-report.json).
See [`REVISION-4.md`](REVISION-4.md) for build/runtime evidence and
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

Revision 4 requires the private decompiled VMF. From the repository root:

```powershell
python generated/codex_inferno/tools/build_original_textures.py

node generated/codex_inferno/tools/generate_inferno.js `
  "path/to/de_inferno_d.vmf" `
  generated/codex_inferno `
  codex_inferno

node generated/codex_inferno/tools/validate_inferno_build.js
```

`generate_inferno.js` and `validate_inferno_build.js` are the stable revision-4
entry points. The older revision-specific generators remain historical
evidence only.

Compile against a clean Allied Assault root containing retail Pak0-Pak6:

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

The documented `-notjunc` fallback preserves the direct architecture but may
leave T-junction crack/seam debt. The ordinary compile was manually stopped
after more than five CPU minutes without a compiler error; it was not treated
as a failed map.

## Validation evidence

- clean temporary regeneration reproduces the MAP, both scripts, and conversion
  report byte-for-byte;
- stable revision-4 validator passes with no failures;
- Q3map `-notjunc`: 24,633 faces from 28,310 inputs, 3,677 removed, 1,910
  seconds, no invalid brushes, leak, or stderr error;
- fast VIS: 49 clusters, 400 visibility bytes, 49 clusters visible on average;
- full MOHlight: 222 seconds and zero stderr errors;
- Q3map `-info`: 5,540 brushes, 24,639 draw surfaces, 82 lightmaps, 55 entity
  lights, and 12.34 MB against the original tool's nominal 10.00 MB budget;
- exact-PK3 OpenMoHAA load: BSP parse 0.097 seconds and Recast generation
  3.858 seconds;
- all eight requested bots admitted and 23 combat/death events observed in the
  recorded sample;
- zero fatal runtime map errors.

The BSP budget is 2.34 MB over the old nominal display. Q3map nevertheless
emitted a valid BSP and OpenMoHAA loaded it successfully. This is explicit
optimization debt, not permission to remove architecture before the visual
recognition gate.

## Known debt and next gate

Revision 4 maximizes architectural fidelity before optimization. It planarizes
Source displacements, omits unverified Source props, excludes the distant 3D
skybox, and maps Source materials to a compact original Inferno palette. Two
nonfatal MOHlight potential-hash-mismatch warnings remain documented in
[`REVISION-4.md`](REVISION-4.md).

The next decisive evidence is a user screenshot set from T spawn, Mid,
Apartments, A, CT, Banana, B, and a high overview. If the direct geometry is
recognizable, optimize by measured class and repair only visible displacement,
prop, material, lighting, door, or seam debt. Do not return to graph extrusion
or inferred village massing.

## Artifact fingerprints

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 4,092,209 | `2B68A264448F674DEE2F852FE99834A0EEBB0748FEBA38DD819002C7C213FB2E` |
| BSP | 14,221,508 | `6B984142E4C687EBC031C035E400619345CDA1FEBE08D06541EC0427196C46D2` |
| PK3 | 7,045,046 | `6F1F9A5568D5C2C2873E8424D6AFF4CAE52F02A1EFD61556778315E7CB6AA441` |

The private VMF SHA-256 is
`C37A3D3CB4EA813B0CC1B36205234A9F9CCFF258B7D69FBA8CA5C448628505D5`.
