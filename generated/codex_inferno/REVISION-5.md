# Codex Inferno revision 5

> **Status: technically validated measured structural-prop fill candidate;
> human visual review still required.**

Date: 2026-07-30

## Why this revision exists

The user's `shot0039.tga` through `shot0051.tga` review called revision 4
“much better.” That establishes direct VMF brush conversion as the first
recognizable Inferno geometry baseline. The screenshots also show why it is not
finished: model-heavy facades are hollow, window and door openings are empty,
sites lack cover and landmarks, and roof supports, pillars, trim, and chimneys
are missing.

Revision 5 preserves the accepted architecture and restores only high-impact
model families with measured, original brush substitutes. It does not return
to inferred massing and does not package Valve assets.

## Preserved geometry

The first 5,696 world brush blocks are byte-for-byte identical after normalized
line endings to revision 4. Their shared SHA-256 is
`2B3EB8EC13E6C9B229C842D98E446C22FEE53DA62103C1861233170C4BD56CDB`.
This includes all 5,533 directly reconstructed playable Source solids, the
structural sky shell, and the previously audited clips/supporting geometry.

The known displacement, distant-skybox, lighting, spawn, and dynamic-door
policies therefore remain unchanged:

- 1,969 displacement-bearing sides remain planar;
- 632 distant 3D-skybox brushes remain excluded;
- 55 clustered lights remain derived from 75 playable candidates;
- 20 Axis, 20 Allied, and 67 neutral DM spawns remain translated;
- the one genuine `prop_door_rotating` remains an AA `func_rotatingdoor`.

## Measured prop layer

A reproducible private-source audit resolves all 7,036 model references and all
308 unique IDST version 49 model headers. The committed
`inferno-model-bounds.json` contains metadata only: model paths, reference
counts, local hull bounds, versions, resolution-source labels, and private-input
fingerprints. It contains no model bytes.

| Evidence | Count |
| --- | ---: |
| Playable prop candidates | 6,200 |
| Candidates with parsed bounds | 6,200 |
| Substituted instances | 1,176 |
| Authored substitute brushes | 1,431 |
| Explicitly omitted remainder | 5,024 |
| Output world brushes | 7,127 |

| Restored class | Instances |
| --- | ---: |
| Windows | 202 |
| Shutters | 87 |
| Doors | 99 |
| Door frames | 65 |
| Arches | 46 |
| Roof surfaces/overhangs | 69 |
| Pillars | 202 |
| Chimneys | 70 |
| Wood roof supports | 191 |
| Balcony supports | 47 |
| Gameplay cover | 90 |
| Landmark assemblies | 4 |

Every substitute record persists its source model path, origin, angles, scale,
and emitted brush count in `codex_inferno-conversion-report.json`. Exact
duplicate transforms are zero. All substitutes remain within the audited
playable bounds.

Approximate facade, door, trim, roof, pillar, chimney, and support pieces use
`-surfaceparm solid`, so they cannot close a route. Only measured cover and
simple fountain/well bodies collide. Four duplicate multi-part landmark records
emit zero additional brushes after their shared physical assembly is built.
Strongly tilted, irregular, foliage, wire, vehicle, and cosmetic props remain
omitted.

Decorative static Source doors are visual non-solid substitutes. Only the one
true rotating-door entity is interactive. Human review must identify any
specific decorative door that intersects a playable passage.

## Generator and stage preflights

The first generated candidate joined three brush helpers with a literal `\n`
escape sequence. Q3map reported `Line 51753 is incomplete`. Revision 5 repairs
those helpers and the validator now checks balanced braces, literal escaped
newlines, invalid numbers, model-manifest fingerprints, per-instance brush
sums, and minimum class coverage.

A first full geometry pass then completed in 3,815 seconds with 33,441 faces
from 37,116 inputs and zero stderr errors, but it was rejected before promotion.
The temporary compile root lacked the authored Inferno texture images, producing
thirteen `Couldn't find image` warnings and potentially baking fallback UV
scale. The candidate BSP was discarded. The corrected stage contains all
sixteen canonical TGA files with matching names and SHA-256 values, verified by
`tools/verify_inferno_compile_stage.ps1` before the repeated BSP pass.

## Corrected build and runtime evidence

The corrected 16-texture stage passes exact MAP and texture-name/hash parity.
The release build then completed every technical gate:

- Q3map `-notjunc`: 33,439 faces from 37,116 inputs, 3,677 removed,
  3,841 seconds, and zero warnings/stderr errors;
- fast VIS: 49 clusters, 400 visibility bytes, 49 clusters visible on average,
  zero stderr errors;
- full MOHlight: 339 seconds, zero warnings/stderr errors;
- Q3map `-info`: 6,971 brushes, 49,958 brush sides, 33,445 draw surfaces,
  108 lightmaps, 55 entity lights, and a valid 16.55 MB BSP against the old
  nominal 10.00 MB display;
- exact deterministic 19-entry PK3 loaded in an isolated OpenMoHAA 0.82.1
  runtime backed only by retail Pak0-Pak6;
- BSP parse 0.127 seconds and Recast navigation generation 5.444 seconds;
- all eight requested bots admitted, 22 combat/death events observed, and zero
  fatal runtime map errors.

The bot-test process launched solely for QA was stopped after the sample. The
6.55 MB nominal BSP overage and `-notjunc` seams are explicit optimization debt,
not evidence of a runtime failure.

## Artifact fingerprints

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| model-bounds manifest | 96,951 | `D4B93C2D3ACA66F9EBDB94061026C406A7925DD9E0A6BE5725E5C91635C678F7` |
| MAP | 5,628,234 | `2CC04B81668A37FE5DC17CFA3E5CB747341131FC8E0011C3F53465C944D05A2C` |
| BSP | 19,090,376 | `44F97DD9B9A522135C574D3C58A12E17731B7A93A3DED91FF78C5919BA421BB5` |
| PK3 | 7,863,439 | `B6120CACB1645A74930E4C32BE0068A23772BA8C4FD89F18D674847C319BBDF0` |

The private VMF SHA-256 remains
`C37A3D3CB4EA813B0CC1B36205234A9F9CCFF258B7D69FBA8CA5C448628505D5`.

## Acceptance state

All technical source, compile, lighting, package, navigation, bot-admission,
and combat gates pass. Visual acceptance is pending a new user screenshot set
from the main routes,
A, B, CT, and a high overview. This revision may fill the screenshot defects,
but metadata and runtime success do not prove that claim.