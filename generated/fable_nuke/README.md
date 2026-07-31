# Fable Nuke (clean-room one-shot benchmark)

A from-scratch CS:GO Nuke conversion built by a newly written generator
(no code reuse from codex_nuke) as the one-shot benchmark. Reference VMF
read locally; nothing from it is committed.

Status: source complete, statically validated; NOT yet compiled — the
compile is the benchmark measurement.

## Build (Windows, MOHTools 1.48, staged retail tree)

```powershell
node generated/fable_nuke/tools/generate_fable_nuke.js "path\to\de_nuke_d.vmf"
Q3map.exe -threads 4 -gamedir "retail-stage" -moddir main "retail-stage\main\maps\dm\fable_nuke.map"
Q3map.exe -vis -fast -threads 4 -gamedir "retail-stage" -moddir main "retail-stage\main\maps\dm\fable_nuke.bsp"
MOHlight.exe -threads 4 -gamedir "retail-stage" -moddir main "retail-stage\main\maps\dm\fable_nuke.map"
# pack main/ into fable_nuke.pk3 (maps/dm + scripts + textures, forward slashes)
```

If MOHlight exceeds 180 lightmap pages, run codex_nuke's
repack_nuke_bsp_lightmaps.js and relight_nuke_unlit_surfaces.js (generic
BSP19 tools) before/after the light pass per that map's README.

## Known v1 debt (deliberate, per playbook policy)

- All 6,891 props omitted and counted (evidence-first; fidelity layer is a
  later stage) — expect a structurally faithful but empty map.
- 706 displacement faces planarized; no seam underlays yet.
- 149 unknown-material faces fell back to caulk (report has counts).
- Doors use simple 56x108 metal slabs, not measured leaves.
- Stock sky, first-guess lighting values.
