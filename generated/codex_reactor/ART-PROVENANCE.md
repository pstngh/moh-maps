# Codex Reactor art provenance

Status: project-owned original diffuse reuse

Date: 2026-08-08

`codex_reactor` contains no Valve texture pixels, Source geometry, Source
models, or extracted CS/CS2 payloads. It is an original brush map.

The package reuses sixteen original diffuse TGAs already authored for this
repository's `codex_nuke` work:

- `asphalt.tga`
- `ceiling_tile.tga`
- `clean_white_metal.tga`
- `concrete_dark.tga`
- `concrete_floor.tga`
- `control_panel.tga`
- `corrugated_blue.tga`
- `corrugated_gray.tga`
- `equipment_blue.tga`
- `metal_grating.tga`
- `metal_trim.tga`
- `painted_concrete.tga`
- `painted_concrete_blue.tga`
- `rubber.tga`
- `safety_red.tga`
- `safety_yellow.tga`

Their source prompts, generated raster sources, deterministic derivative
process, continuity checks, and original-art policy are recorded in
`../codex_nuke/ART-PROVENANCE.md`. Reactor does not modify those image bytes;
the deterministic packager copies and entry-hashes the canonical TGAs.

Stock `sky/mohday1`, `common/caulk`, multiplayer scripts, player/weapon data,
sounds, and effects resolve from the user's legally installed retail Allied
Assault Pak0-Pak6 and are not redistributed in `codex_reactor.pk3`.
