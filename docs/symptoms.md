# Symptoms: what you see, why, and what guards against it

Every bug that was seen in a build and fixed gets a row here, so the next map doesn't pay
for it again. Look up what a shot shows; follow the fix link for the details. **Guard** says
what catches it now without anyone looking: a test, a validator or compile check, a harness
setting, or nothing yet (then a sheet check is the only defence, and a guard is worth
writing). Keep rows short; the explanation belongs in the linked doc. When a shot shows
something no row explains, the tracing methods are in testing.md "Diagnosing a wrong look".

## Props and LOD

| what you see | cause | fix | guard |
|---|---|---|---|
| Grey or black slanted triangles across a prop at some distances (de_nuke Ramp3) | LOD: a vertex that lost its last triangle pointed at vertex 0; the engine keeps drawing dead triangles until an index-degenerate one, so seam slivers / zero-area leftovers stretched | `lod.simplify` orphans follow a live copy; zero-area triangles dropped (engine.md §5.2) | `test_lod.py` test_no_shards_from_seams_or_slivers |
| Flat props drawn as dark grey sheets up close; window glass, ladders, railings missing | LOD "free" collapses had zero plane error but smeared texture and baked vertex lighting | collapse cost counts texture slide + shade change; free level respects them (csgo-conversion.md "What a collapse costs") | `test_lod.py` test_vertex_colours_are_kept |
| A landmark prop (de_nuke's A silo) vanishes at mid distance; its shadow stays | fade cap applied to every prop, big ones too | open: scale the cap with prop size (HANDOFF) | none |
| Hundreds of props missing in game ("No free spots open in skel cache") | more than 1,024 SKDs in the skeleton cache (shared with players, weapons) | `staticmerge` keeps prop SKDs at 600 | `staticmerge.merge` budget; `test_staticmerge_under_limit`; `finish_local` warns over 600; `game.run` triage lists the message |
| Crash with bots, or props drawn with another prop's transform | more than 4,095 static models (12-bit sort key) | `staticmerge` target 3,500 | same; `game.run` reports the crash |
| Props on one installed map drawn wrong though its own test shots are fine (cs_cache with all eight installed: both trucks' cabs mangled and flat-shaded, a rock a dark blob; 3% of the Ttruck frame) | installed pk3s share prop paths (`models/csgo/...`, prop textures) with different contents (LOD tables, vertex order, texture gain); the game uses the copy of the pk3 last by name for every map (2026-10-02: 252 files; cs_cache lost all 208 of its own) | open: per-map prop asset paths (HANDOFF) | `mohkit install` warns (`pak.path_clashes`) |
| Props black inside dark areas (dust2 tunnel crates) | MOHlight's light grid ignores spotlight cones | props lit from the lightmaps (`staticlight.LightmapField`) | `test_lightmap_field_*` |
| Runtime props (`script_model`) solid black (dust2 rubble) or ambient only (cars beside sunlit rubble) | lit by one sun trace from 8 below the origin: a Source pivot on the floor, or a start inside the model's own clip hull; also every sheet shot at `r_fastentlight 1` (grid only) | lighting point 8 above the mesh top (`modelconv.LIGHT_ABOVE_TOP`, csgo-conversion.md "Runtime prop lighting") | `test_modelconv.py` test_convert_variants |
| Props pure white where CS:GO tints them | per-prop tint colours ignored | tints applied (masked by `tint_mask`) | none |
| Players walk through props | static models have no collision without `models/<path>.map` | clip brushes (CLAUDE.md) | none for stock props (`props.get(x).collision` tells) |
| A prop's collision is ~20 units bigger after its pivot moved | the hull face merge compared plane distances from the origin | translation-invariant merge (csgo-conversion.md) | `test_hull_brush_translation_invariant` |
| A long-lived prop (wire, pipe run) never fades and is drawn at full detail from everywhere | one CS:GO `_autocombine_` mesh spans a building | `staticmerge` split_radius (profile key `merge_split`) | `test_staticmerge_splits_big_models` |
| Shot metal vents or wooden covers burst into glass shards | retail `func_window` debris 0-3 are all glass | ship `debris_7.tik` (metal) / `debris_8.tik` (wood) by `$surfaceprop` (engine.md §5.5) | `test_debris_type_by_surfaceprop` |

## Textures and materials

| what you see | cause | fix | guard |
|---|---|---|---|
| Faces drawn as a checkerboard | more than 64 vertices on a face after T-junction fixing: a long or tall face (de_rats' 672-tall wall strip: 65), or a narrow face many detail pieces end on (mk_medina's arcade ceiling: 83) | split brushes at 512 (Carver, `box`, `gable_roof` in X/Y; the converter in Z too); end detail pieces short of a narrow face and bridge with one piece (map-format.md "64-vertex faces") | `compile.face_checks` right after BSP (stops before VIS and light), `validate` |
| Black brushes that ignore light | `func_detail` becomes an unlit entity | `+surfaceparm detail` instead | CLAUDE.md rule |
| Caulk or sky faces as black holes | compiled against non-retail paks | the driver compiles against retail only | driver |
| Decals and masked textures black or dark-edged | Pillow resizes RGBA premultiplied | resize colour and alpha separately (`convert.py`, `modelconv.py`) | `test_convert.py` test_opaque_resize_keeps_colour (world textures) |
| Crack and grime decals as grey or black squares (de_nuke asphalt) | Source DecalModulate drawn as an ordinary blend, or its alpha dropped (a modulate blend has none) | `blendFunc GL_DST_COLOR GL_SRC_COLOR`, alpha folded into neutral grey (csgo-conversion.md materials) | none |
| Light-shaft cards drawn solid white (de_nuke) | `$additive` + `$translucent` model material drawn as a plain add | `blendFunc GL_SRC_ALPHA GL_ONE`; `UnlitGeneric` gets `rgbGen identity` | none |
| Two black panes floating over B site (de_cache) | an `$additive` world material (dark skylight glow, `effects/trainsky`) converted as an alpha blend | `blendFunc add` for world faces and overlays | none |
| An opaque grey shell hides an object (de_inferno's fountain statue) | a `Refract`/`Water` material without `$basetexture` got the grey placeholder | faint translucent tint from `$refracttint` and the normal map (`modelconv.see_through_image`) | `test_see_through_image` |
| Alpha-tested converted prop textures drawn opaque; "Couldn't find image for shader" | the props' shader script sat at the pk3 root: only `scripts/*.shader` is read | write it under `scripts/` | converter refuses shader files elsewhere |
| Opaque squares where decals should be; old textures showing | the engine loads `x.jpg` before `x.tga`; stale files from an older build | `convert.write_assets` prunes + manifest; `pak.image_clashes` on install | install warning |
| Every test shot shows the same wrong texture (de_dust2 "all sand") | the test game also read the installed pk3s (`fs_apppath`) | harness isolates `fs_apppath` | harness |
| Walls bare grey where CS:GO has ivy/plaster over them (de_cache) | `$blendmodulatetexture` blends need a threshold, not a linear mix | threshold blends (alpha test), materials docs | none |
| Shaders swapped or wrong on some surfaces in big levels | more than 2,048 shaders in a level wrap the sort key | keep the shader count down (convert warns above 1,500) | converter warning |
| Q3map "MAX_MAP_SHADERS" though few shaders are used | EA Q3map never de-duplicates 60-character shader names | names capped at 59 (toolchain.md) | `test_shader_names_fit_q3map` (converter only) |
| A texture is missing although the file is in the pk3 | image path of 64 characters or more (`MAX_QPATH`, `tr_image.c`) | converter hashes long names (`modelconv.model_names`, `texture_name`, `l2_<md5>`) | none for hand-made assets |

## Lighting, sky, fog

| what you see | cause | fix | guard |
|---|---|---|---|
| Ceilings lit, floors dark under lamps | `light_spot` aimed the wrong way (pitch sign) | VRAD's direction (z = +sin pitch) | `test_light_spot_points_along_vrad` |
| Interiors much darker than CS:GO | MOHlight's 60 lights per leaf; many near-zero Source lights | tiny lights dropped, close ones merged; now CS:GO's own lighting transferred (lighting.md) | none (`--mohlight` path only) |
| Rooms flat white near lamps and dark between them; single textures blown out (de_nuke radio room 183 vs CS:GO 94) | MOHlight's point light (`7500 * I * cos / d^2` in display space, capped at 127) can't reproduce VRAD's | CS:GO's baked light transferred (csgo-conversion.md "Lighting") | `exposure --ref` against `csgo-ref` shots (manual) |
| Round black blotches at face corners on sunlit floors (de_inferno CT) | VRAD leaves luxels outside a face's polygon black; the transfer used them | luxels more than 0.75 outside an edge dropped | `test_luxels_stay_on_their_polygon` |
| Props black in a transferred map | lit from the floor texels under them, where VRAD baked the prop's own shadow | VRAD's per-vertex prop light (`.vhv`) | none |
| Whole map fogged black (de_vertigo) | the Master fog controller was not the one used | fog from the master controller | none |
| The level shows the stock MOHAA day sky (de_vertigo) | the sky VMT's `$basetexture` isn't shipped, only its HDR texture | fall back to `$hdrcompressedtexture` / `$hdrbasetexture` | report warning "only n/6 faces found" |
| "A map in the sky" over the level | the 3D-skybox room shared the map's VIS region | sky room structural; rules for which rooms to keep (csgo-conversion.md) | none |
| Skybox buildings hang huge over the map from some spots (de_dust2 DD) | AA draws the portal sky from one fixed eye (no parallax), so objects near that eye are far off for players elsewhere | objects nearer than 8 x spawn spread dropped; a room losing over 3/4 gets the 2D sky | none |
| Windows show flat haze where a portal sky should be (de_vertigo) | the renderer tests only the first 32 portal-sky surfaces a frame (engine.md §4.4) | sky brushes left unsplit (1,817 -> 113 surfaces) | none |
| Sky above de_vertigo's city dark navy through windows (CS:GO: light-blue haze) | open: began when the sky room became structural (b857580); the room also lacks CS:GO's sky_camera fog | open (HANDOFF) | none |
| Flat fog-coloured walls (de_mirage) | displacement faces with side 1 built inside out | `SourceBSP.displacement` uses the stored plane | `test_source_readers.py` displacement facing check |
| Patches of a shot exactly in `farplane_color` (x 255, within a few levels) | nothing was drawn there: back-facing or missing faces, not lighting (de_mirage MidCat: 5.5% of the frame) | find the face (testing.md "Diagnosing a wrong look") | none (an `exposure` flag would be cheap) |

## Compiling and conversion

| what you see | cause | fix | guard |
|---|---|---|---|
| Q3map prints "Entity N origin is out of bounds, skipping!" for every entity, then VIS "LoadPortals: couldn't read <map>.prt" (de_vertigo) | the map lies outside ±8192 (de_vertigo is played 11,500 units up) | converter moves the map (`Options.offset`, `translate_map`; textures and report coordinates follow) | converter (automatic) |
| Compile leaks from a spawn to the void; the caulk shell crosses ±8192 (de_cache) | 3D-skybox brushes and func_brushes with no area of their own were kept far from the map | sky box = the sky area plus its leaf bounding box (`Converter._sky_box`) | none |
| Spawns missing after conversion (de_rats: at least 4, all CT spawns) | the map is built for CS's 72-unit player; `validate.fix_spawns` removes spawns with no standing room for 94 | `--scale 1.1` (csgo-conversion.md "Scale") | report `spawns_fixed` lists removals; no warning |
| A transferred map would need more than 256 lightmap pages | renderer array `tr.lightmaps[256]`, no bounds check | raise the lightmap density | `lighting.transfer` refuses |

## Gameplay

| what you see | cause | fix | guard |
|---|---|---|---|
| Players stuck at spawn | Source spawns a few units inside walls (Source unsticks, MOHAA doesn't) | `validate.fix_spawns` | `test_fix_spawns_moves_out_of_walls` |
| Players spawn stuck in a prop (mk_village wagon, sandbags) | spawn inside a prop that has a collision `.map` | move the spawn; the check uses the prop's rotated bounds, so leave margin | `validate` (spawn vs `_prop_solids`) |
| Deathmatch spawns in two clusters at the map ends | DM spawns copied from T/CT spawns | spread FFA spawns from the CS:GO nav mesh (`source/nav.py`) | `test_nav.py` |
| Player stuck near the top of a converted ladder, or falls off it | MOHAA `func_ladder` only lets a player off forward onto a clear spot (CS scaffold and hole ladders); a square volume picked the wrong axis from float noise | CS-style step columns (`ladder_style="steps"`, default); both axes tried | `test_ladder_facing`; `game.ladder_probe` |
| A ladder you can't climb | rail clips 24 apart, narrower than a player; first step more than 18 above the floor in front (displacement ground below a ledge); a near-square volume facing open air | rail-clip pairs dropped; floors count displacements (lowest within 32); axis switch only for 1.5x wall (csgo-conversion.md) | `test_ladder_*`; `game.ladder_probe` (run by hand or a local final script, not by any mohkit command yet) |
| Bots never use converted ladders (de_rats' bots stay on their floor) | the navmesh links only `func_ladder` (off-mesh links); a step column is a wall to it | open: a `func_ladder` in front of each column (untested) | none |

## Testing and measuring

| what you see | cause | fix | guard |
|---|---|---|---|
| A run ends after ~16 s with exit 0, and every shot shows the menu or one spot | the map never loaded (an ERR_DROP back to the menu: "Server crashed: LoadTGA: Only type 2 ..." from a `.jpg` `qer_editorimage`) | read the "Server Shutdown" line; `shaders.editor_image` names the `.tga` | `game.run` reports "never loaded"; `bsp_checks`, `test_editor_image_is_tga` |
| A bot run shows only a negative exit code (`exit=-6`) | the game crashed (signal); the Backtrace is at the end of stdout.txt | — | `game.run` reports the crash (`CRASHED` in the summary) |
| The game idles at the console until the timeout | more than 32 `+` commands push `+devmap` off the command line | extra caller cvars go to autoexec.cfg (`game.fit_command_line`) | `test_plus_command_limit` |
| Every camera shows the spawn point (stock mohdm1, any map with its own loading menu) | the loading screen waits for "continue" and fake-pauses the local server; `tele` is lost | harness sends `finishloadingscreen` | harness |
| Shots are third-person views of a random bot | the local spectator followed a bot | bots join after the last camera | harness |
| Shots taken while the map was still loading | one long loading frame uses up `wait N` | frame-counted bare `wait` runs (`game.frames`) | harness |
| Blurry textures, floor props black, coarse curves on every sheet | a fresh OpenMoHAA home is near the low preset (`r_picmip 2`, `r_fastentlight 1`, `r_subdivisions 20`) | retail high in the run's autoexec.cfg (`game.QUALITY_CVARS`) | harness |
| `Shot.fov` has no effect (every shot at 80) | OpenMoHAA ignores the server `fov`; the client draws `cg_fov`, clamped 65..120 | harness sets `cg_fov`; narrower is a centre crop of 65 | `test_fov_crop` |
| A converted map runs at single-digit fps in tests only | `r_primitives 0` on Apple GL: one Metal draw per triangle strip | harness sets `r_primitives 2` | harness |
| The same build's fps differs by 30% between runs | leftover processes, remote desktop, thermal state | compare only interleaved runs (testing.md "Frame rate") | none |
| Compile or light times that contradict each other (a 2-bounce preview slower than an 8-bounce normal) | several compiles shared the CPU, each with `-threads <cpu count>` | time on an idle machine; label shared timings (toolchain.md) | none |
| `bk` (back-end ms) tiny while frames are slow | 2D draws flush the 3D scene and overwrite the timer | judge by total frame ms (testing.md) | none |
| Test frames 3x darker with stencil shadows | stencil shadows in OpenMoHAA | harness uses blob shadows | harness |
| A sheet still shows the old behaviour after a harness or converter fix | the build was started before the edit and runs the code it imported | re-shoot the package (`mohkit test --shots`) or rebuild | none |
| An A/B shot changed in a way the change can't explain | the package changed too: stale or extra files (48 `l2_*.jpg` in a de_cache LOD build) | diff the two packages first (testing.md "Diagnosing a wrong look") | `pak.image_clashes`, `write_assets` manifest |
| The ladder probe says a working ladder climbs ~0 | the player got off at the top and walked off the ledge before the last `viewpos`; or the probe start was within a unit above a patch and the player fell through it | highest of 500 ms samples; starts 4 above the floor | `game.ladder_probe` |
| Bot kill counts low on maps with drops (de_rats 13 counted, ~19 deaths) | `KILL_RE` counts kill messages, not falls ("cratered") | read the log for deaths | none |
| A build hangs ~20 min in the light stage | multi-threaded MOHlight crashed and Wine parked it in winedbg | `WINEDLLOVERRIDES=winedbg.exe=d`, retry with `-threads 1` | driver |
| A build prints FAILED and packages nothing after a successful one-thread MOHlight retry | the crashed `light_mt` stage counted in `CompileResult.ok` | `ok` skips `light_mt` | `test_compile_ok_after_light_retry` |
| Another map's light stage dies when a build times out | tools were killed by name | `kill_stragglers` kills only the timed-out root's processes | driver |
| A compile root loses its map, BSP and logs mid-build | the repo is under `~/Documents`, which iCloud Drive syncs | build scratch lives in `~/Library/Caches/mohkit/build` | `config.default_build_dir()` |
