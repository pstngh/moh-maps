# Lighting

MOHAA lighting is baked by **MOHlight 1.48** into 128×128 lightmaps (world), a
32-unit light grid (players, props, dynamic models) and per-vertex colours
(static props). Everything is controlled by worldspawn keys and `light`
entities.

## The four roles

Good stock maps separate four jobs. Copying one "brightness" everywhere gives
a flat, tan, washed-out look.

1. **Sun**: direction and warm/neutral colour. It casts the shadows that give
   shape.
2. **Sky fill** (`sundiffuse`, `sundiffusecolor`): soft light from the whole
   sky, usually cooler than the sun, so shadows are blue-grey rather than black.
3. **Ambient floor** (`ambientlight`): a small constant (5–15). Too high and
   everything goes flat.
4. **Fixtures**: `light` entities at actual lamps (hanging lamps, wall
   lanterns, windows at night). Radiosity (8 bounces by default) carries
   daylight through windows and doors.

Never place fill lights over spawns or on an even grid.

## Worldspawn keys

| key | format | meaning / stock range |
|---|---|---|
| `suncolor` | "r g b" | sun colour **and** intensity. EA: "full daylight would be 70 70 70". Stock 15–110; Palermo uses 170 145 100 |
| `sunlight` | "r g b" | older synonym (mohdm1/mohdm3) |
| `sundirection` | "pitch yaw 0" | direction **toward the sun**. Pitch is Quake-style, so negative or 270–360 = above the horizon: `315 210 0` is 45° up, facing yaw 210. `-90` = overhead |
| `sundiffuse` | float | strength of the sky fill (0.5–2, usually 1–1.5) |
| `sundiffusecolor` | "r g b" | fill colour, same scale as suncolor (cooler: 56 62 78, 70 70 90) |
| `ambientlight` | "r g b" | constant light floor, 0–255 scale. Stock 3–20 |
| `ambient` + `_color` | float + "r g b" | alternative ambient (obj_team2: 35 with 1.0 0.9 0.8) |
| `lightmapdensity` | units per luxel | default 32. 16 is sharper (4× the lightmap memory); 64+ for huge outdoor maps |
| `overbright` | none/world/entities/all | overbright control (stock mohdm1: all) |
| `farplane`, `farplane_color` | units, "r g b" 0–1 | fog distance and colour, a big part of the mood |

Per face: `surfaceDensity N` in the `.map` overrides lightmap density.

## Recipes from the stock maps

| mood | suncolor | sundirection | sundiffuse / color | ambientlight | farplane / color | example |
|---|---|---|---|---|---|---|
| clear day | 70 70 70 | 315 210 0 | 1 / — | 8–10 grey | 4000–5000 / .333 .333 .329 | mohdm2, obj_team1, obj_team4 |
| warm Mediterranean | 110 100 90 | 238 210 0 | 1 / — | 20 20 20 | 5000 / .4 .5 .6 | MP_Brest_DM |
| hot noon | 170 145 100 | -50 210 0 | .8 / 90 90 110 | 1 1 2 | 6000 / .4 .4 .37 | mp_palermo_obj |
| golden evening | 100 60 20 | -15 225 0 | 1.1 / 70 70 90 | 8 8 10 | 4000 / .036 .024 .036 | mp_montecassino_tow |
| overcast / storm | 30 30 29 | -90 275 0 | 1 / — | — | 1985 / .34 .34 .34 | MP_Gewitter_DM |
| interior-heavy daylight | 85 85 85 | -90 90 0 | 1 / 85 85 85 | 20 19 18 (+ `ambient 50`) | — | mohdm6 |
| night | 25–35 (bluish 30 30 45) | -30 300 0 | — | 5 5 6 | 2400–3000 / .03 .05 .09 | MP_Flughafen_TOW, mp_ship_lib |
| snow night | 30 30 38 | -70 110 0 | — | 3 3 4 | 1500 / .1 .1 .12 | MP_Verschneit_DM |
| hot afternoon, narrow lanes (mohkit) | 160 140 104 | -55 225 0 | 1.6 / 84 92 116 | 20 18 16 | 9000 / .74 .68 .58 | mk_medina (sundiffuse 1.25 and ambient 16 15 15 left its lanes too dark on a preview sheet; alley `kit.wall_lantern` 190) |

Match the sky shader to the mood: `sky/mohday1`/`mohday2` (day), `sky/m5l2`,
`sky/norway_dawn`, `sky/d-day2`, `sky/africanight`, `sky/mohnightfog`,
`sky/allgrey`.

## `light` entities

| key | meaning |
|---|---|
| `light` | intensity, default 300. Roughly how far the light reaches, in units. Stock fixtures: 50–300 (mohdm6 uses 150 everywhere) |
| `_color` | "r g b" 0–1, e.g. warm lamp `1.0 0.86 0.66` |
| `spawnflags` | 1 linear falloff (`falloff` rate), 2 world only (`no_entity_light`), 4 trace to entities, 8 entities only |
| spotlight | `target` an `info_null`, or `angles` + `radius`; `spot_angle` = cone (default 45) |
| `overbright_range` | 0.01–2.5, default 1 |

**Falloff (measured, MOHlight 1.48, 2026-10-01):** one light per closed room at height h
above the floor, `-fast -bounce 0`, floor lightmap read straight below and along the floor:
stored value = `7500 * light * cos(angle) / d^2`, capped at **127** (light 50 at 64 units:
94 measured, 91.5 predicted; 150 at 128: 69 vs 68.7; 300 at 256: 34 vs 34.3; 800 at 512:
22 vs 22.9). That is Q3map's point light (`pointScale` 7500) in **display space**: the
renderer doubles lightmaps (`r_mapOverBrightBits 1` minus `r_overBrightBits 0`,
`R_ColorShiftLightingBytes`), so 127 = the texture's own colour and nothing is brighter.
`light 300` reaches full brightness at about 130 units and a quarter at 265. The linear
flag (`spawnflags 1`) ends abruptly (`300` lights 0 past ~190 units). Static-model
vertex colours and the light grid are doubled the same way (`tr_staticmodels.cpp`
`R_InitStaticModels`, `R_GetLightingForDecal`).

Placement: just under or in front of the fixture model, never inside a wall
(`validate` warns). Budget ≤ 60 lights reaching any spot. MOHlight clamps
beyond that ("Num lights per leaf clamped"), so cluster dense fixture fields.

## Quality settings

- `draft` (`-fast -bounce 0`): no radiosity, for checking geometry. `-fast` on
  its own still runs the radiosity pass: in a test room its lightmaps matched
  `-fast -bounce 2` (mean difference 0.07 of 255) and not `-bounce 0` (0.89), and
  mk_medina spent 584 s in it. So draft adds `-bounce 0` (2026-09-30).
- `preview` (`-bounce 2`): radiosity with 2 bounces; on mk_village it looks the same as
  `normal`. Re-checked at retail high detail (2026-10-01, same 9 cameras): mean
  brightness within 2.5% on 8 shots, interiors within 1.2%; the warehouse was 11%
  brighter in preview, but that build had newer source than the normal one. Use it to
  judge lighting quickly.
- `normal`: 8 radiosity bounces, so light through windows and doors reaches
  interiors. This is the one to judge lighting by.
- `final` (`-final`): full detail; use for release builds.

Interiors lit only by radiosity are dark in draft builds. Don't compensate
with fill lights until you have seen a normal build.

## Limits

- 170 lightmap pages of 128×128 per map when MOHlight lights it (its 8 MB buffer; tested 2026-09-30: 170 pages compile, 172 fail; 0x800000 / 49152 = 170.7). Exceeding it is a hard failure. The renderer itself takes 256 (`MAX_LIGHTMAPS`), which maps lit without MOHlight may use (de_cbble's transferred light: 190). Use
  coarser `lightmapdensity` (32 or 64) on big maps and big faces rather than
  making surfaces `nolightmap` (unlit detail looks fullbright).
- Radiosity needs VIS data. A map whose only structure is a shell still gets
  bounce light, but compiles slower.
- Static props are lit per vertex. 161k lit vertices lit fine in a test map; one crash near
  ~81k was seen on the full de_dust2 conversion (cause unknown), so the converter budgets 70k.
- **Static-prop lighting is slow and single-threaded.** MOHlight lights every
  static-model vertex on one thread: ~26 s per 4,958-vertex tank (~190 vertices/s)
  in a one-light test room with `-fast` (timestamped log), and far slower on a big
  map with many lights. Budget static-prop vertices for compile time. Props as
  `script_model` cost nothing at compile time (the engine lights them from the
  light grid at run time). `build` (by default) and every CS:GO conversion add the
  props after the light stage with vertex colours from the lightmaps
  (`mohkit.staticlight`): seconds instead of MOHlight's static phase, the same
  brightness, less self-shading (`docs/entities.md`; `--mohlight-props` opts out).
- **The light grid ignores spotlight cones** (MOHlight 1.48; test room, 2026-10-01):
  below a spot aimed at the floor the grid ramps up with depth at any distance
  off-axis (11 just under the lamp, 58 at the floor), while the lightmaps show the
  cone. Static props lit from the grid went black next to a CS:GO ceiling spot, so
  injected props use the lightmaps instead (`docs/csgo-conversion.md`). Players are not
  affected in practice: at `r_fastentlight 0` (retail high) the engine also lights them from
  the light entities at run time, and one under that spot looked as lit as one in the sun.
  At 1 (a fresh home's value, and the owner's) they are lit from the grid only.
- **CS:GO conversions don't use MOHlight any more** (2026-10-01): their lightmaps, grid and
  prop colours are CS:GO's own baked light (`docs/csgo-conversion.md`, "Lighting"). Source
  light falls off with d^2 in linear space (about 1/d^0.9 on screen), which no MOHlight
  light can match.
- **Converted Source lights** (`--mohlight` only). `light_spot` aims along VRAD's direction (z = +sin(pitch));
  an earlier converter aimed ceiling spots at the ceilings and Nuke's interiors were dark.
  MOHAA's `light` value is roughly its reach in units, so converted lights use 1.5 x the
  Source brightness, and MOHlight keeps at most 60 lights per leaf.
- **Where light time goes on a big map.** mk_medina (one thread, 2 bounces,
  2026-09-30) took 3,215 s: initial (direct) lighting 1,020 s + 111 s, one radiosity
  pass 584 s, light grids 9 s, and about 1,450 s in the static-model phase (107
  models, 28,193 vertices; MOHlight prints no time for it). Direct and bounce time
  grow with the lightmapped area: the hill-terrain ring and the building backs
  seen from it are a large share of medina's surfaces, so keep the backdrop
  small and give it a coarse `surfaceDensity` (32–64) rather than `nolightmap`. On
  mk_medina, shrinking the hill ring from 1,536 to 1,024 units and the sky top from 1,664 to
  1,088 cut direct lighting from 955 s to 574 s (one thread). `Material(..., density=N)`
  writes `surfaceDensity N` on every face of that material: mk_summit's fogged-out valley
  floor and distant peaks at 256 and its cliffs at 64 cut a draft light from 339 s to 136 s
  and the lightmaps from 65 to 25 pages (2026-10-02, idle machine, same map otherwise).
- **Surface lights are very slow.** `q3map_surfacelight N` in a shader makes its faces emit
  (retail: 24 shaders, 100-4,000, median 2,000, mostly lit windows). de_nuke's 43 emitting
  surfaces made a `-fast -bounce 2` light estimate ~15 hours. Use a point `light` per
  fixture instead (the converter puts one 8 units out from each emitting face, intensity
  sqrt(area x brightness) x 4).
