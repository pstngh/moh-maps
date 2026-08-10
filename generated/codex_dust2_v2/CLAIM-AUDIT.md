# codex_dust2_v2 revision 10 claim audit

Audit date: 2026-08-10

Status: `candidate`; not accepted; not an accepted baseline

This is a bounded evidence audit of the tracked README, conversion report,
generator provenance, package, compile logs, exact-package runtime evidence,
visual captures, Git history, and recorded user feedback. It does not create,
compile, package, or repair a map. Labels use the repository vocabulary:
`PROVEN`, `OBSERVED`, `HYPOTHESIS`, `OPEN`, `REJECTED`, and `SUPERSEDED`.

## Evidence identity

The repository was at commit
`0889c65f845410392f2888b238d691bfb7ce7f71` before this audit.

Tracked candidate identity:

- PK3: 1,550,872 bytes; SHA-256
  `9B113BC0A20B26A2DFD7E89AAC56AA87712E76B37FBA2D9246968EE43686DDA9`.
- Packaged BSP: 6,111,568 bytes; SHA-256
  `05E0F1E96B2ABA73F2326330A42F6CD3D30D19599E6BB44E039925AA994CE442`.
  It is byte-identical to the BSP beside the audited compile logs.
- Editable map: 2,763,453 bytes; SHA-256
  `BBFD2BD7A65E58C10AA6A003CDB89319A3A99C95E669C8A78F8B189EAC4AFF14`.
- Pre-audit README payload: SHA-256
  `F9395E6E0BD6DC8AF157E473C3F0C51EEAE6E4462BA1255895E125E803DA8BCB`.
- Conversion report: SHA-256
  `ECAE62CBBE1C4079CD68EBF21A790BDA0A9B88A1292327885E0A28B825A76B68`.
- Generator: SHA-256
  `BDFB052136B99DDCFD1B79CE000D1EF61163186D7DF639E06889D94E217E0D4B`.
- VMF analyzer: SHA-256
  `BE014F324FE778BD274357B082C6C13E78E59194959B65DF079B28EF9D422D09`.
- Packaging script: SHA-256
  `3E86FDF32D446B1E1BB3DFF7D0CEAF3A6C4C4CB4C0ED8CB01B34DEBAF7617FFE`.

Untracked local evidence used only by exact hash or content identity:

- Reference `de_dust2_reference.vmf`: 7,065,309 bytes; SHA-256
  `05482EB1AB0702B22E40A015D1D2096763F302B83BBAD4C535F6CFA247668D38`.
- `../generated_dust2_v2/q3map-bsp.log`: SHA-256
  `42E6BE58EA8D18AA973F5EC5DCB77E9DE9618692D3037C185DCC9CEE3BC00834`.
- `../generated_dust2_v2/q3map-vis.log`: SHA-256
  `DD1E6813E7DE2B40FEB3375F6A51D20B78B48789AE82616B564736B94A68C8D6`.
- `../generated_dust2_v2/mohlight.log`: SHA-256
  `923B0A22805D1AC9416AD23F4D79480A62B22A64F0638971D8CE351501E0CB0F`.
- `../visual_v18/main/qconsole.log`: SHA-256
  `1CB16216CA7BB2BCD4EDDA6158885A60ACDCBDEB5BC6F184E45976A996B63308`.
- `../visual_v18/main/qa_cycle.cfg`: SHA-256
  `217D263AF533D0EF30B8D6E2E7B786B78300EBF8A764D0FFF31FC44E3A84BECD`.
- `../visual_v18/contact.png`: SHA-256
  `75FD11438E3157D7EB4C1A17FDEA08603B1488C947BDF3DC700E370D3EB58473`.
- The bootstrap request recording comparative but non-final user feedback is
  26,932 bytes; SHA-256
  `13DFA127F712F4C1483F1CAB44185DF10618C2FBDB74F4B9909971648FA44824`.

The external paths above are workspace-local, not repository evidence. Their
hashes prevent a similarly named file from silently substituting for the
audited evidence.

## Claim ledger

| Label | Significant README claim | Audit result |
| --- | --- | --- |
| `PROVEN` | The tracked directory contains editable map/scripts, analyzer, converter, conversion report, packaging script, and PK3. | Git and file inspection establish presence. The PK3 contains only the BSP and two map scripts. No VMF, Source material, or Source model path is tracked, and the reference VMF is not packaged. This proves repository/package contents, not third-party licensing outside them. |
| `PROVEN` / `OPEN` | Ordinary brush planes and spawn coordinates preserve the reference. | A read-only set comparison proves all 20 terrorist origins equal the 20 Axis origins, all 20 counter-terrorist origins equal the 20 Allied origins, and their 40-origin union equals the deathmatch spawns. The generator visibly consumes VMF planes, but a complete independent source-to-output plane equivalence audit was not performed; that broader part remains `OPEN`. |
| `PROVEN` | The build contains 2,330 brushes, 296 patches, and 120 entities. | Independent textual counts in the tracked map agree with the report. These are structural counts, not proof of correctness, fidelity, sealing, or playability. |
| `PROVEN` / `OPEN` | Sixty-one displacement faces became 296 meshes with 6,944 source-grid and 3,480 skirt triangles, without void seams. | The tracked generator and its generated report contain these transformations and counts. The independent analyzer finds 69 displacement sides in the whole VMF; the converter records exclusions and 61 rebuilt sides. No independent triangle-by-triangle equivalence or mapwide seam/void inspection exists, so the quality guarantee remains `OPEN`. |
| `PROVEN` / `OPEN` | Supports, hulls, cover, backings, and skirts seal terrain and provide collision. | Generator branches and emitted structures prove implementation. The exact runtime produced 120 `CM_GridPlane unresolvable` warnings and one mixed-plane-side warning. Their gameplay impact and mapwide sealing/collision quality remain `OPEN`. |
| `PROVEN` / `OPEN` | Four cars were ground-snapped; eight palms and one wagon were placed; stock model bounds make collision valid. | Generator/report counts and MOHlight's 13-model list establish emitted placements and lighting. Ground contact and collision behavior were not measured against authoritative model bounds or mapwide human views, so those behavior claims remain `OPEN`. |
| `PROVEN` / `OBSERVED` / `OPEN` | The listed sun, ambient, and light values produce directional Mediterranean daylight with readable interiors. | The tracked map/generator contain the listed worldspawn values and 25 source-derived light entities. Exact-hash screenshots show daylight and directional contrast in the sampled exterior routes; one sampled interior is very dark. Mapwide lighting readability and quality remain `OPEN`. |
| `OBSERVED` / `OPEN` | Earlier playtests found floating props, nodraw rectangles, gaps, voids, dark interiors, and flat lighting, and the listed repairs corrected them. | Git history proves six successive repair/relight commits and older workspace captures record iteration. The exact candidate has only bounded follow-camera evidence, so "all corrected" is not established mapwide. |
| `PROVEN` | Q3map, VIS, and MOHlight completed with the README's technical counts. | The exact packaged BSP matches the compiled BSP. Logs record 7,036 faces from 7,551 inputs, 599 clusters, 1,913 portals, 2,326 VIS faces, average 547 visible clusters, and 13 lit models. Q3map/VIS record no leak, invalid-brush, warning, or error diagnostic. MOHlight completed with 58 potential-hash-mismatch warnings. This proves tool execution and recorded outputs only. |
| `OBSERVED` | OpenMoHAA loaded 6,740 faces and 296 meshes and built Recast navigation in 3.171 seconds. | `visual_v18` contains the exact candidate PK3 hash, and its console records those values. The same run records collision-plane and missing-asset/script diagnostics. Runtime loading does not prove visual, gameplay, or acceptance quality. |
| `OBSERVED` / `OPEN` | Eight bots navigated and fought successfully. | The exact-hash console records combat involving bot1 through bot8 and 14 bot kill events. It also records seven failures to load `global/bot_run.scr`; the capture script follows players by toggling `+use`. Combat is `OBSERVED`, but successful mapwide navigation, route coverage, fairness, and sustained play remain `OPEN`. |
| `REJECTED` / `OPEN` | Two eight-viewpoint lighting passes covered open areas, interiors, arches, tunnels, and high angles after the current package was rebuilt. | The exact candidate has one eight-screenshot `visual_v18` spectator-follow cycle. The adjacent v16 and v17 runs contain different BSP hashes, so they are not additional passes over this candidate. The exact run is not a fixed player-height/high-angle sweep. The two-pass and high-angle coverage claim is `REJECTED`; mapwide visual coverage remains `OPEN`. |
| `SUPERSEDED` | "Corrected final build" implies final, accepted, polished, or release-ready status. | "Final" is only a historical build label. The authoritative bootstrap request says feedback was comparatively positive but forbids full acceptance without explicit final approval. No revision/hash-linked original feedback or explicit approval was found. Status remains `candidate`; `accepted_baseline` remains null. |

## Acceptance and reuse decision

Revision 10 remains the latest candidate because it has exact-hash technical and
bounded runtime evidence plus a comparative, non-final user-feedback summary.
It is not accepted and must not be used as a proven visual/construction baseline.
Compile success, Recast generation, bot combat, and eight screenshots cannot
promote the open fidelity, collision, mapwide visual, gameplay, or acceptance
claims.

Before promotion, evidence must identify this exact PK3 (or a newer exact
candidate), include full-resolution player-height and deliberate high-angle
coverage of all major routes/boundaries/interiors, record collision and
route-coverage testing, and contain explicit user approval of that exact
candidate.
