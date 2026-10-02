# Converting CS:GO maps

```sh
python -m mohkit csgo de_dust2                  # -> local/csgo/cs_dust2/{cs_dust2.map, assets/, cs_dust2.pk3, shots}
python -m mohkit csgo de_inferno --name cs_inferno -q normal
python -m mohkit csgo de_dust2 --props-only     # re-place runtime props in the last compile (~1 min)
```

`--resume` skips conversion and compiling: it injects the props, packages and tests
what the last build left in `local/csgo/<name>/` (map, assets, `statics.json`) and its
compile root, for when a stage was re-run by hand. Drafts use `lightmapdensity 32`
(`--lightmap-density`): MOHlight time is about proportional to lightmap texels, and
de_nuke has ~1M of them at 16.

`--refresh-assets` re-converts and re-packages the last compile when only textures,
shaders or models changed: it refuses unless the new `.map` text equals the compiled one.

`--resume` re-injects with the prop settings of the last conversion, not `--props`: the
`report.json` `convert` keys `lod_tau`, `lod_base_error`, `merge_split`, and the per-prop
fades and drops already in `statics.json` (6th field = fade). To try a prop setting without
converting again, edit those (and `prop_light.npz` in the same order whenever `statics.json`
gains or loses entries; keep copies, the next `--resume` uses whatever is there). On de_nuke
it takes ~4 min with LOD cached (`<build dir>/lod/`, keyed by SKD bytes, `lod.VERSION`,
scale and instance colours), ~15 min after a `lod.VERSION` bump.

**File names are per map.** Everything a conversion packages is under its own name: world
textures `textures/csgo/<name>/<material path>`, prop models `models/csgo/<name>/...`, prop
textures and clip shaders `textures/csgo/<name>_p/...` (a world material and a prop material
can share a path, with different shaders), merged props `models/csgo/m_<name>/`, sky
`env/csgo/<name>/`. Only the engine-fixed `models/fx/windows/debris_<n>.tik` are shared
(`convert.SHARED_PATHS`, the same bytes in every map). Prop files are map-specific (LOD
tables, vertex order, headroom gain), and installed pk3s that share a path override each
other: the game searches a folder's pk3s from the last name down (`FS_AddGameDirectory`), so
until 2026-10-02 every map drew one pk3's copy of `models/csgo/props/...` (252 files among
the eight installed; cs_cache lost all 208 of its own, its trucks' cabs mangled and
flat-shaded). Verified after the fix: the rebuilt cs_cache with the seven other installed
pk3s against alone, same 19 cameras: 18 pixel-identical (Ttruck had 3% of its pixels changed
before), the overview differing no more than two runs of one pk3 do. Older builds and
`--resume` of them keep the shared names: packaging warns
(`pak.unowned_paths`), `mohkit install` lists clashes (`pak.path_clashes`), and `mohkit ab
<map> --a X.pk3 --b X.pk3 <other installed pk3s>` shows what another installed map does to
this one (same cameras, per-camera change).

**When a conversion is done** (the user asks for it as "the same way as Inferno and
Cache"): every CS:GO route is walkable (every ladder passes `game.ladder_probe`, jumps and
drops work); the named-camera sheet has no holes, leaks, black or missing textures; props
sit, light and collide where CS:GO's do; sky, sun and fog read like CS:GO; decals and
signage are there; 8 bots for 90 s get kills; the brightness error against CS:GO's own shots
(`csgo-ref`, `exposure --ref`) is low (the 2026-10-01 finals: 4-11 of 255) after
`--fit-exposure`; fps is measured. When a whole class of converted things looks wrong the
same way (every interior dark), check the conversion's sign and axis conventions against the
Source tool's code with a one-entity test before tuning intensities: three light-count and
intensity fixes went in before the `light_spot` pitch sign was found. Order: `-q unlit` first (minutes: geometry, props, doors,
ladders, spawns), fix and batch the converter fixes, then one lit build. A lit build started
before a fix has to be redone (de_mirage was lit-built three times on 2026-10-01, 45-65 min
each). Converter fixes stay generic (no per-map branches). Before a rebuild meant to change
the look, keep the old build in `local/csgo/before/<name>/`; install only after the new
sheet was compared with the installed one on the same cameras (sky band included) and the
user agreed: batch scripts must never install. The steps exist only as gitignored scripts
in `local/csgo/` (`*_final.sh`, `ladprobe.py`, `cmp3.py`, `perf_nukes.sh`) until a
`mohkit csgo --final` command replaces them.

To check a converter change without compiling, run the stages involved in-process:
`cv = Converter(bsp, csgo_dir, Options(name="x", props=False)); cv.brushes(); cv.ladders()`
(about 5 s a map) and compare `cv.report` before and after on several maps (a `> 24`
threshold also moved de_mirage's 24.0000x-wide ladder; caught before any build).

**Workshop maps** aren't in the CS:GO install. A public item downloads without Steam: POST
`itemcount=1&publishedfileids[0]=<id>` to
`https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/` (no key)
and fetch `file_url`. The file is a zip holding the `.bsp` (named `.bsp` anyway); the last
component of the CDN URL is its SHA-1. Keep it in `local/workshop/` and convert it by path
(`mohkit csgo local/workshop/x.bsp --name cs_x`): custom models and materials come from the
BSP's own pakfile (de_rats_1337_v2, item 741136461: 253 files), and a map without
`<stem>_cameras.txt` gets automatic cameras. Use the Workshop file even when a copy is
lying around (the ~/Downloads de_rats was another version).

**Texture resizing trap (fixed 2026-10-01):** Pillow resizes RGBA images with
premultiplied alpha, so RGB goes black where alpha is 0. Source keeps specular/envmap
masks in the base texture's alpha, so every such texture over 512 px was written
darkened, and DecalModulate decals (neutral grey with alpha) came out as black squares.
Opaque images are now resized as RGB (`Converter._write_image`, `modelconv.convert_texture`).

`-q unlit` compiles BSP and fast VIS only and gives props a flat grey: geometry, props,
doors and ladders can be checked in minutes (de_nuke's draft light alone takes over an
hour: MOHlight's base cost per lightmap texel dominates, and texel count is what
`lightmap_density` controls; density 32 instead of 16 was ~5x faster). Removing the light
entities, `-notrace`, `-blocksize 512/256` and `sundiffuse 0` all read 0-1% after 150-300 s,
but that is no test: the slow part comes first, so compare MOHlight variants only at the
end of "Initial Lighting", alone on the CPU. Full builds suggest fewer lights and
`-blocksize 512` did shorten de_nuke's initial pass (65 min vs ~28-34 min), with CPU load
uncontrolled.

`--props-only` re-converts, checks that nothing but `script_model` props changed
(`mapfile.compiled_difference`: brushes compared by plane, numbers to 0.01), and
rewrites only the entity lump of the last compile with `Q3map -onlyents`
(`compile.update_entities`): 48 s on de_dust2 instead of about 45 min. Lighting stays
that of the last compile, and anything else that changed (a clip brush, a light, a
static prop) refuses with the first difference: run a full build then.

The converter reads the **compiled** `.bsp` shipped with the game, plus
materials and models from the VPKs. It needs no decompiler (BSPSource) and
no VMF. Output goes to `local/` (gitignored). It contains textures decoded from
Valve's files, so it's for personal use only: don't commit or share it.

## What gets converted

| Source | MOHAA | notes |
|---|---|---|
| world brushes, `func_detail` | world brushes (`+surfaceparm detail`) | bevel planes pruned; face points snapped to the grid; cut on a 1,024 grid in X/Y (`Options.split`) and 512 in Z (de_rats' 672-tall, 24-wide wall strip collected 65 T-junction vertices) |
| `func_brush`, `func_wall`, `func_breakable`, `func_illusionary` (non-solid), doors | world brushes, transformed to world space | doors become static. `func_brush` keys: `StartDisabled 1` = not there at spawn: dropped (de_nuke's 32 office-light strips VRAD used only for baking; with `--mohlight` texlights their faces still become lights); `Solidity 1` = non-solid; `rendermode 10` = not drawn: clip when solid, dropped otherwise |
| map position | moved inside ±7,900 when any brush is outside (`Options.offset`, on a 512 grid; de_vertigo by (-512, 512, -6656)) | `translate_map` moves brushes, patches and origins and corrects each face's texture shift; statics, landmarks, cameras, ladder records, luxels and the sky room follow `report["offset"]` (anything new that stores world coordinates in the report must too: ladder records once didn't, and 3 probes failed at the old place) |
| `toolsclip` / `toolsplayerclip` / `toolsinvisible` | `common/clip` / `common/playerclip` | |
| nodraw faces | `common/caulk` | |
| sky faces | converted skybox shader (`skyParms env/csgo/<map>/sky`) | Source cubemap faces → `_rt _lf _ft _bk _up _dn` (up/dn rotated) |
| hint, skip, areaportal, trigger, occluder, fog, blocklos, grenade/NPC clip | dropped (counted in the report) | |
| ladder volumes (`CONTENTS_LADDER`) | **CS-style step columns** (default, `Options.ladder_style="steps"`): invisible `common/clip` slices against the wall face of the Source volume, 16 units high, each 1 unit shallower than the one below (less, down to 0.5, where the room in front would not fit a climber beside the column: de_rats' 893-unit shaft ladder climbs 809 with that, 0 without; half-unit steps on open walls climbed less, 17-53 instead of 71-88 units), from the floor (when one is within 96 units below the volume; brushes or displacements, the lowest within 32 units of the highest in front) to the volume top. Running into it climbs it, backing off climbs down, and the player can step off sideways or onto the ledge at the top, as in CS. `ladder_style="func_ladder"`: MOHAA ladders (`common/trigger` over the volume + 8 units toward the climber, `common/origin` on the climb face, `angle` toward the wall) | Facing: the side of the volume with solid (Source contents, or converted detail and clip brushes) behind it; a square volume tries both axes (mirage's leaning ladder is 32.0001 × 32, and float noise had picked the wrong axis), a near-square one too (see Ladder facing below). Why steps: MOHAA's `func_ladder` only lets a player off forward at the top, after a 98-unit clear rise (`Player::CondCanGetOffLadderTop`), and the jump-off is weak (`jumpxy -70 0 150`, `global/mike_torso.st`). CS scaffold and hole ladders (mirage's two at the scaffolds: platform behind and beside, upper floor 96 units above) hung the player near the top. Climb speed: MOHAA steps up at most 18 units per move (`STEPSIZE`, `bg_slidemove.cpp`), so a column climbs at ~600 units/s at 60 fps (8-unit steps were no slower; it depends on frame rate). Walking backward off the top just walks down the column, so a hole ladder is left by strafing onto the platform beside it (verified 2026-10-01 on an unlit Mirage: all 3 ladders climb to the top; strafing off the two scaffold ladders lands on their platforms at z -40 and -58). Probe: `game.ladder_probe(pk3s, map, game.ladders_for_probe(bsp))`; a step ladder's report entry has a `probe_start` clear of solids (28 units out, else 22/16/36, slid along the width), since starting inside a clip strip or under an overhang made working ladders fail. Touching ladder volumes are one ladder (`merge_ladder_boxes`: de_cache's A ladder is two rails and a brush per rung). `func_ladder` notes: a hanging ladder's trigger is extended down to the floor (only when it hangs 32+ units above the floor in front: extending one whose bottom was 23 up stopped it mounting, it climbed 0 instead of 234) (mounting puts the player at absmin + 2, `FuncLadder::PositionOnLadder`); a volume deeper than 28 units climbs 8 units off its far face; prop collision in a ladder volume or its mount box is dropped (it blocks `Player::CondLadder`/`CanUseLadder`). `Converter.ladders`, report `ladders` |
| water volumes | the drawn face gets a water shader (`surfaceparm water trans nonsolid`, image = the normal map's relief tinted with `$fogcolor`, alpha `$waterblendfactor`); hidden sides `common/waterskip` (caulk is solid and would fill the volume) | Source water has no base texture |
| `func_breakable`/`_surf` (glass panes, mirage's wall-hole covers) | `func_window` (MOHAA's breakable brush), Source `health`, glass debris for glass, coloured otherwise | |
| overlays (`info_overlay`, LUMP_OVERLAYS) | flat 3×3 patch half a unit off the surface; shader `ov_<material>`: `trans nonsolid nomarks polygonOffset`, `blendFunc blend` + `nextbundle $lightmap` like retail decals | U axis is packed in the z of UV points 0–2, V = N×U (negated if point 3's z is 1); overlays wrapped over corners/displacements are placed flat |
| doors (`prop_door_rotating`) | `func_rotatingdoor`: a brush slab between the model's two largest opposite faces, textured with the model's material (each face's texdef reproduces the UVs of the largest mesh triangle on it), origin brush on the hinge, `openangle` = `distance`, `time` = distance/speed, `alwaysaway` for two-way doors | door meshes can lie 90° off the frame their angles apply to (rotated root bone): the mesh is turned to match the MDL hull box (`_yaw_to_hull`); no static prop in de_nuke needs it |
| ropes (`move_rope` → `keyframe_rope` via `NextKey`) | two crossed ribbon patches per segment, `Width` wide, `rope_*` shader (nonsolid, `cull none`, alpha-tested, lightmapped) | sag ≈ sqrt(3·span·Slack/8): a parabola, exact as one 3-column patch row (quadratic Bezier) |
| `env_sprite` (lamp glows) | a thin `common/nodraw` brush whose east face is a quad with an additive `deformVertexes autosprite` shader (`spr_*`), image fitted to the quad, `rendercolor` × `renderamt` baked in; 0.75 × texture size × `scale`, 8–96 units | autosprite needs a 4-vertex surface: the brush floats free so nothing T-junctions it |
| props with an `OnBreak` output (de_nuke's vent slats and vent cover, mirage's shutter and sheet-metal wall covers) | `func_window` slab of the model (same slab as doors), health from Source or 25: the vent is shut until shot. Debris by `$surfaceprop`: glass 0 (retail), metal 7, wood 8. Retail's `models/fx/windows/debris_0..3.tik` are all glass shards, so converted maps ship `debris_7.tik` (sparks from `bh_metal_fastpiece` + `metal_section` chunks, `snd_bodyfall_metal1`) and `debris_8.tik` (crate planks and splinters, `snd_crate_wood`) (`convert.debris_tiki`; verified in a test room) | bots don't use crouch-only vents anyway (the navmesh is built at standing height) |
| texlights (`lights.rad`: emissive materials, e.g. de_nuke's office-light strips, lit windows, reactor glow) | with `--mohlight` only (on by default there, `--no-texlights` turns it off; CS:GO-lit builds carry the light in the transferred lightmaps): one point `light` per emitting face (de_nuke: 43, incl. the faces of its disabled emitter func_brushes), 8 units out along the normal, intensity sqrt(area × brightness) × 4 (40–600), colour from the rad line | `q3map_surfacelight` works (test room) but de_nuke's 43 emitting surfaces made `fastrad` light estimate ~15 hours. Compared on de_nuke (2026-10-01, same cameras): Hell 1.8x brighter, B site 1.4-1.7x, the Heaven approach 1.5x, lit like CS:GO instead of dim; B site's upper walls take the warm white of `window_illum_001` (252 239 209). dust2 and mirage have no texlights |
| `env_fog_controller` | worldspawn `farplane` = fogend / fogmaxdensity, `farplane_color`, `farplane_cull 0` | the Master controller (spawnflags 1), not one only a `fog_volume` switches to: de_vertigo's first is `fog_shaft` (black, 3,000 units, the elevator shaft), which had fogged the whole map and its sky black |
| sky (`skyname`) | six faces from each face material's `$basetexture`, else its `$hdrcompressedtexture` / `$hdrbasetexture` (de_vertigo ships no LDR sky: it had the stock `sky/mohday2`) | de_nuke's `nukeblank` faces all use `skybox/nukeblankup` (plain 90 134 186 blue) |
| spectator cameras (`maps/<map>_cameras.txt`) | contact-sheet shots (eye position, pitch/yaw as given), pages of 9 (`<name>_shots.png`, `_shots_2.png`, …) | `named_cameras`. Shot at MOHAA's fov 80, while CS:GO draws them at 90 (both 4:3-basis): the converted shot is narrower, so `--ref` and `--fit-exposure` compare slightly different framings (a fix: `fov=90` for named cameras, then re-fit). Without a cameras file (workshop maps) the converter shoots one camera per bomb site, spread spawn cameras and an overview, each looking down its longest clear horizontal sightline (24 rays, exact ray/brush clipping: 16-unit ray marching skipped de_rats' 2-unit vent walls) |
| 3D skybox (the area containing `sky_camera`) | **MOHAA portal sky** (`Options.skybox3d="portal"`; `"drop"` keeps only the 2D sky): the room's brushes, displacements and props are kept, moved beside the map inside +-7,900 (`Converter._place_sky_room`: below, above, then beside it) and shrunk about `sky_camera` by 1/2 or 1/4 when it fits nowhere at full size (a perspective view is unchanged by scaling the scene about the eye; de_vertigo's 7,360-unit city: 1/2, `scale_face` keeps its texels); a `script_skyorigin` at `sky_camera + spawn mean / scale` (where Source's skybox camera is for a player there: de_vertigo is played 11,600 up, and from `sky_camera` itself its city looked street-level); the map's sky faces become `common/skyportal` (AA's `common.shader`), the room's own sky faces the converted 2D sky; `report["sky_room"]` tells `lighting.place` where the room's luxels and alphas went | detected from the area containing `sky_camera`, plus everything inside that area's leaf bounding box when the box is clear of the other areas' leaves (`Converter._sky_box`; disjoint on all five Valve maps checked): de_cache's skybox brushes whose faces all touch solid, and its func_brushes, have no area of their own; kept, they pushed the caulk shell to x = 9,879 and the compile leaked (207 skybox brushes dropped instead of 182). Allied Assault has no sky parallax (`skyboxSpeed` comes with protocol 15, `cg_main.c` `CG_ParseFogInfo_ver_6`), so the room is seen from one point. Portal-sky faces are never drawn; the renderer checks only the first 32 of a frame for being on screen (`tr_sky_portal.cpp` `R_Sky_AddSurf`) and draws no sky when all are off it, so the map's pure sky brushes are not split at 1,024 (de_vertigo: 742 split brushes, 1,817 surfaces, windows showing flat haze). The room keeps Source's structural brushes (everything else is detail inside one structural shell): sealed by them it is a VIS region of its own. Sky faces don't occlude, so when the room shared the map's region the portal view, drawn from inside it, drew the map too: de_dust2's buildings hung upside down in its sky. Seen from one fixed point, room objects near it land far from where a player elsewhere would see them (error angle ~ (player offset / scale) / distance): objects closer to the eye than 8 x the spawns' horizontal spread / scale (over ~7 degrees off at the far spawn) are dropped, and when over three quarters of the room goes the map gets the 2D sky only, its sky brushes split again (`report["sky_near_dropped"]` = [dropped, objects]). Kept share at that cut: de_vertigo 11 of 11 (played 732 above its city, spawns 800 apart), de_nuke 27 of 303, de_cbble 5 of 41, de_inferno 1 of 150, de_dust2/de_mirage/de_cache 0: their skyboxes are rooms built around the map, which one fixed eye can't show (de_dust2's houses past its walls hung huge over DD, its own buildings upside down before the room was its own VIS region). So only de_vertigo has a portal sky |
| displacements | `patchDef2` meshes | midpoint-expanded so they pass through every kept Source sample; sample rows/columns straight within `disp_tolerance` (1 unit) dropped, consistently across shared edges; split to ≤ 17×17; visible side toward the air |
| materials | TGA/JPG + generated shader script | `$basetexture`; two-layer blends (`$basetexture2`, WorldVertexTransition on displacements) get a second stage `blendFunc blend` + `alphaGen vertex` (layer 2 x lightmap over layer 1) and `lighting.blend_alphas` sets each drawvert's alpha after the compile from the Source displacement alphas of the same material within 48 units (weights 1 / (0.5 + d)^2; none: 0, as Source draws brush faces); layer-2 images are named `l2_<md5>` (image paths must stay under 64 characters, `tr_image.c`); 4-way blends keep the first layer. de_mirage: mean error against CS:GO 6.0 -> 4.4, its plaster and blue walls back. With `$blendmodulatetexture` (all of de_cache's) CS:GO switches layers where the vertex alpha passes a per-pixel threshold (`smoothstep(g - r, g + r, alpha)` of the mask, lightmappedgeneric_ps2_3_x.h); a linear blend washed de_cache's ivy walls out to bare panels (greenness error against CS:GO 0.57 -> 0.99). Those are alpha-tested: layer 2's alpha = 255 / (1 + g), vertex alpha = (1 + a) / 2, `alphaFunc GE128`, so layer 2 shows exactly where a >= g (hard edges; `$blendmasktransform` ignored); power-of-two, max 512 px; `$surfaceprop` → MOHAA material surfaceparm; alphatest/translucent/nocull handled. `$additive` world materials and overlays → `blendFunc add` (as a blend, de_cache's dark `effects/trainsky` glow drew two black panes over B site); model materials with `$additive` + `$translucent` → `blendFunc GL_SRC_ALPHA GL_ONE` (a plain add drew de_nuke's light-shaft cards solid white); `UnlitGeneric` → `rgbGen identity`; DecalModulate overlays → `blendFunc GL_DST_COLOR GL_SRC_COLOR` (grey 128 = no change) with the alpha folded into neutral grey, `128 + (rgb - 128) * a`, since that blend has none; `Refract`/`Water` without `$basetexture` (glass, de_inferno's fountain sheet) → a faint translucent tint from `$refracttint`/`$fogcolor` and the normal map's relief (`modelconv.see_through_image`; the grey placeholder hid the statue). Every two-layer blend on the seven Valve maps is a displacement (no brush faces): inferno 1,826, nuke 538, mirage 430, cbble 406, cache 278 (all modulated), dust2 149, vertigo 0 |
| texture alignment | Q3 shift/rotate/scale | exact for any rotation, scale or mirror (`tests/test_texdef.py`) |
| `info_player_terrorist` / `counterterrorist` / `info_deathmatch_spawn` | `info_player_axis` / `allied` / `deathmatch` | DM spawns are spread for FFA (`Options.ffa_spawns`, default): CS:GO's own `info_deathmatch_spawn`s first (only de_inferno 67 and de_cache 25 have them), then `nav.spawn_count` spots from the bot nav mesh (`maps/<map>.nav` v16, `mohkit.source.nav`: one per 640 x 640 units of walkable floor, 24-48; stock DM maps have 11-25), picked by walking distance and facing the longest open run, 12 units up (nav floors are only bilinear over an area's corners). Without a mesh (de_cache) CS:GO's DM spawns thinned to 48, else T+CT copies (the old behaviour: two clusters). Entities, so a full conversion is needed, not `--resume` |
| `light`, `light_spot` | `light` (+ `info_null` target along VRAD's spot direction: z = +sin(pitch), so pitch -90 points down; until 2026-10-01 04:40 the converter used -sin and every ceiling spot lit the ceiling) | intensity ≈ 1.5 × Source brightness, clamped 40–800 (0.75× left interiors dark: MOHAA's `light` is about its reach in units, and a 175-brightness ceiling spot barely reached the floor). Lights below brightness 20 are dropped and a light within 32 units of a brighter one is folded into it (de_nuke 473 → 247): MOHlight keeps at most 60 lights per leaf, and in the converted map's big leaves the near-zero fill lights crowded out the fixtures (radio rooms went dark while the light grid, which gets every light, made their props bright) |
| `light_environment` | worldspawn `suncolor`, `sundirection`, `ambientlight`, `sundiffusecolor` | sky fill = `_ambient` colour normalised to its brightest channel × clamp(brightness / 8, 20, 70) |
| `prop_dynamic(_override)`, `prop_physics(_override)`, `prop_physics_multiplayer`, `prop_hallucination` that stand still in play | static props like `prop_static` (de_mirage: 94; `prop_hallucination` is never solid: de_rats draws its 97 ladders and lamps with it) | interactive ones are not: an `OnBreak` output, `StartDisabled`, or the target of an Enable/Disable/Toggle/Break/Kill/SetAnimation/TurnOn/TurnOff output (vents, shutters: see the `func_window` row). Props only re-skinned by outputs (de_mirage's TVs) stay ordinary props |
| static props (`prop_static`) | `mohkit/source/modelconv.py` (MDL → TIKI/SKD/SKC + collision `.map`). **Default (`props_mode="inject"`): every prop** becomes a static model added to the lit BSP by `mohkit.staticlight` and coloured from its light grid, with its collision as world clip brushes. `props_mode="compile"`: the largest as MOHlight-lit `static_*` up to `--static-verts`, the next 600 as `script_model`s | MOHlight lights static models on one thread (~190 verts/s), so de_nuke's 4,801 props would light for hours; injection takes seconds and costs no entities |

**Ladder rails (2026-10-01):** CS:GO often flanks a ladder volume with two player-clip
brushes 24 units apart (de_vertigo, de_nuke), narrower than the 32-unit player: harmless
when the engine moves you in the volume, but a MOHAA player climbing the step columns got
wedged between them and the probe climbed 0. Such a **pair** goes
(`Converter._drop_ladder_rail_clips`, `report["ladder_rail_clips_dropped"]`): clip-only
brushes touching opposite sides of a 16-32 unit wide axis of the volume, each beside at
least half its height, removed before the ladders are placed. The first rule (every clip
touching a volume) also removed a 96 x 104 clip block under a de_vertigo ladder, caps on
de_nuke ladder tops and the clips behind de_rats ladders (68 there); counted as walls, the
rails had also turned a 26.7 x 24 de_vertigo ladder toward open air (it climbed 0).

**Ladder facing and floors (2026-10-01):** a near-square volume (sides within 25%) is
scored on both axes, but leaves its thin axis only for 1.5x as much wall on the other (a
22 x 17.6 de_rats shaft ladder has about as much on both and climbs as it was). The floor a
column starts from counts displacements (`Converter._displacement_heights`) and takes the
lowest floor within 32 units of the highest in front: de_cbble's 460-unit ladder rose from
a stone ledge 4 units above the displacement ground the player stands on, so its first step
was 20 up (over `STEPSIZE` 18) and it climbed 0. A ladder whose first step is more than a
jump (56) above the floor in front (counting prop collision) gets `hang` in its report
entry: de_vertigo's hatch ladder hangs 135 up (a CS:GO player reaches 72 + 57 = 129, so it
is climbed down there too). `game.ladder_probe` starts those in the air at the column with
+forward held: a falling player pressing into a step column steps up it. Probe starts are 4 units above the floor: the probe's `tele` rounds to whole units, and a player put within a unit of a patch falls through its collision (de_cbble's 460-unit ladder: "climbs 0", the player sank 46 units onto the caulk below the displacement ground; from 4 up it climbs 464 to the top).

## Visibility and compile time

Converted maps compile with Q3map `-blocksize 512` (`convert.BSP_ARGS`): the leaves of an
all-detail map are the BSP blocks, and smaller blocks mean fewer lights per leaf for
MOHlight's 60-light cap (de_nuke: ~500 clusters, 31 KB of VIS data).

By default every converted brush is detail inside a structural caulk shell. The price
is no VIS culling and a slow BSP stage on big maps: tens of thousands of faces share one
leaf. `--structural` keeps Source's own world/detail split instead. The old claim that
this overflows MOHAA's 2 MB VIS buffer is **false for de_dust2** (tested 2026-10-01 with
`-blocksize 512`, fast VIS): BSP 919 s (559 s all-detail), 691 clusters, 1,663 portals,
60,816 bytes of VIS data, no leak (a few lights inside walls "leaked" harmlessly). Not
yet compared: lit result, full VIS time, and whether it lights faster (smaller leaves).

**Displacements cost BSP time quadratically.** Q3map groups patches for LOD by
comparing every control point of every patch with every control point of every
other patch (`PatchMapDrawSurfs`, q3map `patch.c`). de_dust2's 619 patches
(118k control points) spent 673 s there, measured with timestamped logs.
Dropping straight sample lines halves the control points and cuts that work
3.9× (`Options.disp_tolerance`, default 1 unit; 2 units: 6.8×, not taken: the remaining
BSP phases dominate by then).

**A face's plane is `planes[planenum]` as stored; ignore `side`.** On every face of
de_dust2, de_mirage and de_nuke the stored plane agrees with the face winding, whatever
`side` says (`side` only records how the face sits on its BSP node). Until 2026-10-01 the
displacement normal was flipped when `side` was 1, so those displacements (dust2 176,
Mirage 143, Nuke 77) were turned inside out: back-facing patches the engine culls, seen
in game as flat `farplane_color` walls (Mirage's mid and B site). Found by casting the
camera's rays through both BSPs (every ray hit the patch; the patch faced away).
`tests/test_source_readers.py` now checks that displacements face the air.

**Source leaf contents know only structural brushes.** `func_detail` (merged into model 0
with `CONTENTS_DETAIL`) and clip brushes are not in the BSP tree, so a point inside them
reads as air in `leafs[point_leaf(p)].contents`. Test player solidity against the brushes
themselves (`Converter._ladder_solid` uses the converted brushes), not the leaf.

## Scale

CS players are 72 units tall, MOHAA's are 94, but jump height (56 vs about 55)
and step height (18) are nearly equal. At the default `--scale 1` rooms feel a
bit tight, but every CS jump spot that doesn't need a crouch-jump stays
reachable. `--scale 1.25` gives more natural proportions but lifts many boxes
out of reach. Maps built tight around CS's player can be too low for MOHAA's 94: de_rats'
vents are 88-96 tall, and at `--scale 1` `validate.fix_spawns` removed at least 4 spawns
(all CT spawns) with no standing room; `--scale 1.1` keeps all of them. Read
`report["spawns_fixed"]` after a conversion: removals are listed there and nowhere else.
Scale is applied per prop instance, so TIKIs stay at scale 1.

## Runtime prop lighting

A converted model's origin sits over its bounds centre, 16 units above its top
(`modelconv.convert_model(centre=True)`): the engine lights a non-solid
`script_model` from 8 units below its origin with one sun trace
(`docs/reference/engine.md` §5.2). From the Source pivot (on the floor), the rubble in
the first dust2 drafts was black; from the bounds centre, cars got ambient light only,
because the trace from inside their own collision hull entered another hull brush.
(The rubble stayed black after the re-centring because those sheets were shot at
`r_fastentlight 1`, grid only; at retail high the centred rubble was lit. The pivot rule
matters for the sun trace, and for players on low/medium.)
Instances are moved by `R(angles) * pivot` so they stay where Source put them.

Collision hulls (`.phy` pieces → `modelconv._hull_brush`) must not depend on the pivot.
They did until the near-coplanar face merge compared plane distances from the origin:
moving car002a's pivot merged two roof faces 2° apart and grew a hull by 20 units.
The merge now tests the triangle against the kept plane, and every plane is written
as three points 64 units apart around the hull centre's projection
(`tests/test_modelconv.py::test_hull_brush_translation_invariant`; dust2 props now
differ by ≤ 0.2 units between pivots, from near-parallel face conditioning).

## Static props without MOHlight (`mohkit.staticlight`)

Static models never collide (the collision loader skips them), so they don't need to
exist when Q3map runs: the converter adds each prop's clip brushes to the world,
compiles and lights the map, then `staticlight.inject` appends the props to
STATICMODELDEF, lists each in the leaves its bounds touch and writes per-vertex
colours to STATICMODELDATA. A vertex's colour comes from the map's own lightmaps
(`staticlight.LightmapField`, since 2026-10-01): every lightmap texel is binned into
16-unit cells by facing (six axis slots), and each vertex marches against each slot's
direction to the first texels facing that way (the floor under a crate lights its top),
blended by its normal and scaled by 1.78 (`LIGHTMAP_TO_VERTEX`). Against MOHlight's
own static-model colours on mk_medina (21k vertices): correlation 0.56 (light grid
0.41), mean error 45 (grid 51), and the quantiles match at 1.8-2.1x throughout.
Vertices that find no texel within 256 units fall back to the light grid (32-unit
cells, sampled 6 units out, `staticlight.shade`; means within 2% of MOHlight on an
ambient-only map and on mk_medina).

**Why not the light grid:** on cs_inferno (MOHlight-lit) the grid was far flatter than the
lightmaps: 4x brighter where they are darkest, 0.87x where they are brightest, so
grid-lit props lose contrast both ways. And MOHlight fills the grid without spotlight cones. A spot
aimed at the floor of a closed test room (`target` or `angles`, 60 degree cone) lights
a lit pool in the lightmaps, but the grid is a flat ramp that brightens with depth
below the lamp at any distance off-axis: 11 just under it, 58 at the floor (the floor
lightmap's peak is 59), even outside the cone. A point light's grid is uneven too
(113-254 above the lamp, 51-131 near the floor, brighter on one side of a symmetric room). dust2's tunnel crates near a ceiling spot got
grid values of 13-21 (black) while the floor around them was lit; the lightmap field
gives them 130-190. Players are fine at `r_fastentlight 0` (the engine default and retail high; the owner's
configs and a fresh home have 1, grid only): the engine also lights them from the light
entities at run time, and a third-person player under
that tunnel spot looked as lit as one in the sun. `tests/test_staticlight.py`.

OpenMoHAA draws every static model whose bounds pass the frustum test (the leaf
`visCount` check is commented out in `tr_staticmodels.cpp`); at most 8,192 static
surfaces a frame (`MAX_STATIC_MODELS_SURFS`). de_nuke's 4,801 props have 9,071 surfaces
in all, so only a view of nearly the whole map (the overview shot) can lose some.

**At most 4,095 static models and about 600 prop SKDs per map.** The renderer adds each
drawn static model's triangle count to `staticModelNumIndexes[4095]`
(`renderergl1/tr_model.cpp:33`, `:1560`), indexed by static model number, and packs that
number into 12 sort-key bits (`R_DecomposeSort`, `tr_main.c:1241`: `& 4095`). Model 4,095
and up write past the array every frame and draw with another model's transform:
de_inferno's 6,326 injected props crashed the game 16 s into an 8-bot match
(`R_PrintInfoWorldtris`, called on corrupted state). Separately, the skeleton cache holds
1,024 SKDs (`TIKI_MAX_SKELCACHE`, `tiki/tiki_shared.h:79`), shared with players, weapons
and effects; props past it never load ("No free spots open in skel cache"): de_nuke's
1,365 prop SKDs lost hundreds of props (2,807 such errors in its shot run).
`mohkit.staticmerge` keeps both budgets (3,500 instances, 600 SKDs): it merges one-off
models first (no geometry is duplicated), then the models cheapest to duplicate, per
1,024-unit cell, into rigid models with one surface bucket per shader; `prune` drops the
merged-away originals from the pk3. de_inferno: 6,326 models / 301 SKDs -> 3,436 / 253;
de_nuke: 4,801 / 1,365 -> 2,917 / 598, pk3 assets 262 -> 267 MB. `staticlight.inject`
refuses more than 4,095 static models; `finish_local` warns above 600 SKDs. Tried and
rejected first: merging the copies of each model per 512-unit cell (de_inferno 6,326 ->
2,920 models) turned 301 SKDs into about 1,600, since every merged model is an SKD of its
own: 1,236 "No free spots open in skel cache" in the shot run. Split pieces of big meshes
(`merge_split`) always merge, so the budget can't pull them back: on de_nuke 512-unit piece
cells gave 678 SKDs, 768 gave 597 (ordinary props keep 1,024-unit cells; `merge()` defaults
to 512, the stock profile uses 768). No console command lists the skeleton cache
(`code/tiki/` registers none), so the 600 budget (leaving ~400 for players, weapons and
effects) is a margin, not a measured figure.

**Props carry progressive LOD (`mohkit.lod`, since 2026-10-01).** With no VIS culling for
static models, a converted map drew its props at full detail at any distance: on de_cache
0.3-1.3 M prop vertices per frame, 70-85% of the frame time (`mohkit csgo de_cache --perf
2000 --toggle r_drawstaticmodels=0`; the cost follows vertices, ~19 ns each, not draw
calls). After `staticmerge`, `inject_statics` gives every prop SKD quadric-error collapse
tables and a `.lod` curve (engine rules: docs/reference/engine.md §5.2) and permutes each
instance's vertex colours to the new vertex order. The curve keeps the error under
`lod.TAU_PX` = 2 pixels at 1920 wide with retail's high preset (`r_lodscale`/`r_lodcap`
0.55); a player's lower presets simplify more. de_cache at 1280x720: mean 174 -> 268 fps,
worst camera 68 -> 138; shots differ from the full-detail build by under 1/255 (1 px) and
3/255 at the overview (2 px). Foliage cards keep their open edges, so trees and bushes
are now the largest remaining prop cost. `--resume --no-lod` builds without it.

**What a collapse costs (2026-10-02).** The quadric error is the distance to the original
*planes*, so on flat parts it is zero for collapses that still change what you see. de_nuke's
chain-link fence covers (flat panels with CS:GO's baked vertex lighting) went from 304
triangles to 8 "for free" and drew as dark grey sheets (their darkest corner colours spread
over the panel); window glass, ladders and railings vanished the same way. Collapses are now
ordered by a cost that also counts the texture slide on each surviving triangle (back through
the triangle's own mapping, in world units) and the shade change there (`lod.COLOR_STEP` = 12
levels costs the collapse's length, less in proportion; up to 8 instances' colours per SKD,
from `inject_statics`), both added up along collapse chains. The free level (collapses made
at every distance, `base_error`) must respect that full cost; the distance curve uses the
geometric error (`lod.ATTR_FAR` = 0), measured after simplifying by replaying 16 levels like
the engine (`lod.measured_errors`, ~0.6 s a mesh: a safety net for open objects that might
close gaps at zero plane error; on every model checked, the merged railing and two wire
clusters, it returned exactly the quadric errors. What fixed the railing, drawn in its
coarsest form everywhere because all 1,631 of its collapses cost under base error 4, was the
texture-slide term: free collapses at 4 units 1,631 -> 1,230). Tried and dropped: a flat
0.25 units per colour level kept nearly everything (576k prop vertices per view instead of
115k; 124 vs 168 fps interleaved); 0.5 x move length x change/255 let the fence covers
darken again; an isotropic texture-slide scale mis-weighted wires, which map ~6 units
around and hundreds along (about 20x their vertices kept). Counting texture and shading in the distance curve too kept 3.5x the vertices
(de_nuke 397k prop vertices per view instead of 115k); counting only the geometry
everywhere is what drew the dark sheets. de_nuke stock profile (s8): ~277k vertices per view
estimated (`mohkit.propcost`), fps level with the old stock build (two interleaved runs:
200 vs 202 mean, 148 vs 145 worst), shots match a no-LOD build. Every conversion before this
also drew shards: docs/reference/engine.md §5.2 (index-degenerate rule).

**Props vanish where CS:GO fades them (since 2026-10-01).** CS:GO fades most props out
by distance (sprp flag 1, `fademindist`..`fademaxdist`; `prop_dynamic` keys of the same
name): de_nuke 4,814 of 5,002 (median 1,578 units), de_inferno 5,893 of 6,379 (1,350), so
50-85% of the props in a view's frustum are ones CS:GO doesn't draw. The converter keeps
each prop's cut (the fade midpoint, `convert.fade_distance`; 6th field of `statics.json`),
and the LOD curve's last point becomes a vanish step: maxMetric = R x (100 / fovX) / cut,
where the engine pivots `r_lodscale`, so the distance holds at every detail preset
(`lod.lod_control(vanish=...)`, `tests/test_lod.py`). Per model the cut is the largest of its
instances' (none if any instance never fades); `staticmerge` merges only props of one fade
class (`FADE_CLASSES`) and a merged model vanishes at its class plus its farthest member's
offset. No shader per fade distance: OpenMoHAA has `alphaGen tikiDistFade near range`, but
the draw sort key holds 11 bits of shader number (`QSORT_SHADERNUM_SHIFT` 21 in a 32-bit
key, `tr_local.h`), so a level can use at most 2,048 shaders (de_cache loads 1,168 at spawn).
de_inferno 181 -> 250 fps mean, worst 91 -> 152 (two interleaved runs each), error vs
CS:GO unchanged (6.3 / 6.4). de_nuke gained less (88 -> 95): its cost is merged one-off
clusters (CS:GO's own `_autocombine_*` meshes, radius 800-1,300) that are near relative to
their size, so neither LOD nor the fade cuts much.

**Prop profiles (`--props balanced|stock`, `convert.PROP_PROFILES`; build with `--name`).**
Stock maps draw 6-19k vertices and 800-1,700 surfaces per view (mohdm1-4: 1,200-1,700 fps on
the harness, worst camera 513-1,042; the small mohdm6/7: 9,000-12,000 fps, 3-7k vertices);
converted maps draw 100-900k and 2-11k, and the converted world alone (props off)
already runs at 700-950 fps on de_nuke. The owner plays with `com_maxfps 250`, so "stock-like"
means a worst camera above 250 at their settings, not 1,200 (testing.md "Frame rate"). The profiles drop small props (by largest dimension;
bigger limits for props without collision and for foliage), give small never-fading props a
fade and cap all fades, collapse detail below `base_error` even up close, and raise the LOD
screen error. CS:GO's own mesh LODs don't help: 2 of de_nuke's 1,378 prop models ship more
than one. de_nuke with the profiles as they were on 2026-10-01 (stock: fades 1536, tau 6,
base error 2, the LOD before the shard and dark-panel fixes; two interleaved runs): full
97 / 65 fps (mean / worst camera), balanced 133 / 98 (871 props dropped), stock 210 / 155
(2,198 dropped); error vs CS:GO 5.6 / 5.5 / 5.7. `--props stock` is now the s8 row of the
table below (fades 1024 / 256, tau 10, base error 4, split 384 / 768).
Most of what remains is the merged `_autocombine_` clusters.

**Where a converted map's frame goes, and what was tried (de_nuke, 2026-10-02).** Stock-profile
build at 1280x720, mean over 38 cameras: world 1.3 ms, prop surfaces (culling, sorting,
per-surface calls) 0.4 ms, prop vertices 2.0 ms (`--toggle r_drawstaticmodelpoly=0` /
`r_drawstaticmodels=0`); stock maps draw 6-19k vertices per view, this build ~120-280k prop
vertices alone (`mohkit.propcost`). Static models are never VIS-culled, so props on other
floors and behind walls draw whenever they are in the frustum and inside their fade. About
60% of the prop geometry in view is CS:GO `_autocombine_` meshes (pipes 19%, wires 18%, roof
trusses 12.5%, ducts 6.5%); they are boxy, so only 9-30% of their vertices collapse under
8 units: LOD can't shrink them. Tried, with interleaved timings (same machine, same run):

| change | prop verts / view (est.) | fps mean / worst | look |
|---|---|---|---|
| stock profile (fades 1536, tau 6, base error 2) | 213k | 233 / 175 | shards, dark panels (LOD bugs, fixed since) |
| LOD tau 10, base error 4 | 125k | 272 / 208 | same bugs, worse |
| + split big models into 768 cells (`merge_split`) | 120k | not timed | barely helps: pieces still visible from everywhere |
| + fades 1024, then the LOD fixes (s8, now `--props stock`) | 277k | 200 / 150 vs 202 / 145 for row 1 | matches a no-LOD build |
| s8 + fades 768 + overhead wire meshes dropped (s9) | 166k | 266 / 194 vs 200 / 150 | A-site silo vanishes (cap hit a landmark), power lines gone |

Not done, with the reason: per-shader `alphaGen tikiDistFade` culling skips surfaces before
sorting, but only the 0.4 ms surface part (shaders aren't the obstacle: de_nuke's props use
151, its world 314, of 2,048); counting texture and
shading in the LOD distance curve kept 3.5x the vertices. Next idea: props as world
triangle-soup surfaces (the renderer loads `MST_TRIANGLE_SOUP`, `tr_bsp.c:1634`) so VIS culls
them, with real VIS for the world (`--structural`); untested. A fade cap must scale with prop
size, or landmarks vanish.

## Lighting: CS:GO's own baked light (default since 2026-10-01)

Lit builds no longer run MOHlight. Q3map compiles BSP and VIS only (it allocates the
lightmap pages), then `mohkit.source.lighting.transfer` fills them from the Source map's
own VRAD lighting, and the light grid and every prop are lit from the same data. de_inferno
builds in about 7 minutes instead of 15+ (its light stage alone took 674 s), de_nuke in
about 20 instead of an hour. `--mohlight` keeps the old path (converted `light` entities,
texlights and sky fill lit by MOHlight).

**Why.** Converted lights can't reproduce VRAD. MOHlight's point light is
`7500 * I * cos / d^2` *in display space*, capped at a stored 127 (measured, `docs/lighting.md`);
VRAD's is `brightness/255 * (100/d)^2` in *linear* space, which the display gamma turns
into roughly `1/d^0.9`. So converted lamps were flat white near the lamp and dark between
lamps, texlights stacked more lights on top, and the sky fill was a guess. Measured on
the same 31 CS:GO cameras of de_inferno (`csgo-ref`, `exposure`): per-camera mean
brightness correlated with CS:GO's at 0.12 before and 0.75 after; mean error 31 -> 19
(of 255). Halls went from 107 (blown, flat) to 51 (CS:GO 56), Banana from 45 to 52-60.

**Lightmaps.** Every lit face's style-0 lightmap (`LIGHTING_HDR`, lump 53, addressed by
`FACES_HDR`, 58; `ColorRGBExp32`: `c / 255 * 2^exp` linear) becomes luxels with a world
position: planar faces solve the lightmap vectors for `lm_mins + (s, t)`; displacement
luxel (s, t) sits at grid parameter (s / S, t / T), t along corner 0 -> 1 and s along
0 -> 3 from the start corner (VBSP `CCoreDispSurface::CalcLuxelCoords` gives the corners
luxel coords (0,0), (0,T), (S,T), (S,0); checked against seam continuity with flat
neighbours: 0.35 median log error vs 0.55-0.75 for the 7 other orientations). Bumped faces
store the flat lightmap first. **A face's lightmap is the rectangle around its polygon and
VRAD leaves luxels well outside the polygon black**: those are dropped (more than 0.75
luxel outside an edge); before that, de_inferno's sunlit CT floor had round black
blotches at face corners. Each MOHAA texel (`staticlight.lightmap_texels`, padding
included) takes the luxels within 24 units, weighted `facing / (1 + d)^2`: first those on
its plane facing the same way (88% of de_inferno's texels), then near its plane, then any
facing within 60 degrees, then anything within 96 units, then (coarse Source lightmaps) any
luxel within 192 units. Lightmap density is 16 (pages: de_inferno 87, de_nuke 134; the
renderer takes 256 and the transfer refuses more). A face whose Source luxels are coarser
than 1.5x the map's density gets `surfaceDensity` = its luxel size (at most 256,
`Converter._density`): finer MOHAA texels would only interpolate the same CS:GO light and
cost pages (de_vertigo's 128-unit facade luxels: 1.25M texels / 151 pages -> 382k / 48).
Maps compiled without HDR (de_rats_1337_v2, 2016) have no lump 53: the transfer reads
`LIGHTING` (lump 8) with the normal face lump, and prop light from `sp_<index>.vhv`.
Correlating luxel brightness with a displacement's sun facing was no test of the luxel
orientation (all 8 orientations within -0.09..0.18: cast shadows dominate); seam
continuity with flat neighbours was. To debug a transferred lightmap, splat the Source
luxels top-down next to the MOHAA texels of the same box, project the bad pixel's ray back
onto the luxels and dump the source face's raw luxel rectangle (that showed de_inferno's
black luxels outside the polygon).

**Exposure and tone curve.** CS:GO auto-exposes between the `SetAutoExposureMin/Max` its
`logic_auto` sends to `env_tonemap_controller` (de_inferno 0.75-1.5, de_nuke 0.75-1.15,
de_dust2 0.7-3, de_cbble 0-0.9); `exposure_for` takes the geometric mean (half the
maximum when the minimum is 0). That rule left every map 5-17% darker than CS:GO's own
shots, so `python -m mohkit csgo <map> --fit-exposure` re-lights the last build
(`resume_local`, ~1 min plus re-shooting per step) until the median per-camera brightness
ratio against the `csgo-ref` shots is within 2% (first step ratio^2.2, then secant steps;
2-3 in all) and keeps the value in `data/csgo_exposure.json`, which `lighting.transfer`
uses before the rule. Fitted values are 1.07-2.5x the rule (de_inferno 2.69 vs 1.06,
de_dust2 2.32 vs 1.45, de_mirage 1.09 vs 1.02). Fit last, after every texture or lighting
change (de_dust2's blends moved it from 2.53 to 2.37), and only from clean shots: the first
fits were made while installed pk3s leaked into the test game and had to be redone. A texel stores `127 * (exposure * L)^(1/2.2)` (MOHAA
multiplies the sRGB texture by the doubled lightmap, Source the linear albedo by linear
light), rolled off smoothly from 0.82 so bright areas keep their gradients.

**Headroom.** MOHAA can't show a lit surface brighter than its texture (127 doubled),
but CS:GO's sunlit floors are lit 1.5-2.5x (displayed ~1.3-1.5x). So every lit texture is
brightened by `headroom_gain` (up to 1.6, as far as its 99.5th-percentile texel stays
under 250) and the light on its surfaces is divided by the same gain
(`report["texture_gain"]`, applied per BSP surface and per prop vertex): shading is
unchanged below the old cap, and sunlight reaches up to the gain. Additive, unlit,
translucent world and water materials are not brightened.

**Props.** VRAD bakes every static prop's vertex lighting into the map's pakfile
(`sp_hdr_<prop index>.vhv`, `HardwareVerts::FileHeader_t`: 40-byte header, 28-byte mesh
records `lod, vertexes, offset`): one stream per body part, model, VTX LOD, mesh and strip
group, in that order (`studiomdl.vhv_layout`, matched 400 of 400 sampled de_inferno props);
CS:GO writes 3 colours per vertex (bump basis), each 4 bytes B, G, R,
`255 * 0.5 * linear^(1/2.2)` (mathlib `lineartovertex`, OVERBRIGHT 2), then the sun share
(vradstaticprops.cpp `SerializeLighting`). The converter keeps each SKD vertex's source
(body part, model, mesh, mesh vertex id) through `modelconv.weld`/`split_surface`
(`ConvertedModel.vertex_source`), averages the 3 colours in linear light and stores
`prop_light.npz`; injection puts them through the same tone curve as the lightmaps
(6,269 of de_inferno's 6,326 props). Sampling the floor under a prop does not work with
these lightmaps: VRAD bakes the prop's own shadow there, and props went black. Props
without a `.vhv` (`prop_dynamic`) are lit from the lightmaps at scale 1.0.

**Prop tints.** CS:GO tints props per instance (`sprp` DiffuseModulation; `rendercolor` on
`prop_dynamic`): 2,569 of de_nuke's 5,002 props (yellow rails, grey 168 pipes, blue-grey
boxes) and 2,193 of de_inferno's. They were all drawn white. The tint now multiplies the
vertex colours, weighted per material by how much of it the tint covers: all of it, the
mean of the base alpha for `$blendtintbybasealpha` (the tint follows that mask; vertex
colours can't, so the mask's average stands in), none for `$notint`.

**Light grid.** Built without MOHlight (`lighting.build_grid`): 32-unit cells over the
world model's bounds, a cell is open when its centre's leaf has a cluster
(`point_leaves`, BSP descent; de_inferno: 94% agreement with MOHlight's own grid), coloured
with the mean of the light arriving along the six axes and the brightest of them
(`LightmapField`), quantised to 255 palette entries (k-means), RLE-encoded
(`encode_grid`; round-trips MOHlight's grid exactly, but shares nothing across columns, so
its data lump is ~2.4x MOHlight's: 1.40 MB vs 585 KB on cs_inferno). Only open cells within
3 cells (96 units) of a lightmap texel are sampled; the rest take their sampled neighbours'
mean, then the median (players and models are always near surfaces): de_nuke's grid 469 s ->
47 s. Drawvert colours (`rgbGen vertex`
surfaces) come from the luxels too.

**Results (2026-10-01, all maps rebuilt this way, same cameras as CS:GO's own shots):**
per-camera mean brightness, mean absolute error against CS:GO (0-255) and correlation.

| map | CS:GO mean | before (MOHlight) | after (transfer) | build (BSP + light) |
|---|---|---|---|---|
| de_dust2 | 113 | 71, error 52, corr -0.36 | 96, error 17, corr 0.96 | ~12 min (was ~55) |
| de_mirage | 100 | 77, error 35, corr 0.05 | 95, error 6, corr 0.97 | ~8 min (was ~45) |
| de_nuke | 96 | 131, error 38, corr -0.05 | 90, error 7, corr 0.95 | ~6 min (was ~57) |
| de_inferno | 95 | 72, error 31, corr 0.12 | 79, error 19, corr 0.75 | ~7 min (was ~15) |
| de_cache | 106 | 79, error 34, corr -0.38 | 95, error 13, corr 0.84 | |
| de_vertigo | 92 | (new) | 86, error 10, corr 0.88 | 4 min |
| de_cbble | 75 | (new) | 65, error 10, corr 0.99 | 9 min |

These are before the exposure fit; after it the errors are 4.1-10.7 (README table: mirage
4.1, cbble 4.8, dust2 4.9, nuke 5.6, inferno 6.4, cache 9.6, vertigo 10.7). What remains is
mostly CS:GO's bloom, detail textures and phong, which are not converted. Lightmap pages may pass
170 now (de_cbble: 190): that limit was MOHlight's buffer; the renderer takes 256
(`MAX_LIGHTMAPS`, `renderergl1/tr_local.h:1182`) and de_cbble loads and plays.

**Reference shots.** `python -m mohkit csgo-ref de_nuke` runs the CS:GO client in
`csgo_dir` windowed, drives it over `-netconport`, and saves `jpeg`s from every named
camera into `local/csgo/<name>/csgo_ref/` (restoring `config.cfg`/`video.txt`). Compare
them with the conversion's shots (`local/csgo/<name>/shots/`, same names) using
`python -m mohkit exposure`. Run one CS:GO process per map (a `map` command over netcon
closes the client) and never start one while another `csgo_osx64` lives: launches that never
opened the netcon port sat at ~120% CPU and needed `kill -9` (2026-10-01; with stdout logged
to a file and 5 s between maps every run loaded in ~12 s). `-condebug` appends to the game's
own `csgo/console.log`, `screenshot` (not `jpeg`) leaves TGAs in `csgo/screenshots`, and
the launcher's `mac_launcher.cfg` sets `bot_quota 18` (bots are kicked). Workshop maps ship
no cameras file, so they get no reference shots. Source's own code for encodings is on this
Mac: `~/source-engine/` (VRAD `utils/vrad/lightmap.cpp`, `vradstaticprops.cpp`,
`mathlib/color_conversion.cpp`, `public/builddisp.cpp` `CalcLuxelCoords`) and the Kisak
CS:GO tree under `~/Documents/Codex/2026-09-21/https-github-com-swagsoftware-kisak-strike/work/source/`
(missing some definitions); find files with `mdfind -name <file>.cpp`.

## Known gaps

- Prop tints that follow a texture mask (`$blendtintbybasealpha`) are averaged over the
  material: exact masks need tinted texture variants per tint (TIKI shader overrides). Only
  two materials in the seven maps have a partial mask (de_inferno's flower sets, 65%;
  de_cache's plants, 12%); the rest are fully tinted or untinted, which is exact.
- 4-way blends (`Lightmapped_4WayBlend`) use the first layer only. `$blendmodulatetexture`
  blends are alpha-tested, so their edges are hard where CS:GO's `smoothstep(g - r, g + r)`
  band is soft: visible on de_dust2 and de_cache masks (r ~0.39), near exact on de_inferno
  (r 0.03-0.08); the vertex alphas are right (corr 0.995 with the Source displacement
  alphas, dust2); `$blendmasktransform` is ignored. A dithered second stage would cost a
  pass per blend surface: not done.
- Bots never climb the step-column ladders (the navmesh links only `func_ladder`s), so on
  ladder-heavy maps (de_rats: 30) bots stay on their floor. Untested idea: a `func_ladder`
  in front of each column as the bots' link.
- de_rats_1337_v2: 25 of 30 ladders climb. Ladder 25's volume hangs ~600 units above any
  floor, 14 has no model and no clear start, 6, 9 and 15 stop ~53 up under overhangs.
- de_vertigo's portal sky is dark navy above the city in some views (T spawn window,
  overview) where CS:GO is light blue, and by the numbers it matches CS:GO worse than its 2D
  sky did (error 9.9 -> 10.6, corr 0.88 -> 0.79, 10 cameras). It began when the sky room
  became structural; suspects: the 2D sky box size in the portal view (`tr_sky.c`,
  boxSize = zFar / 1.75) and the missing sky_camera fog (143 172 186). Open.
- The other six 3D skyboxes are lost (one fixed eye can't show them). Untested idea: shoot
  CS:GO's skybox as a cubemap (six square 90-degree `csgo-ref` shots from the skybox eye) and
  use it as the 2D sky. When a room falls back to the 2D sky its props' models still ship
  in the pk3 (de_cache: bloat only).
- Door handles and other relief of door and vent models are lost (slabs). Vents break
  (`func_window`, metal debris) instead of swinging open.
- Detail sprites (grass) are dropped.

## Measured builds (2026-10-01, Apple Silicon, three or four builds sharing 10 cores)

| map | quality | props injected (vertices) | overlays | BSP | VIS | light | shots | bots (8, 90 s) |
|---|---|---|---|---|---|---|---|---|
| cs_dust2 | draft (density 32) | 1,574 (842k) | 459 | 559 s | 1 s | 1,962 s | 32 named cameras, 47 s | 75 kills |
| cs_nuke | unlit | 4,801 (5.6M) | 718 | 261–489 s | 1 s | — | 38 named cameras, 59 s | 83 kills |
| cs_nuke | fastrad (04:43 code, spot fix; alone on the CPU) | 4,801 (5.6M) | 718 | 200 s | 1 s | 2,389 s | 38, 59 s | 70 kills |
| cs_dust2 | fastrad (03:15 code) | 1,574 (842k) | 459 | 684 s | 2 s | 2,752 s | 32, 47 s | 91 kills |
| cs_mirage | fastrad (03:13 code) | 1,470 (1.35M) | 512 | 293 s | 1 s | 2,672 s | 30, 45 s | 77 kills |

de_nuke's draft light at density 16 had reached 1% after 6 minutes; at density 32 the
first 10% still took ~15 minutes (progress is not linear: the slow part comes first).
