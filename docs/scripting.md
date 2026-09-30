# Map scripts and packaging extras

## What the game loads for `map dm/NAME`

| file | purpose |
|---|---|
| `maps/dm/NAME.bsp` | the level |
| `maps/dm/NAME.scr` | level script, run from the top when the level spawns (`main:` is a convention) |
| `maps/dm/NAME_precache.scr` | precache list, run first |
| `maps/dm/NAME.min` | loading-bar data. OpenMoHAA writes one after the first load; ship it for the original game (it can crash without one) |
| `ui/*.urc` menu named `dm/NAME` | custom loading screen (otherwise `loading_default`) |

Put MP maps in `maps/dm/` (DM, TDM, round-based) or `maps/obj/` (objective).
Sound aliases for MP only load when the map name starts with `dm`, `obj`, `moh`
or `train`.

## Minimal DM script

`mohkit` generates this (from `META` in `maps/<name>/build.py`) unless
`assets/maps/dm/<name>.scr` exists:

```text
main:

setcvar "g_obj_alliedtext1" "Village Crossroads"
setcvar "g_obj_alliedtext2" ""
setcvar "g_obj_alliedtext3" ""
setcvar "g_obj_axistext1" ""
setcvar "g_obj_axistext2" ""
setcvar "g_obj_axistext3" ""
setcvar "g_scoreboardpic" "mk_village"

	if(level.roundbased)
		thread roundbasedthread

	level waittill prespawn
	exec global/DMprecache.scr
	level.script = maps/dm/mk_village.scr
	exec global/ambient.scr mohdm1       // reuse a stock map's music and ambience
	level waittill spawn
end

roundbasedthread:
	level waittill prespawn
	level waittill spawn
	level.dmrespawning = 0
	level.dmroundlimit = 5
	level.clockside = kills          // axis | allies | kills | draw
	level waittill roundstart
end
```

`NAME_precache.scr` holds `exec global/DMprecache.scr`, plus `cache
models/…tik` for every runtime (`script_model`) model. OpenMoHAA prints "Add the
following line to the *_precache.scr" when one is missing.

## Useful script patterns

```text
// fog set from script instead of worldspawn
$world farplane 5000
$world farplane_color (.333 .333 .329)

// ambient loop at a point
local.s = spawn script_model model "fx/dummy.tik"
local.s.origin = ( 512 256 96 )
local.s loopsound amb_stereo_ambience          // any alias from ubersound
local.s notsolid

// locked doors (stock pattern): trigger_use targetname door_locked, $type wood
exec global/door_locked.scr::lock
```

## Objective maps

Model on `maps/obj/obj_team1.scr`. The script sets `level.defusing_team`,
`level.planting_team`, `level.targets_to_destroy`, round settings, waits for
`roundstart`, and runs `$bomb thread global/obj_dm.scr::bomb_thinker` on a
`script_model` bomb whose `target` is the object to destroy and whose
`$trigger_name` names its `trigger_use`. Keep team spawns (allied/axis) and
test in `g_gametype 4`.

## Scoreboard and loading picture

`g_scoreboardpic NAME` shows the shader `NAME`, which stock maps define in
`scripts/mohmenu.shader` as `textures/mohmenu/dmloading/NAME.tga`. Ship both a
shader and an image (256×256) in your PK3 to have one.
