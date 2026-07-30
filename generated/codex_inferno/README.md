# Codex Inferno

`codex_inferno` is an authored-from-scratch Allied Assault/OpenMoHAA
deathmatch map inspired by the classic Inferno circulation graph. It is not a
Source brush conversion: no Valve geometry, textures, models, sounds, VMF, or
BSP content is included.

Revision 1 is compiled, fully lit, packaged, and validated with eight
OpenMoHAA bots. Its first human map-view review is still pending, so it should
be treated as a strong first playable rather than a finished visual replica.

## Design and inventory

- DM/TDM for roughly 2-8 players or bots;
- 20 named connected combat areas across Mid/A, Apartments, CT, and Banana/B;
- 464 world brushes, including 21 complete building masses;
- 71 authored facade windows, 20 flat roofs, and two gable roofs;
- 16 Axis, 16 Allied, and 24 neutral deathmatch spawns;
- eight local interior lights plus warm sun, cool sky fill, and low ambient;
- 16 original 512x512 diffuse textures with exact stored-edge tiling;
- zero imported Source solids, props, or displacements.

The 128-unit occupancy grid defines playable streets. Its complement is merged
into complete building volumes, which prevents omitted Source models from
becoming holes. See [`DESIGN-BRIEF.md`](DESIGN-BRIEF.md),
[`REFERENCE-AUDIT.md`](REFERENCE-AUDIT.md), and
[`ART-PROVENANCE.md`](ART-PROVENANCE.md).

## Regenerating

From the repository root:

```powershell
python generated/codex_inferno/tools/build_original_textures.py
node generated/codex_inferno/tools/generate_inferno.js
node generated/codex_inferno/tools/validate_inferno_build.js
```

The VMF is not needed. It was used only to audit broad route roles, scale, and
the failure risk of a direct conversion.

Compile against a clean Allied Assault root containing retail Pak0-Pak6:

```powershell
Q3map.exe -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

Q3map.exe -vis -fast -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

MOHlight.exe -threads 4 -gamedir "retail-stage" -moddir main `
  "retail-stage\main\maps\dm\codex_inferno.map"

powershell -ExecutionPolicy Bypass `
  -File generated/codex_inferno/tools/package_inferno.ps1
```

Use ordinary Q3map. The authored detail is intentionally emitted into
`worldspawn`; this MOHAA Q3map build stripped ordinary Quake `func_detail`
brush entities during testing.

## Playing

Copy `codex_inferno.pk3` into the game's `main` directory:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 4
map dm/codex_inferno
```

## Validation evidence

- Static validation passes all material, route, spawn, lighting, source-path,
  and no-Source-import assertions.
- Q3map emitted 2,050 faces from 2,052 and wrote a valid portal file.
- Fast VIS completed with 1,127 clusters, 4,086 portals, and 3,725 faces.
- Full MOHlight completed with ambient `8 9 11`.
- The exact 19-entry PK3 loaded from a fresh OpenMoHAA home backed only by
  retail Pak0-Pak6.
- OpenMoHAA 0.82.1-beta+5 parsed the BSP in 0.008 seconds, generated Recast
  navigation in 0.173 seconds, admitted eight bots, and logged 15 combat
  deaths in the final short sample.
- The final run produced zero precache suggestions and zero fatal map-loading
  errors.

The runtime reports an absent optional `global/bot_run.scr` in the stock-only
test environment, but all eight native bots still navigate and fight. This is
not map content and is recorded rather than hidden.

## Known debt

- Human exterior, interior, overview, transition, sightline, and map-edge
  screenshots still need review.
- Visual fidelity is intentionally interpretive; the route graph and landmark
  roles are the target, not one-to-one Source geometry.
- Interior lights in Apartments and Library produced non-fatal Q3map
  leaf-leak diagnostics; all eight light entities remain in the BSP and full
  lighting succeeds.
- Doors are static architecture in revision 1.
- Dense vegetation, signs, graffiti, small clutter, curved displacement
  terrain, and a distant 3D skybox are intentionally omitted.

## Artifact fingerprints

- MAP: 271,270 bytes; SHA-256
  `40A7B86994757E80D127EFEAECA1FA044E0F742DFFF3DDC2A19895625F9A53B6`
- generation report: 1,075 bytes; SHA-256
  `8ED42FAA344A6F0178C44AFB66E396F838006B71B70F4D669F5AF2A8EA2EA543`
- BSP: 1,933,728 bytes; SHA-256
  `F2DECC307875AE9725D991DEE6DD969A818F0F80B8CD99F49C711B788ECBA223`
- PK3: 4,670,179 bytes; SHA-256
  `30FBE96874CC8BB2ECA4C80B047CE67E2FA3E67EE42C5153D99222ACDC82B8A2`
