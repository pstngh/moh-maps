# codex_cache revision 1 claim audit

Audit date: 2026-08-10

Status: `candidate`; not accepted; not an accepted baseline

This is a bounded evidence audit of the tracked README, revision and reference
records, generator and texture provenance, generated source, package, surviving
compile-stage files, exact-package runtime transcript, bot events, visual
evidence, Git history, and human acceptance record. It does not create,
compile, package, launch, or repair a map. Labels use the repository vocabulary:
`PROVEN`, `OBSERVED`, `HYPOTHESIS`, `OPEN`, `REJECTED`, and `SUPERSEDED`.

## Evidence identity

The repository was at commit
`9BD2FA6C18C0BB5AE69DB075BE401E7A6537D6E7` before this audit.

Tracked candidate identity:

- PK3: 10,127,241 bytes; SHA-256
  `90477F688E4115400813B119A2061434A1F62324381B3CC864FA7BAB29084C53`.
- Packaged BSP: 32,125,316 bytes; SHA-256
  `653AEF5E9AE82FEA5FD68307CD67F1842E424DC611758875CB8EA779E16EE94C`.
  It is byte-identical to the tracked BSP and the surviving BSP in
  `../compile_retail`.
- Editable MAP: 8,482,127 bytes; SHA-256
  `9966961E5C1D52B65D6BBB300699FF24E2EF3BDCBC6B4BB90619ABF8794DBEDC`.
  It is byte-identical to the surviving compile-stage MAP.
- Conversion report: 26,102 bytes; SHA-256
  `FEEEABB1A44FAD14954317973378CBAF9B21A5AC0A6644438A4F5056F889122B`.
- Generator: SHA-256
  `6237616B4B1421E348883FE21C493B5056EB9D2429A360D5B3FC4DCD6AA033D3`.
- Static validator: SHA-256
  `F59F5D584A189048E3F4E929475F9D72C8DBCBCEF3302082C659489D41397A38`.
- Packaging script: SHA-256
  `B8115A70D49B8C1C272B42B8FC0A1DCC1C3727ECBA3D03868AFFABAF5E465661`.
- Texture builder: SHA-256
  `315B847D412DE19A56922556C18EAD7A5BFC6BA0E65F4135A669E47D7A5DAA73`.
- Contact sheet: 850,545 bytes; SHA-256
  `38023560F2AB30795027698400A4C2AE08774A784ADAEA41A77FC45428117CFD`.
- Pre-audit README: SHA-256
  `6917C287DBFF8DAFB01CAAE4B7B9F415199D8666444EB8027A74A31B0CB03DEB`.
- `REVISION-1.md`: SHA-256
  `35B376CAC90522F2A98AEE2E9DA3141D35FCB2E9B91CDC306AD5B768C3759C98`.
- `REFERENCE-AUDIT.md`: SHA-256
  `08717EF20C178BD5CAC06144B0D249A15CA8B56FEB0F6E8ADD355A667B5D0455`.
- `ART-PROVENANCE.md`: SHA-256
  `F4649F276A4591F9D4BC7ADF6FBDD582C81458A08A88669CF04DF9F15727B11E`.

Surviving workspace-local evidence used only by exact hash or content identity:

- `../compile_retail/main/maps/dm/codex_cache.prt`: SHA-256
  `64495FF5F43A9AEDDE2D88063E0034EF68B5C3275C0B51797D5300DF7D312009`.
- `../compile_retail/main/maps/dm/codex_cache.vis`: SHA-256
  `A9F591DB24A213273D2FD310BDA2963DCEDE374E89933E765930C94094880EA7`.
- `../runtime_cache_r1_20260728/main/codex_cache.pk3`: SHA-256
  `90477F688E4115400813B119A2061434A1F62324381B3CC864FA7BAB29084C53`.
- `../runtime_cache_r1_20260728/cache-runtime.stderr.log`: SHA-256
  `D4C95A79FD71F37D12849F3E78B1A5EE12E3541C52426D6DDD29855462087C79`.
- `../openmohaa-bin/runtime/omohaaded.exe`: SHA-256
  `DDB7D12666560701D914FF0D26B5082D686C1CC027407A929FB4950D24FBDAFB`.
- `../openmohaa-bin/runtime/game.dll`: SHA-256
  `7ED4F2CC70B9579F2DF2577B7F2722D5990653131269ECF61074AEB341968EE0`.

The external paths are workspace-local, not tracked repository evidence. Their
hashes prevent a similarly named file from silently substituting for the
audited artifacts.

No `de_cache_d.vmf`, source-VMF hash, raw Cache Q3map/VIS/MOHlight log,
Cache map-view screenshot, fixed-view plan, screenshot hash ledger, or human
playtest/approval artifact was found. The conversion report names only
`de_cache_d.vmf`; it does not bind the generated output to exact reference
bytes. The historical black application frames described in the revision
record do not survive as auditable image files.

## Claim ledger

| Label | Significant claim | Audit result |
| --- | --- | --- |
| `PROVEN` / `OPEN` | Revision 1 is reproducibly generated from a measured Cache reference and preserves its playable brush layout. | The repository tracks the generator, generated MAP, report, texture inputs, validator, package script, and outputs. The current static validator passes. The exact reference VMF is absent and unhashed, so regeneration and independent source-plane/entity equivalence are `OPEN`. "Measured" and "preserves the playable layout" remain unverified source-fidelity claims. |
| `PROVEN` / `OPEN` | The generated inventory contains 10,876 world brushes, 268 entities, 20 Axis, 20 Allied, and 24 neutral spawns, one rotating door, 201 lights, and zero invalid brushes. | Independent MAP parsing and BSP inspection establish the output counts, class counts, resolved materials, and one emitted `func_rotatingdoor`; the validator reports no current failures. Report-only claims about 10,787 retained source solids, 8,165 planarized displacement sides, 83 seam underlays, 138 retained clips, 1,379 skipped helpers, 3,800 excluded solids, and 2,588 source prop omissions cannot be compared to the missing reference and remain `OPEN` as source-fidelity claims. Counts do not prove valid mapwide construction, sealing, collision, or visual quality. |
| `PROVEN` / `SUPERSEDED` / `OPEN` | One verified interactive door preserves the Source door. | The generator emits one measured-bounds brush entity and the BSP contains one `func_rotatingdoor`. Canonical OpenMoHAA source at `a2f340195975f4f042e28a60b62561dd9a0b2700`, `code/fgame/doors.cpp`, registers that classname as `RotatingDoor`. The source VMF/model measurement is not hash-bound, and no exact-hash activation, hinge direction, blocking, alignment, clearance, or human interaction probe survives. "Verified interactive door" is superseded; door behavior remains `OPEN`. |
| `PROVEN` / `OPEN` | The package contains 19 deterministic, edge-verified original textures and no Valve payload. | All 19 committed TGA files are 512 by 512, and an independent read-only pixel check confirms equal stored opposite edges. The PK3 contains those textures and no Valve-named path or Source model/material file. The committed source PNGs and derivation script establish a reproducible project asset chain, but filenames and documentation alone cannot independently prove byte authorship against every external Valve asset. Semantic palette coherence, in-engine material behavior, scale, alignment, and lighting remain `OPEN`. |
| `PROVEN` / `OPEN` | Q3map, fast VIS, and full MOHlight completed with the recorded counts, timings, `-notjunc` fallback, one potential-hash warning, and six light clamps. | The exact compile-stage MAP and BSP survive; the BSP is valid AA BSP 19 with 57,628 draw surfaces, 166 lightmap pages, 456 visibility bytes, and the expected entity classes. The surviving PRT header records 56 clusters and 97 portals. Raw Cache compiler/light logs were not found, so the command line, timings, 57,622 merged-face report, normal-build failure, warning text/count, and six clamps are not independently correlated. The lit output exists, but the broader historical process claims remain `OPEN`. `-notjunc` crack/seam quality is a visual question and remains `OPEN`. |
| `PROVEN` | The exact 23-entry PK3 contains the intended committed payload. | The candidate hash recomputes exactly. Every PK3 member is byte-identical to its committed input; the sole packaged BSP has SHA-256 `653AEF5E...6EE94C`, matching both tracked and compile-stage BSPs. This proves package identity and contents only. |
| `OBSERVED` / `OPEN` | OpenMoHAA loaded the exact package, parsed the BSP in 0.180 seconds, and generated Recast navigation in 3.567 seconds without Cache content/runtime errors. | The surviving isolated runtime copy matches the candidate hash. Its raw transcript names the 23-file PK3 ahead of a base containing only retail Pak0-Pak6, records OpenMoHAA `0.82.1-beta+5.a72bc15`, map initialization, BSP parsing, and Recast generation. A raw diagnostic scan finds fresh-config misses, a stock Allied pilot box warning, and a 4.483-second hitch, but no Cache map/script/package/navigation error. Exact launch arguments and a separate qconsole log do not survive, so launch provenance is incomplete. Loading and Recast do not prove visual or gameplay quality. |
| `OBSERVED` / `SUPERSEDED` / `OPEN` | Eight bots spawn, move, fight, die, and respawn successfully. | The exact-hash transcript records bot1 through bot8 entering, all eight participating in 55 combat/death lines, and concrete deaths. This supports bot entry, combat, and death only. It contains no position samples, explicit spawn/respawn observations, controlled route probes, door-use evidence, or mapwide reachability record. The aggregate checked claim is superseded: spawn, movement, respawn, meaningful route diversity, collision quality, stalls, and fairness remain `OPEN`. |
| `OPEN` | The contact sheet proves a coherent clean industrial palette, and the black application captures establish the map's visual status. | The contact sheet identity and texture edge properties are auditable, but no durable semantic review record accompanies it. The reported black frames are absent and were correctly excluded by the historical document. No exact-hash map-view image survives. Recognition, exterior/interior/transition quality, boundaries, long sightlines, terrain/seam closure, lighting, material roles, door appearance, no-void/no-floating claims, and visual completeness all remain `OPEN`. |
| `OBSERVED` / `OPEN` | "First-playable" or "measured playable baseline" means a recognizable, enjoyable, ready-to-play Cache conversion. | Exact-hash server load, Recast generation, and bot combat establish bounded technical execution. They do not establish human playability, route quality, recognition, fidelity, cover, spawn safety, balance, polish, or enjoyment. "Baseline" is only a historical revision label; this map is not the project's accepted baseline. |
| `REJECTED` | Revision 1 is accepted, final, complete, polished, release-ready, visually complete, or approved. | The proposition is false under project policy: no revision/hash-linked human approval exists, `accepted_revision` is null, and `accepted_baseline` is null. The map remains an unaccepted candidate. Technical success, a quiet map-specific log, and absent criticism cannot promote it. |

## Acceptance and reuse decision

Revision 1 remains a candidate because its exact package identity, compiled BSP,
isolated load, Recast generation, and bounded bot combat survive audit. It is
not a proven visual, geometry, gameplay, door, or construction baseline and
must not be promoted or described as accepted, final, complete, polished, or
release-ready.

The next evidence pass must keep the exact candidate hash or record a new one;
preserve complete engine executable, argument, base/home, package-inventory,
and raw-log provenance; capture unobscured fixed player-height and deliberate
high-angle views of exteriors, interiors, transitions, long sightlines,
boundaries, the door, and likely `-notjunc` seam domains; and instrument bot
spawn, movement, death, respawn, and multiple route probes separately. Human
acceptance remains open until the user explicitly approves that exact tested
candidate.
