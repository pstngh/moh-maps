# Entities

The entities a DM/TDM/objective map actually needs, with the keys that matter.
[reference/entities.md](reference/entities.md) lists every classname and key used
in the stock maps, and [reference/engine.md](reference/engine.md) §4–5 has
source citations.

General rules:

- Every key/value becomes an event on spawn. `#key` sets a numeric script
  variable and `$key` a string one (`$type wood`).
- `angle` is yaw only (−1 = up, −2 = down); `angles` is "pitch yaw roll".
- Spawnflag 2048 (NOT_DEATHMATCH) removes an entity in all multiplayer modes.

## worldspawn

| key | effect |
|---|---|
| `message` | level title |
| `suncolor`, `sundirection`, `sundiffuse`, `sundiffusecolor`, `ambientlight`, `lightmapdensity`, `overbright` | **compiler** lighting keys, see [lighting.md](lighting.md). The renderer also reads `suncolor`/`sundirection`/`ambientlight` to light models |
| `farplane` N | fog and far-clip distance (0 = off). Sent to original AA clients too |
| `farplane_color` "r g b" | fog colour, 0–1 |
| `farplane_cull` 0/1/2 | none / standard (default) / portal sky only. Use 0 to fog without culling |
| `gravity` | default 800 |
| `soundtrack` | a `music/*.mus` file (usually set by `global/ambient.scr`) |
| `skyalpha`, `skyportal` | sky blending; a portal sky needs a `script_skyorigin` |

## Spawn points

| classname | used by |
|---|---|
| `info_player_deathmatch` | FFA (`g_gametype 1`) and spectators |
| `info_player_allied`, `info_player_axis` | TDM, round-based, objective (`g_gametype` ≥ 2) |
| `info_player_start` | fallback, and `map dm/x$name` starts |
| `info_player_intermission` | end-of-match camera (`angles` or `target`) |

`origin` is the feet: place it 1 unit above the floor. The game spawns at
origin + (0 0 1) and telefrags whoever is there. In FFA the spawn farthest
from enemies is chosen; team modes prefer far from enemies and near friends. If
a gametype finds no spawn of its class and there is no `info_player_start`, the
map fails to load.

## Lights

`light`: see [lighting.md](lighting.md). Key facts: `light` intensity
(default 300, stock 3–300), `_color` "r g b" 0–1, spotlights via `target` →
`info_null`, `spawnflags 1` linear falloff, `2` world only, `8` entities only.
The game deletes lights at spawn; they only matter to MOHlight.

## Props

`static_<name>` entities with `"model" "static/foo.tik"` (path relative to
`models/`; MOHRadiant writes `static//foo.tik`, and either works). Keys:
`origin`, `angle` or `angles`, `scale`, `spawnflags`. `testanim idle` is
editor-only.

- Q3map moves them out of the entity list into the BSP's static-model lump;
  MOHlight lights them per vertex. Scripts can't see them.
- **Collision is not automatic.** The engine never collides with static
  models. Q3map instead looks for `models/<same path>.map` (clip brushes in model
  space) and bakes it into world collision. 274 of 1,055 stock props have one
  (`mohkit.props.get(name).collision`). Props without it are ghosts to
  players, bullets and bots: add `common/*clip` brushes yourself.
- The classname is cosmetic (Radiant derives it from the TIKI's QUAKED line,
  e.g. `static_item_indycrate`); `mohkit` fills it in from the catalog.
- The pivot is usually the base. Hanging lamps (`lights/hanglamp.tik`) pivot at
  the *bottom* of the shade. `MapBuilder.prop(..., hang=True)` handles it.
- Use `python -m mohkit.propview static/wagon lights/hanglamp` to render any
  props in a test room with a +X arrow and a 64-unit ruler.
- `script_model` is a runtime (scriptable, animated) model. It must be
  precached (`cache models/x.tik` in `_precache.scr`).

## Doors

`func_rotatingdoor` (brush entity):

- It needs a `common/origin` brush on the hinge line. `angle` points from the
  hinge toward the door's middle.
- `openangle` 90, `doortype wood|metal` (sounds and speed), `alwaysaway 1`,
  `time 0.8`, `wait 1`. Stock maps use exactly these.
- Spawnflags: 1 START_OPEN, 32 TOGGLE, 64 AUTO_OPEN.
- Bots don't see doors in their navmesh.

`func_door` slides (`angle` = direction, `lip` 8, `speed` 100).
Locked-door prop, as in stock maps: a `trigger_use` with `targetname
door_locked` and `$type wood`, plus `exec global/door_locked.scr::lock` before
`level waittill spawn`.

## Static props without MOHlight (`build --inject-props`)

MOHlight lights `static_*` props per vertex on one thread at about 190 vertices a second
(mk_medina's 107 props: ~55 minutes of its light stage). `python -m mohkit build maps/x
--inject-props` holds them back: their collision `.map` brushes go into the world (where
Q3map would have baked them), the map compiles and lights without them, and
`mohkit.staticlight` adds them to the BSP afterwards with vertex colours taken from the
map's lightmaps (light grid where none reach; docs/csgo-conversion.md). The colours
match MOHlight's on average but have no per-vertex shadows, so
compare a sheet before preferring it for a finished map. Tried on a copy of mk_medina
(2026-10-01, draft): 107 props injected with 501 collision brushes, every TIKI read, and
the sheet showed palms, carts, the car and café chairs lit in keeping with the walls
around them (`dist/mk_medinai_shots.png`).

## Ladders

`func_ladder` is a brush entity that covers the climbable face, with an origin
brush **on the face, horizontally centred**. `angle` points into the wall (the
direction the climber faces). Stock ladders are 28–64 wide. `surfaceparm
ladder` does nothing.

## Triggers, breakables, sound

- `trigger_multiple`, `trigger_once`, `trigger_use`, `trigger_hurt`,
  `trigger_push`, `trigger_teleport` → `func_teleportdest`: keys `setthread
  label` (runs a script thread), `target`, `wait`, `delay`, `cnt`, `message`.
  Spawnflag 128 = shoot to fire.
- `func_crate` (`health`, `debristype` 0–3), `func_barrel` (`barreltype
  water|oil|gas`), `func_window` (`health`, `debristype`).
- Stock MP maps make ambient sound in script (`loopsound` on a `script_origin`)
  rather than with `sound_speaker`.

## Script helpers

`script_origin` (invisible point), `script_object` (brush model you can move or
hide), `info_notnull` (persistent point), `info_null` (compile-time target,
removed at spawn).

## Don'ts

- No `func_detail`: it becomes a generic game entity that renders black (see
  map-format.md). Use `+surfaceparm detail`.
- No `misc_model`: the game deletes it and Q3map ignores it.
- `info_pathnode` is only needed for legacy bots or single-player AI; OpenMoHAA
  bots use the generated navmesh.
