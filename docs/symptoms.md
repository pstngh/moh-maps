# Symptoms: what you see, why, and what guards against it

Every bug that was seen in a build and fixed gets a row here, so the next map doesn't pay
for it again. Look up what a shot shows; follow the fix link for the details. **Guard** says
what catches it now without anyone looking: a test, a validator or compile check, a harness
setting, or nothing yet (then a sheet check is the only defence, and a guard is worth
writing). Keep rows short; the explanation belongs in the linked doc.

## Props and LOD

| what you see | cause | fix | guard |
|---|---|---|---|
| Grey or black slanted triangles across a prop at some distances (de_nuke Ramp3) | LOD: a vertex that lost its last triangle pointed at vertex 0; the engine keeps drawing dead triangles until an index-degenerate one, so seam slivers / zero-area leftovers stretched | `lod.simplify` orphans follow a live copy; zero-area triangles dropped (engine.md §5.2) | `test_lod.py` test_no_shards_from_seams_or_slivers |
| Flat props drawn as dark grey sheets up close; window glass, ladders, railings missing | LOD "free" collapses had zero plane error but smeared texture and baked vertex lighting | collapse cost counts texture slide + shade change; free level respects them (csgo-conversion.md "What a collapse costs") | `test_lod.py` test_vertex_colours_are_kept |
| A landmark prop (de_nuke's A silo) vanishes at mid distance; its shadow stays | fade cap applied to every prop, big ones too | open: scale the cap with prop size (HANDOFF) | none |
| Hundreds of props missing in game ("No free spots open in skel cache") | more than 1,024 SKDs in the skeleton cache (shared with players, weapons) | `staticmerge` keeps prop SKDs at 600 | `staticmerge.merge` budget; `test_staticmerge_under_limit` |
| Crash with bots, or props drawn with another prop's transform | more than 4,095 static models (12-bit sort key) | `staticmerge` target 3,500 | same |
| Props black inside dark areas (dust2 tunnel crates) | MOHlight's light grid ignores spotlight cones | props lit from the lightmaps (`staticlight.LightmapField`) | `test_lightmap_field_*` |
| Props pure white where CS:GO tints them | per-prop tint colours ignored | tints applied (masked by `tint_mask`) | none |
| Players walk through props | static models have no collision without `models/<path>.map` | clip brushes (CLAUDE.md) | none for stock props (`props.get(x).collision` tells) |
| A long-lived prop (wire, pipe run) never fades and is drawn at full detail from everywhere | one CS:GO `_autocombine_` mesh spans a building | `staticmerge` split_radius (profile key `merge_split`) | `test_staticmerge_splits_big_models` |

## Textures and materials

| what you see | cause | fix | guard |
|---|---|---|---|
| Faces drawn as a checkerboard | more than 64 vertices on a face after T-junction fixing | split brushes at 512 (Carver, `box`, `gable_roof`) | compile `bsp_checks`, `validate` |
| Black brushes that ignore light | `func_detail` becomes an unlit entity | `+surfaceparm detail` instead | CLAUDE.md rule |
| Caulk or sky faces as black holes | compiled against non-retail paks | the driver compiles against retail only | driver |
| Decals and masked textures black or dark-edged | Pillow resizes RGBA premultiplied | resize colour and alpha separately (`convert.py`, `modelconv.py`) | none |
| Opaque squares where decals should be; old textures showing | the engine loads `x.jpg` before `x.tga`; stale files from an older build | `convert.write_assets` prunes + manifest; `pak.image_clashes` on install | install warning |
| Every test shot shows the same wrong texture (de_dust2 "all sand") | the test game also read the installed pk3s (`fs_apppath`) | harness isolates `fs_apppath` | harness |
| Walls bare grey where CS:GO has ivy/plaster over them (de_cache) | `$blendmodulatetexture` blends need a threshold, not a linear mix | threshold blends (alpha test), materials docs | none |
| Shaders swapped or wrong on some surfaces in big levels | more than 2,048 shaders in a level wrap the sort key | keep the shader count down (convert warns above 1,500) | converter warning |
| Q3map "MAX_MAP_SHADERS" though few shaders are used | EA Q3map never de-duplicates 60-character shader names | names capped at 59 (toolchain.md) | `test_shader_names_fit_q3map` |

## Lighting, sky, fog

| what you see | cause | fix | guard |
|---|---|---|---|
| Ceilings lit, floors dark under lamps | `light_spot` aimed the wrong way (pitch sign) | VRAD's direction (z = +sin pitch) | none |
| Interiors much darker than CS:GO | MOHlight's 60 lights per leaf; many near-zero Source lights | tiny lights dropped, close ones merged; now CS:GO's own lighting transferred (lighting.md) | none |
| Whole map fogged black (de_vertigo) | the Master fog controller was not the one used | fog from the master controller | none |
| "A map in the sky" over the level | the 3D-skybox room shared the map's VIS region | sky room structural; rules for which rooms to keep (csgo-conversion.md) | none |
| Flat fog-coloured walls (de_mirage) | displacement faces with side 1 built inside out | `SourceBSP.displacement` uses the stored plane | none |

## Gameplay

| what you see | cause | fix | guard |
|---|---|---|---|
| Players stuck at spawn | Source spawns a few units inside walls (Source unsticks, MOHAA doesn't) | `validate.fix_spawns` | `test_fix_spawns_moves_out_of_walls` |
| Deathmatch spawns in two clusters at the map ends | DM spawns copied from T/CT spawns | spread FFA spawns from the CS:GO nav mesh (`source/nav.py`) | `test_nav.py` |
| A ladder you can't climb | rail clips narrower than a player; probe started inside geometry | rail-clip pairs dropped, probe start on the floor (csgo-conversion.md) | `test_ladder_*`, `game.ladder_probe` in final builds |

## Testing and measuring

| what you see | cause | fix | guard |
|---|---|---|---|
| A converted map runs at single-digit fps in tests only | `r_primitives 0` on Apple GL: one Metal draw per triangle strip | harness sets `r_primitives 2` | harness |
| The same build's fps differs by 30% between runs | leftover processes, remote desktop, thermal state | compare only interleaved runs (testing.md "Frame rate") | none |
| `bk` (back-end ms) tiny while frames are slow | 2D draws flush the 3D scene and overwrite the timer | judge by total frame ms (testing.md) | none |
| Test frames 3x darker with stencil shadows | stencil shadows in OpenMoHAA | harness uses blob shadows | harness |
