# V2 Depot revision 1

## Identity and baseline

- Map/revision/date: `codex_v2_depot` / 1 / 2026-08-08
- Commit before work: `1a80d712c3ae11c83d3e2433aa2b014e4310119c`
- Goal: bot-ready DM/TDM following actual `obj_team2.map` construction grammar without copying its layout
- User evidence: `codex_reactor` was rejected as buggy and messy; technical success alone was not acceptable
- Target: Allied Assault BSP 19 and OpenMoHAA

Reactor's simplified boxes, custom palette, and optimistic automated claims were discarded as a design baseline. The stock source was measured first.

| Measurement | `obj_team2` | V2 Depot |
| --- | ---: | ---: |
| Ordinary brushes / faces | 5,827 / 35,217 | 189 / 1,150 |
| Patches / terrain | 708 / 7 | 0 / 0 |
| Axis boxes / angled brushes | 3,352 / 2,475 | 187 / 2 |
| DM / Allied / Axis starts | 14 / 16 / 16 | 18 / 8 / 8 |
| Lights | 181 | 25 |

The reference supplied proportions, flags, palette evidence, and authoring conventions only. No stock geometry, script body, or asset byte was copied.

## Defects and repairs

| ID | Symptom | Repair |
| --- | --- | --- |
| V1 | Reactor looked like a buggy blockout despite numeric passes | made real-source grammar and actual texture inspection mandatory |
| V2 | three initial spawn origins lacked support/clearance | moved them and added validator gates |
| V3 | 20 optional `corona_orange.map` warnings | used a precached runtime corona; retained proven static lamps |
| V4 | deep hall/service views were too dark | raised ambient/sky/sun and added local hall/rear fill |
| V5 | overview, edge, and rear cameras misrepresented geometry | corrected camera origins/angles without altering MAP/PK3 |
| V6 | visual log read blocked after capture | replaced streaming cmdlet behavior with a finite file snapshot |

## Construction and assets

The stock palette combines bunker concrete, warehouse floor/steps, I-beams, ceiling beams, deck grates, iron/rust, utility boxes, and reinforced crates. Hidden faces default to caulk; visible modules receive face-specific top/front/side materials. Private retail texture contact sheets remain ignored and no custom texture is packaged.

- 189 brushes: 187 six-face boxes and 2 angled cylinders
- 1,150 faces; 424 caulk (36.87%)
- 18 DM, 8 Allied, 8 Axis, 1 start
- 25 lights and 41 stock model placements
- 10 route zones, 15 links, 192-unit minimum
- zero moving doors

## Compile, runtime, and visual evidence

| Gate | Result |
| --- | --- |
| Q3map | 0.668 s; 713 BSP surfaces; zero warnings/leaks/degenerates |
| Fast VIS | 0.210 s; 1,128 visibility bytes |
| Full MOHlight | 4.587 s; 5 pages; zero clamps/hash warnings |
| Exact runtime | BSP 0.003 s; Recast 0.127 s; 8 bots; 23 events/40 s; zero candidate diagnostics |
| Fixed views | yard, west entry, hall, service, rear cross, upper loop, overview, edge; 8 screenshots/markers; zero script errors |

The visual pass repaired dark stacked routes and misleading cameras. It confirmed complete facade/shell views, broad thresholds, readable hall/service circulation, a visible rear passage, grounded central cover, and a connected upper loop. Generation reproduced the 137,984-byte MAP and packaging reproduced the same three-entry PK3 twice.

## Artifacts

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| MAP | 137,984 | `61ee413bd42b3f5646fad77beed3ced395ac60737d0c28ae81fae43879a9aa5d` |
| BSP | 655,120 | `f2a5a2b920bcb418a27b146612455db11014b1b854f809c5abc8f911a48cec30` |
| PK3 | 112,494 | `a46451bc445281079b647817b4bc45ec5137b0fd15a8f16d96b6d059bb826245` |

## Outcome

Fixed: spawn validity, corona warnings, dark routes, and bad regression cameras. Improved: stock construction discipline, palette coherence, lighting hierarchy, route readability, and bot density. Remaining debt: human play must judge fairness, cover, and subjective brightness; user screenshots override this automated first-pass verdict.

- [x] Reproducible source/generator
- [x] BSP, VIS, and full light
- [x] Exact isolated PK3
- [x] Bots spawned, moved, and fought
- [x] Fixed views inspected
- [x] Hashes and debt documented
- [x] Shared knowledge updated
- [x] Commit pushed
