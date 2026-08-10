# codex_cache revision 1 exact-hash evidence checkpoint

Date: 2026-08-10

Status: candidate only; semantic visual review failed; human acceptance remains open; promotion is forbidden.

## Exact identities

- PK3 SHA-256: `90477f688e4115400813b119a2061434a1f62324381b3cc864fa7bab29084c53`
- Packaged and compiled BSP SHA-256: `653aef5e9ae82fea5fd68307cd67f1842e424dc611758875cb8ea779e16ee94c`
- Generated MAP SHA-256: `9966961e5c1d52b65d6bbb300699ff24e2ef3bdcbc6b4bb90619abf8794dbedc`
- OpenMoHAA visual client SHA-256: `2364a08a2c2269504320027fad3354c9504230434aa33ac43e6234c50c630cd6`
- OpenMoHAA dedicated server SHA-256: `ddb7d12666560701d914ff0d26b5082d686c1cc027407a929fb4950d24fbdafb`
- OpenMoHAA `game.dll` SHA-256: `7ed4f2cc70b9579f2df2577b7f2722d5990653131269ecf61074aeb341968ee0`

## Strict audit result

Passing gates: candidate package identity, visual runtime package identity, bot runtime package identity, launch provenance, raw runtime diagnostics, runtime load, fixed-view capture, bot entry/combat, bot lifecycle, and bot route coverage.

Open gates:

- Build provenance: the revision-1 raw compile log is absent, so the surviving MAP, BSP, and PK3 cannot establish a complete source/design/compile/package chain.
- Human acceptance: no explicit user approval of this exact candidate exists.

Failing gate:

- Semantic visual review: four blocking findings are recorded below.

The strict auditor exits `2`, sets `technical_ready_for_human_review` to false, `promotion_allowed` to false, and `acceptance_status` to `requires_explicit_user_approval`.

## Visual evidence

Seventeen ordered, unique, unobscured fixed views cover player-height forward/reverse, high-angle, boundary, interior, exterior, transition, and long-sightline categories. Original 1280x720 TGA captures were converted to repository PNGs; the conversion manifest verifies identical decoded dimensions, color mode, and pixel bytes for every image.

Blocking findings:

1. `mid_transition_reverse`: camera placement abuts or intersects opaque geometry, leaving most of the frame black and preventing assessment of the intended reverse transition.
2. `east_boundary_reverse`: exposed gray exterior or underside shell against open blue space; playable boundary containment is not established.
3. `notjunc_low_south`: open rectangular black floor aperture beside the paved surface.
4. `notjunc_low_west`: long black pavement-to-grass seam plus a triangular open blue/void aperture.

The two rotating-door still views are unobscured, but static images do not prove interaction or collision behavior.

## Runtime and bot evidence

The package-pure dedicated-server lane used exactly the seven retail PK3s plus this candidate. It observed BSP parse completion, Recast generation, all 8 bot entries, and 48 combat events. The raw log's missing stock `global/bot_run.scr` messages are explicitly classified as proven nonblocking for these bounded claims because entry/combat completed and the separate exact-hash instrumentation confirms movement and lifecycle activity; the messages are retained verbatim.

The supplemental instrumentation lane is deliberately labeled not package-pure because it adds one hash-recorded loose script while retaining the exact candidate PK3 and retail package inventory. Across 720 one-second samples it recorded:

- 703 unique sampled positions
- 37 combat events
- 32 live-to-dead transitions
- 32 dead-to-live transitions
- 72 alive-to-alive coarse-zone transitions
- 17 distinct coarse route pairs

The coarse zones are analysis bins, not authored route names or proof of route quality, fairness, absence of stalls, or human playability.

## Rotating-door evidence

The supplemental controlled-door lane is also explicitly not package-pure. It hash-links runtime entity 24 to the source rotating door at origin `(199 2058 1688)`, records 40 samples with zero script errors, and demonstrates bounded `0Ã‚Â° -> 90Ã‚Â° -> 0Ã‚Â°` motion under controlled `doopen`/`doclose` events. This does not prove ordinary human activation, bot-touch activation, clearance, collision quality, blocking behavior, or gameplay fairness.

## Scope and policy

No MAP, BSP, PK3, generator, texture, or other map artifact was modified during this checkpoint. Evidence is observational and candidate-specific. It must not be transferred to another hash or used to accept/promote this map. Only explicit user approval can accept an exact tested candidate.

## Durable layout

- `reports/strict-audit.json`: authoritative gate result
- `reports/evidence-plan.json`: exact view, diagnostic, lifecycle, and route claims
- `reports/visual-report.json`: repository-relative screenshot/log report
- `reports/screenshot-conversion-manifest.json`: original TGA to durable PNG hash/pixel correlation
- `reports/bot-runtime-report.json`: package-pure bot QA
- `reports/bot-instrumented-report.json` and `reports/bot-route-analysis.json`: supplemental movement/lifecycle evidence
- `reports/door-instrumented-report.json`: supplemental controlled-door evidence
- `screenshots/`: all 17 lossless full-resolution PNGs
- `logs/`: raw and derived logs
- `instrumentation/`: exact harnesses and loose scripts used by the final evidence lanes
