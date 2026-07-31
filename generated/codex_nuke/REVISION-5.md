# Nuke revision 5: unlit-surface rendering repair

## Identity

- Map: `codex_nuke`
- Revision: 5
- Date: 2026-07-31
- Commit before work: `1b5ce3fa43344067b8f80c04703d6f3debc6e146`
- Goal: remove the revision-4 regression in which chain-link panels, foliage
  cross-cards, and window backings render arbitrary wrong textures in the
  user's runtime.
- User evidence: eighteen in-game screenshots (`shot0011`-`shot0028`) taken on
  the exact revision-4 package.
- Compatibility target: retail Allied Assault BSP 19 and OpenMoHAA DM/TDM with
  4-10 bots.

## Defect inventory

| ID | Location/view | Visible symptom | Confidence |
| --- | --- | --- | --- |
| N5-01 | Outside/yard perimeter, garage, T entrance | Chain-link fence panels render as solid black slabs with bright white smears instead of see-through mesh | Proven in user screenshots |
| N5-02 | Yard, roofs, map edge | Foliage cross-cards render as black/white crosses or as unrelated game textures, including character-skin and vehicle-skin images | Proven in user screenshots |
| N5-03 | Control room and offices | Window backings show the engine's console character set mirrored across the pane | Proven in user screenshots |
| N5-04 | Interiors, lit architecture, machinery, ramps, rails | Correctly textured and lit | Confirms the fault class is narrow |

## Diagnosis

The broken families are exactly the draw surfaces that revision 4 shipped with
`lightmapNum = -1`:

| Shader | Unlit draw surfaces in the revision-4 BSP |
| --- | ---: |
| `textures/codex_nuke/chainlink` (panels) | 1,408 |
| `textures/codex_nuke/foliage` (cards) | 2,904 |
| `textures/codex_nuke/window_backing` | 435 |
| `textures/sky/m5l2` (legitimately unlit) | 53 |

Three facts isolate the cause:

1. The 423 lightmapped chain-link surfaces (fence posts) using the very same
   shader and texture render correctly in the same screenshots, so the
   texture, the shader file, and the atlas repack are not the fault.
2. The garbage differs per surface and per view — a stale lightmap page on
   fences, the console character set on windows, character/vehicle skins on
   foliage — which is the signature of undefined texture binding, not of one
   wrong asset.
3. Revision 3 already shipped 171 unlit `window_backing` surfaces; revision 4
   grew the unlit set to 4,747 surfaces across every fence line and bush,
   which is what made the artifact impossible to miss.

Conclusion: the target renderer does not reliably support world faces without
a lightmap. Retail-compiled maps never contain them (MOHlight bakes every
world face; only sky legitimately carries `-1`), so that code path binds
whatever texture state is left over. The revision-4 assumption that a
constant `rgbGen` tint makes an unlit world face safe is disproved by the
screenshots and is retracted.

## Correction

`tools/relight_nuke_unlit_surfaces.js` is a deterministic post-light BSP 19
edit; no recompile is required because the MAP source, geometry, and baked
lighting are unchanged.

1. Append one 128x128 constant-white lightmap page to the lightmap lump,
   growing the atlas from 166 to 167 pages, still below the 180-page retail
   limit.
2. Point every unlit non-sky draw surface (4,747) at that page with a shared
   126x126 rectangle at (1,1) and set each owned draw vertex's lightmap UV to
   the rectangle center.
3. Refuse to run if an unlit surface shares draw vertices with a lit surface,
   is not a planar face, or if the appended page would exceed the 180-page
   limit. Sky surfaces are left untouched.

The shader file is deliberately unchanged. Sampling constant white through
the existing `$lightmap` multiply stage reproduces the intended constant
tints (`0.62` chain-link, `0.68` foliage) exactly, the lit fence posts keep
their baked shading, and `window_backing` never samples the lightmap. Every
world face now takes the same renderer path as every retail map surface.

`tools/inspect_nuke_bsp.js` gains `--require-revision-5`, which includes the
revision-4 gates and additionally fails on any unlit non-sky draw surface. It
fails the revision-4 BSP with count 4,747 and passes the revision-5 BSP with
count zero.

## Validation

Performed in this revision (static, deterministic):

- Byte-precise output diff: only the lump directory, the lightmap lump (one
  appended white page), the 4,747 patched surface records, and their owned
  draw-vertex lightmap UVs differ from the revision-4 BSP; all other lumps
  and the file tail are byte-identical.
- Zero lit surfaces changed; zero patched UVs off-center; zero lit/unlit
  draw-vertex sharing.
- `inspect_nuke_bsp.js --require-revision-5`: 167 allocated and 167 written
  pages, 47,615 draw surfaces, zero unlit non-sky surfaces.
- `validate_nuke_build.js`: zero failures; the MAP source, conversion report,
  and fidelity manifest are unchanged.
- Repacked PK3 carries the patched BSP bit-exactly and the unchanged shader,
  scripts, and 22 textures in the established 26-entry layout.

Not performed in this environment (no retail AA data or game runtime is
available here): Q3map/MOHlight recompile (not required — no source change),
OpenMoHAA isolated-package load, bot/combat cycles, and renderer screenshots.
The user's screenshot pass on this package is the acceptance gate for the
repair, exactly as their revision-4 screenshots exposed the defect.

## Outcome

- Fixed in artifact: the undefined texture binding on chain-link panels,
  foliage cards, and window backings, by construction — those surfaces now
  carry a valid constant lightmap sample.
- Unchanged: geometry, baked lighting on all previously lit surfaces, MAP
  source, shaders, textures, scripts, and the fidelity layer itself.
- Retracted rule: a constant shader tint does not make an unlit world face
  shippable; unlit world faces themselves are the defect.
- Remaining known debt (carried from revision 4): user screenshot review of
  the restored fidelity layer, provisional stock sky, conservative blocky
  substitutes, planarized displacement curvature, 28 clamped light leaves,
  and 710 omitted autocombines.

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| MAP (unchanged) | 8,195,795 bytes | `5DB889B73F2214F3675FA73EAD8412EF8A938623203C43C76FDDF1F476868040` |
| BSP | 31,285,288 bytes | `B4DB8BCD1D07A277F072BC283A82E4E7425F67D4918139455A517FF8F2E4CACA` |
| PK3 | 9,299,991 bytes | `D95D477163C553B050408DA28F609D08720BDDF83B7FF44F2D5BFA320830A59F` |

## Knowledge promotion

- Map README records the revision-5 correction, pipeline step, and new
  fingerprints.
- Research log records the unlit-world-face evidence and diagnosis.
- Playbook replaces the "constant tint makes nolightmap safe" guidance with
  the constant-page relight requirement.
