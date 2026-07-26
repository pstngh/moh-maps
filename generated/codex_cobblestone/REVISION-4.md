# Cobblestone revision 4 report

Status: validated release candidate

Date: 2026-07-26

## Identity

- Map: `codex_cobblestone`
- Target: Allied Assault BSP 19 and OpenMoHAA
- Modes: DM/TDM
- Baseline: revision 3, commit `7f302d6`
- Reference: legally obtained `de_cbble_reference.vmf`, not redistributed

## User evidence

The input set contains nine 1920x1080 screenshots, `shot0019.tga` through
`shot0027.tga`. Revision 3 is visibly much cleaner: its floating architectural
frames, facade panels, pale strips, and broad wall failures do not recur.

### Defect matrix

| Screenshots | Visible symptom | Cause classification |
| --- | --- | --- |
| 0019, 0024, 0026, 0027 | Bright triangular or ribbon-like sky gaps between otherwise textured floor surfaces | **OBSERVED:** adjacent planar displacement backing faces do not cover all of the XY area occupied by the original horizontally offset Source terrain |
| 0020 | Grass ramp/backing face ends abruptly above the adjacent floor | **OBSERVED:** the flat backing plane cannot reproduce the sculpted displacement edge |
| 0021-0023, 0027 | Bots reach exposed exterior terrain islands and the distant view contains floating trees | **PROVEN:** vegetation beyond the safe grounding correction remained at its original height. **DISPROVEN:** restoring the measured large Source clip volumes alone does not contain every exterior route |
| 0025 | Interior floor/support gaps and disconnected surfaces | **OBSERVED:** the remaining failures occur at converted support and displacement transitions, not at the omitted revision-2 model placeholders |
| User observation | Visible doors do not open | **INTENDED SOURCE BEHAVIOR:** the VMF has zero `func_door` or `func_door_rotating` entities and 33 door-model props; route-blocking placement still requires runtime inspection |

## Shared causes

Revision 3 repaired mixed-material nodraw faces, but a correctly textured side
face cannot fill XY area that existed only after Source displacement samples
moved horizontally. Full curved reconstruction remains too expensive for the
legacy compiler. A low-detail material-matched underlay can cover narrow
transition gaps while the original backing brush continues to provide simple
bot collision.

The earlier helper policy was also too broad. Cobblestone contains only three
explicit `toolsplayerclip` brushes, but 46 `toolsclip` brushes have at least
one 512-unit extent. Those large volumes represent intentional collision
architecture rather than editor noise. The other 1,080 helper-only brushes
remain omitted.

Door interactivity is not being synthesized in this revision. The reference
contains 22 `door_a`, five `door_b`, and six ornate door-model instances, but
no actual Source door entity. Adding AA rotating doors without verified model
bounds, pivots, swing clearance, and route intent would repeat the unsafe
model-substitution mistake fixed in revision 3.

## Revision-4 candidate

- preserve the three Source player-clip brushes as stock
  `common/playerclip`;
- preserve 46 large Source clip brushes as stock `common/clip`;
- add a 12-unit-deep, 24-unit-expanded material-matched underlay below each
  traversable planar displacement surface;
- emit 311 simple seam underlays rather than thousands of full curved patches;
- omit vegetation when a displacement support exists but grounding would
  require a correction outside the verified range;
- retain all revision-3 brush architecture, nodraw repair, materials, spawns,
  lights, and unsafe-model omissions.

Initial generation measurements:

- 5,142 generated brushes or patches;
- 4,702 converted Source solids;
- 311 planar seam underlays;
- 3 player-clip and 46 large general-clip brushes;
- 31 retained stock vegetation entities;
- 123 generated cover brushes;
- 44 neutral, 22 Axis, and 22 Allied spawns;
- 65 translated fixture lights.

## Validation

Q3map compiled 29,258 input faces to 27,373 output faces in 1,172 seconds
with no warning or error matches and a 12,956,936-byte unlit BSP. Fast VIS
remained stable at 90 clusters, 161 portals, and 1,448 visibility bytes.

MOHlight completed in 487 seconds and produced a 20,422,536-byte lit BSP.
Its diagnostics contained two ordinary per-leaf light clamps, from 64 and 62
lights down to the engine limit of 60, plus four `potential hash mismatch`
warnings. Two mismatches lie in distant/sky geometry and two lie in playable
map coordinates. The build completed, loaded, and rendered, but these warnings
remain recorded rather than being described as a clean light pass.

The final three-entry PK3 was copied into a fresh isolated home path and its
SHA-256 matched the tested package. OpenMoHAA 0.82.1 loaded it, generated
Recast navigation in 6.575 seconds, and ran eight bots. The automated
bot-follow run captured six viewpoints and recorded ten kills, proving
spawn, navigation, movement, combat, and respawn behavior.

The bot views show no recurrence of the floating incompatible vegetation
substitutions in the sampled areas. The restored clip volumes improve source
collision fidelity, but they do not fully contain bots: exterior terrain and
edge routes remain reachable. Automated fixed-camera and high-altitude
surveys showed no giant underlay or architecture regression, but did not
reproduce every exact ground-level user camera. The 311 underlays therefore
remain a bounded repair for the diagnosed planar XY gaps, with a user
ground-level retest still required to judge every seam.

A separate regeneration produced a byte-identical 4,237,412-byte `.map`,
SHA-256
`8C05CCEEF9A3E91C53FC08A9E3BC698231DB994D943792B45494B91221193E58`.

## Release fingerprints

- BSP: 20,422,536 bytes; SHA-256
  `BEB92C96CBCDB6CB7F00755F97EBFACADBA4E184E7CC1FCFF48B80515E7DB8E6`
- PK3: 3,916,777 bytes; SHA-256
  `22862E336C2C1CF8014AF7CBE1984CF07B7F6FD1CAD76F5E953728179394D32F`
- source ZIP: 452,664 bytes; SHA-256
  `EC4B11984FD58540FBD32DAEF819F1B816ACEF7C5B70235605D3AA3E46282CE2`

## Known remaining debt

- Source displacement terrain is still planar rather than sculpted.
- Exterior boundary and omitted 3D-skybox geometry leave exposed edge routes
  and incomplete distant silhouettes.
- The four MOHlight potential-hash-mismatch warnings need coordinate-specific
  investigation if a later visual report correlates them with a defect.
- Visible door props remain intentionally static because the reference
  contains no functional door entities.

## Knowledge promotion

- Map-specific status, fingerprints, door intent, and exterior debt are in the
  current map README.
- The chronological measurements and camera-harness finding are in the
  research log.
- The playbook now distinguishes editor helpers from gameplay collision,
  records bounded seam underlays, requires containment retesting, and explains
  reliable player-camera view angles.
- The stock asset catalog identifies the verified AA clip materials used here.

## Release checklist

- [x] Source and generator reproduce a byte-identical `.map`.
- [x] Q3map BSP, fast VIS, and full MOHlight completed against retail AA data.
- [x] The exact isolated PK3 loaded.
- [x] Neutral, Allied, and Axis spawns plus multiplayer scripts are present.
- [x] Eight bots spawned, moved, fought, respawned, and scored kills.
- [x] Bot-follow, fixed-camera, overview, interior, exterior, and map-edge
  regression views were inspected.
- [x] Remaining visual, route, lighting-warning, and door-interactivity debt is
  documented honestly.
- [x] Repository artifacts match the recorded hashes.
- [x] Map README, revision report, research log, playbook, and asset catalog
  are updated.
- [x] The release commit is pushed to `main`.
