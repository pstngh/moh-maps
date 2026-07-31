# Nuke revision 4: human playtest verdict

## Evidence

- Date reviewed: 2026-07-31.
- User evidence: 18 target-renderer screenshots, `shot0011.tga` through
  `shot0028.tga`.
- Images remain local review evidence and are not redistributed in the
  repository.
- Tested artifact claimed by the current repository revision:
  `codex_nuke.pk3`, SHA-256
  `214F0EAD023D754F5FA199A9C9F8E5A66E6C0AC9F89EF0A6DA6B53A1834E067F`.
- Human verdict: failed visual acceptance. The map is playable, but it remains
  substantially incomplete and contains visibly corrupt surfaces.

## Defect inventory

| ID | Area/evidence | Visible symptom | Cause class | Next action |
| --- | --- | --- | --- | --- |
| N4H-01 | Exterior and high views, especially shots 12-19 | Facility masses, roofline, railings, yard equipment, and facades are sparse, overly white, and visibly block-built | Bounds-based model substitutes lack source topology | Replace selected landmark/model families with topology-backed geometry; do not add more aggregate hulls |
| N4H-02 | Interior rooms and transitions, especially shots 11 and 20-23 | Correct-scale spaces remain empty and generic | Important structural/furnishing model layer is still absent | Restore topology-backed doors, frames, ceiling plant, pipework, consoles, platforms, and cover by callout |
| N4H-03 | Shot 16 | Display/proxy faces show unrelated photographic imagery | Runtime material/image resolution or package conflict | Reproduce in a clean single-PK3 client and collect the matching client log and search path |
| N4H-04 | Shot 24 | A display/window surface shows mirrored alphabet/font-atlas imagery | Runtime material/image resolution or package conflict | Same gate as N4H-03; this is not a lighting-only defect |
| N4H-05 | Lower industrial rooms, especially shots 25, 26, and 28 | Floors contain huge black, white, and brown patchwork panels | Base material resolution, surface UV, or post-VIS lightmap-atlas regression | Isolate base-texture lookup first, then compare a non-repacked control BSP at fixed viewpoints |
| N4H-06 | Whole map | Clean CS:GO Nuke art direction is only approximated by a small generic palette | Current package contains original substitutes rather than locally converted owned Source assets | Choose a local extraction/conversion pipeline or a fully redistributable original-art reauthoring |

## Diagnostic evidence

- The committed `textures/codex_nuke/control_panel.tga` is a valid, simple
  original image; it does not contain the face or alphabet visible in the
  screenshots.
- Recognizable unrelated imagery therefore cannot be explained by sunlight or
  ordinary lightmap darkness alone.
- The available `C:\Users\plex\main\qconsole.log` contains no `codex_nuke`
  entries. During the filesystem timestamp window for these screenshots it
  records `dm/codex_inferno`, so it is not accepted as the matching Nuke client
  log.
- The revision-4 isolated runtime test remains evidence that the PK3 can load;
  it is not evidence that the user's launcher loaded the same package and
  search path.

## Revised implementation direction

1. Treat revision 4 as a playable conversion scaffold, not an accepted visual
   baseline.
2. Stop using model AABBs or family hulls for landmark architecture.
3. Use the owned CS:GO BSP/VMF, VPK assets, and model topology locally to
   reconstruct the visible structural layer at the original measured
   transforms.
4. Keep GitHub redistributable: commit conversion tools and derived metadata,
   but do not commit Valve texture or model payloads unless distribution rights
   are independently established.
5. Add a clean-install/package-hash test and capture the matching client
   `qconsole.log` before diagnosing lightmaps.
6. Build fixed callout regression views for Outside, Garage, Lobby, Ramp,
   A Site, Heaven, B Site, Control, Secret, and Roof.
7. Require zero unrelated/fallback imagery and human recognition at every
   callout before release.

## Information still needed from the user

- Approval to use the recommended local extraction/conversion workflow against
  the user's owned CS:GO installation.
- The exact OpenMoHAA launch profile or console `path` output for the session
  that loads Nuke, so stale or conflicting package precedence can be ruled out.
