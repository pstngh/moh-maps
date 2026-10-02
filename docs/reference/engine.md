# MOHAA / OpenMoHAA engine facts for mappers and map tooling (BSP v19)

Sources and how they are cited:
- **Engine source.** Paths are relative to `openmohaa-src/code/`, e.g. `fgame/bg_public.h:39`.
- **Retail data.** Cited as `PakN.pk3:path`; the paks are in `~/Documents/Games/moh/main/`.
- **EA material.**
  - Original QUAKED entity defs: `entdefs.pk3:code/X.cpp`, i.e. `MOHTools/entdefs.pk3`.
  - Original EA `.map` sources: `MOHTools/maps/MP/*.map`.
  - Compiler binaries: `Q3map.exe (strings)` (v1.34) and `MOHlight.exe (strings)` (v1.48). These are text strings pulled out of the Windows binaries, so they have no line numbers.
- **Measured from retail BSPs.** Cited as "measured: <map>". These values come from my own Python parse of the Pak5 BSPs.

Anything I could not confirm directly is marked **UNVERIFIED**. Units are Quake units. Per `Pak0.pk3:models/static/*.tik` ("world is in 16 units per foot"), 1 ft = 16 u.

---

## 1. Player and movement dimensions

### 1.1 Constants

| Item | Value | Source |
|---|---|---|
| Bounding box X/Y | mins −15, maxs +15 (30 u wide) | `fgame/bg_public.h:31-34` |
| Box bottom (MINS_Z) | 0; the origin is at the feet | `fgame/bg_public.h:38` |
| Standing box top (MAXS_Z) | 94 | `fgame/bg_public.h:39` |
| Crouched box top (CROUCH_MAXS_Z), used by retail AA | 54 | `fgame/bg_public.h:43`; retail state machine uses `modheight "duck"` → 54 (`Pak0.pk3:global/mike_legs.st`, 11×) and `fgame/player.cpp:8370-8372` |
| CROUCH_RUN_MAXS_Z (`modheight duckrun`) | 60; not used by the retail .st | `fgame/bg_public.h:44`, `fgame/player.cpp:8373-8375` |
| Prone box top | 20; OpenMoHAA-only. AA has no player prone | `fgame/bg_public.h:42`, `fgame/player.cpp:8376-8382` |
| Dead box top | 32 | `fgame/bg_public.h:41`, `fgame/bg_pmove.cpp:1024-1027` |
| Eye height standing (DEFAULT_VIEWHEIGHT) | 82 | `fgame/bg_public.h:46` |
| Eye height crouched | 48 | `fgame/bg_public.h:49` |
| Eye height at jump start | 52 | `fgame/bg_public.h:48` |
| Eye height crouch-run / prone / dead | 64 / 16 / 8 | `fgame/bg_public.h:47,50,51` |
| How AA maps maxs.z to pm flags | 60 → DUCKED; 54 → DUCKED+VIEW_PRONE (box 54, eye 48); 20 → VIEW_PRONE | `fgame/player.cpp:4038-4050`, `fgame/bg_pmove.cpp:1046-1066` |
| STEPSIZE (max step-up) | 18. If standing +18 is blocked, pmove retries at +9 | `fgame/bg_public.h:190`, `fgame/bg_slidemove.cpp:250-273` |
| No stepping while moving upward | Stepping is skipped while `velocity[2] > 0` unless you are on walkable ground | `fgame/bg_slidemove.cpp:255-258` |
| MIN_WALK_NORMAL | 0.7, so the steepest walkable slope is acos(0.7) = **45.57°** | `fgame/bg_public.h:188`, `fgame/bg_local.h:27` |
| Gravity | `sv_gravity` is registered as "512", but the World constructor sets **800** on every map load. The worldspawn key `gravity` overrides it | `fgame/gamecvars.cpp:361`, `fgame/worldspawn.cpp:570`, `:711-713` |
| Jump | The state machine calls `jump 56`. Player::Jump adds v = sqrt(2·g·h) = sqrt(2·800·56) ≈ **299 u/s**, so the apex is **56 u** at any gravity. `JUMP_VELOCITY 270` in bg_local.h is unused | `Pak0.pk3:global/mike_legs.st` (`commanddelay 0.05 jump 56`), `fgame/player.cpp:7920-7953`, `fgame/bg_local.h:29` |
| Run speed | `sv_runspeed` default "287", but it is reset to **250** when `sv_sprinton` is 0, which is the AA default | `fgame/gamecvars.cpp:396-418` |
| Walk / crouch multipliers | `sv_walkspeedmult` 0.6, `sv_crouchspeedmult` 0.6 | `fgame/gamecvars.cpp:397-399` |
| Multiplayer multiplier | `sv_dmspeedmult` 1.1 (applied when not single-player) | `fgame/gamecvars.cpp:399`, `fgame/player.cpp:4101-4103` |
| Weapon multiplier | Applied to speed: e.g. bazooka 0.7, kar98 0.94, mp40 1.0 (tik `movementspeed`) | `fgame/player.cpp:4088-4098`, `Pak0.pk3:models/weapons/*.tik` |
| Effective MP speeds (no weapon factor) | run 275, walk 165, crouch-run 165, crouch-walk 99 u/s | derived from the rows above |
| Air/ground physics | accelerate 8, air 1, friction 6, stopspeed 50, strafe ×0.85, back ×0.80 | `fgame/bg_pmove.cpp:35-48` |
| Terminal velocity event | 1200 u/s | `fgame/bg_pmove.cpp:293-316` |
| Lean (AA protocol, MP) | leanMax 40° (0 in single-player), speed 4, recover 15. The eye rotates about a pivot 28.7 u below it, so full lean shifts the eye about 18.4 u sideways and about 6.7 u down | `fgame/player.cpp:3733-3745`, `cgame/cg_predict.c:516-527`, `cgame/cg_view.c:376-382` |

### 1.2 Fall damage (AA protocol)

**How landing severity is computed.** PM_CrashLand computes `delta = v_impact² × 0.0001` (`fgame/bg_pmove.cpp:756-801`).
- A free fall of height h at g = 800 gives `delta = 0.16·h`.
- Standing water scales delta by ×0.25 (waterlevel 2) or ×0.5 (waterlevel 1).
- `SURF_NODAMAGE` suppresses the damage.

**Damage per band** (`fgame/player.cpp:6140-6173`):

| delta | Free-fall height at g=800 | Event | Damage (AA) |
|---|---|---|---|
| ≤ 20 | ≤ 125 u | none | 0 |
| > 20 | > 125 u | EV_FALL_SHORT | 5 |
| > 40 | > 250 u | EV_FALL_MEDIUM | 10 |
| > 80 | > 500 u | EV_FALL_FAR | 20 |
| > 100 | > 625 u | EV_FALL_FATAL | max_health + 1 |

- Falling damage is skipped in MP when dmflag `DF_NO_FALLING` is set (`fgame/player.cpp:6171`).
- A jump adds up to 56 u of fall to the drop.
- Retail AA also marks landings as medium when z-velocity ≤ −180 and hard when < −400 (animation only; `fgame/player.cpp:3911-3912`).

### 1.3 Ladders

Ladders are the **`func_ladder`** brush entity. `surfaceparm ladder` is not what makes a ladder.

**What the entity does**
- It sets `CONTENTS_LADDER` (2), `SOLID_BSP`, and never networks to clients (`fgame/misc.cpp:2824-2865`).
- Its `angle` key sets the facing: `m_vFacingDir` is the direction the climber faces, into the wall (`fgame/misc.cpp:2867-2873`).

**How a player gets on** (`Pak0.pk3:global/mike_torso.st:67-74`)
- The player either presses **+use** while looking at it (trace from the eye, up to 128 u, `MASK_LADDER`), or walks forward into it while looking up/down more than 35°.
- `CanUseLadder` then applies these checks:
  - The horizontal distance from the ladder **`origin`** must be ≤ 52 u.
  - The player's facing must be within about ±81° of the ladder facing (dot ≥ −0.15).
  - The player must stand on the non-wall side.
  - A box trace at `origin − facing·29`, `absmin.z + 16` must be clear (`fgame/misc.cpp:2875-2946`).
- Getting on at the top needs the player's head above `absmax.z` and a clear box at `origin + facing·26`, `absmax.z + 16`.

**While climbing**
- The player is placed at `origin − facing·16`, with z snapped to 16-u steps (`(z+8) & ~15`) (`fgame/misc.cpp:2948-3018`).
- Consequence: the ladder entity's **origin must sit on the climbable face, centred horizontally**.
- In retail maps this is done with a `common/origin` brush on the wall face; the rest of the brush is `common/trigger` (`MOHTools/maps/MP/mohdm2.map`, first func_ladder).
- Retail ladder brushes are about 28–64 u wide, 2–60 u deep, with `angle` 0/90/180/270 (measured: 38 func_ladder in Pak5 BSPs).

**`surfaceparm ladder`**
- It sets `SURF_LADDER` 0x8 (`renderergl1/tr_shader.c:2156`).
- It is only read by the dead `Player::StartClimbLadder` (`fgame/player.cpp:5130-5144`, never called) and by the cgame surface-info printout (`cgame/cg_consolecmds.c:218`).

### 1.4 Collision masks that matter

- **Players** (MASK_PLAYERSOLID) collide with SOLID, PLAYERCLIP, FENCE, TRIGGER, BODY and BBOX. They do **not** collide with monsterclip or weaponclip (`fgame/bg_public.h:621-623`).
- **Bullets** (MASK_SHOT) hit SOLID, FENCE, WEAPONCLIP, BODY and TRIGGER, but not PLAYERCLIP (`fgame/bg_public.h:636-638`).
- **Static models have no engine collision.** The collision loader never reads the static-model lumps (`qcommon/cm_load.c:899-1000`). Retail maps block them with `*clip` brushes such as `common/metalclip` and `woodclip`, which carry a material flag (measured: mohdm1 shader lump).

### 1.5 Practical mapping numbers (derived from the above)

| Item | Number | Why |
|---|---|---|
| Absolute minimum corridor width | 31 u; use **≥ 48–64** | box is 30 wide |
| Door opening a standing player fits through | ≥ 32 w × **≥ 96 h** | box 30×94 plus epsilon. Retail doors are about 56–72 wide × 124–144 tall (measured: mohdm1 func_rotatingdoor submodels) |
| Crouch-only gap (clear height) | **56–92 u** (e.g. 64 or 72) | crouched top is 54, standing top is 94 |
| Max stair riser | **18 u**. Use 8–16 for smooth stairs; ≤ 9 under low ceilings | STEPSIZE |
| Max climbable ramp | < 45° (normal.z ≥ 0.7) | MIN_WALK_NORMAL |
| Jump-up ledge | 56 u reliably. About 56 + 18 = 74 u may work via air stepping after the apex (**UNVERIFIED**) | jump 56 |
| Safe drop | ≤ 125 u with no damage; ≤ 250 u costs 5 HP | fall table |
| Eye level for sightlines | 82 standing, 48 crouched | viewheights |

---

## 2. Automated camera control (screenshots)

### 2.1 Command routing and cheat gating

**How the console resolves a command.** It tries, in order: engine command → alias → cvar → cgame command → server game command → otherwise it forwards the text to the server as a client command (`qcommon/cmd.c:1003-1050`).
- `give`, `noclip`, `notarget`, `join_team`, `spectator`, … are registered with a NULL handler just so they get forwarded (`fgame/gamecmds.cpp:90-114`).
- Player console commands are Events, checked by `Entity::CheckEventFlags` (`fgame/entity.cpp:5097-5144`):
  - The event must carry `EV_CONSOLE` or `EV_CHEAT`.
  - For `EV_CHEAT`: if cvar **`thereisnomonkey`** (default 0, CVAR_TEMP) is 0, the game **forces `cheats` to 0** and then refuses the command.
  - **Cheat commands therefore need both `set thereisnomonkey 1` and `cheats` = 1.**
- The cheat cvar is named **`cheats`** (the fgame pointer is called `sv_cheats`).
  - It is CVAR_LATCH (`fgame/gamecvars.cpp:388`, `qcommon/cvar.c:1752`, `server/sv_init.c:1078`).
  - A real cvar named `sv_cheats` exists only because `CL_Disconnect` writes it (`client/cl_main.cpp:1017`).
- **`map` vs `devmap`** (`server/sv_ccmds.c:224-240`). This logic only applies when `developer` is 0:
  - If `svs.iNumClients == 1`, cheats is set to 1.
  - Otherwise, a command containing "devmap" sets cheats to 1, and plain `map` sets it to 0.
  - With `developer` ≠ 0 the cvar is left alone.
  - **Use `devmap <name>`**, e.g. `devmap dm/mohdm1`.
- `map` fails if `maps/<name>.bsp` is missing, or if a `dm/` map is loaded while `g_gametype 4` is set (`server/sv_ccmds.c:199-222`).
- CVAR_CHEAT client cvars can only be set while cheats ≠ 0 (`qcommon/cvar.c:653-657`).

### 2.2 Teleport and view commands (Player events)

| Command | Gate | Syntax / effect | Source |
|---|---|---|---|
| `tele` | EV_CHEAT\|EV_CONSOLE | `tele X Y Z` or `tele "X Y Z"`. Position only, velocity is not cleared | `fgame/player.cpp:1087-1094`, `fgame/player_util.cpp:639-646` |
| `face` | EV_CHEAT\|EV_CONSOLE | `face PITCH YAW ROLL` or `face "p y r"`. Sets delta_angles so the view really turns | `fgame/player.cpp:1096-1103`, `:7988-8007` |
| `coord` | EV_CONSOLE (no cheat) | prints location and angles to the server console | `fgame/player.cpp:1105-1112` |
| `viewpos` | cgame cmd | prints `(x y z) : yaw` of the current view | `cgame/cg_consolecmds.c:63-72` |
| `noclip` | EV_CHEAT\|EV_CONSOLE | toggle; refused in a vehicle or turret | `fgame/player.cpp:220-227`, `:6018-6045` |
| `notarget` | EV_CHEAT | toggle FL_NOTARGET; bots ignore you | `fgame/player.cpp:211-218` |
| `dog [0\|1]` | EV_CHEAT\|EV_CONSOLE | **god mode**. `god` is registered but no event handles it, so it does nothing | `fgame/player.cpp:193-200`, `fgame/gamecmds.cpp:94` |
| `give <item>` / `wuss` / `fullheal` | EV_CHEAT | items, all weapons, heal | `fgame/player.cpp:292-299,167-174,202-209` |
| `fov [f]` | EV_CONSOLE | clamped to 1..160, but it only sets the server-side player fov: **cgame ignores it** unless the player is zoomed or in a script camera, and draws with the client cvar `cg_fov` instead, clamped to 65..120 every frame (OPM addition). Set `cg_fov` for screenshots | `fgame/player.cpp:6060-6085`, `cgame/cg_predict.c:342-362`, `cgame/cg_view.c:870-874` |

- `setviewpos`, `setangles`, `thirdperson` and `toggleviewmode` **do not exist**.
- `tele` and `face` round-trip through the server, which runs at `sv_fps` 20 (`fgame/gamecvars.cpp:389`). Wait before capturing.

### 2.3 Spectator and third person

**`spectator`** (EV_CONSOLE)
- It sets noclip movement, hides the model, and **auto-follows a random player** (`fgame/player.cpp:823-830`, `:9302-9342`).
- In AA protocol, `+use` cycles the followed player and any up/down move (`+moveup`) returns to free-roam (`fgame/player.cpp:4818-4848`).
- Follow view is third-person unless `g_spectatefollow_firstperson 1` (`fgame/gamecvars.cpp:700`).
- The spectator prompt "Press Use to follow a player" is always drawn (`cgame/cg_drawtools.cpp:1284-1345`). Only `saveshot` hides it.

**`join_team allies|axis`** (`fgame/player.cpp:758-765`). Any other argument joins axis (`fgame/player.cpp:9554-9559`).

**Third person**
- Controlled by `cg_3rd_person 1`, which is **CVAR_CHEAT** (`cgame/cg_main.c:147`).
- Camera placement: `cg_cameradist` 120, `cg_cameraheight` 18 (`cgame/cg_main.c:149-152`).

### 2.4 Hiding the HUD, gun and console

**`ui_hud 0`**
- This is a *command*, not a cvar (`client/cl_ui.cpp:4679-4733`, `:5347`).
- It hides the HUD and also sets `cg_hud`.
- CG_Init runs `ui_hud 1` on every map load (`cgame/cg_main.c:770`), so **issue it after the map loads**.

Other cvars:
- `cg_hud` (default 0) gates cgame icons, the crosshair and similar elements (`cgame/cg_main.c:170`).
- `ui_crosshair 0` (`client/cl_ui.cpp:5253`).
- `cg_drawviewmodel 0|1|2`: none / gun only / full (default 2) (`cgame/cg_main.c:148`).
- `ui_compass 0`, `ui_gmbox 0` (game-message box), `ui_minicon 0`, `ui_drawcoords 0` (`client/cl_ui.cpp:5249-5263`).
- `fps 0` (`qcommon/common.c:1911`), `cg_lagometer 0`, `cg_drawsvlag 0` (`cgame/cg_main.c:144,172`).
- `cg_draw2D`, `cg_drawgun`, `r_drawviewmodel`, `cg_thirdperson` and `con_notifytime` **do not exist**.

**`saveshot [args]`**
- It sets `cls.no_menus`, draws a frame, then runs `screenshot args` (`client/cl_main.cpp:4610-4633`).
- With `no_menus`, the UI draws only the 3D view, plus the HUD if `ui_hud` is on. CG_Draw2D, the crosshair, spectator text, centerprint and fps are skipped (`client/cl_ui.cpp:1833-1861`, `client/cl_uiview3d.cpp:574-604`).
- The screenshot render command is queued after the clean draw, before the next BeginFrame. That this yields a clean image is my reading of the code, **UNVERIFIED at runtime**.

### 2.5 Screenshot file naming (`renderergl1/tr_init.c`)

**`screenshot`**

| Form | Output |
|---|---|
| no argument | `screenshots/shotNNNN.tga` (first free of 0000–9999) (`:634-653`) |
| `<name>` | `screenshots/<name>.tga`. If the name contains `/` it is used verbatim (`:843-846`) |
| `silent` | numbered, no message |
| `levelshot` | `levelshots/<map>.tga`, 128×128 |

- A non-silent `screenshot` does `centerprint "Wrote …"` (`:886-887`), and that text shows up in later frames.

**`screenshotJPEG`**
- Takes `[name]` and writes `screenshots/<name>.jpg` (`:899-936`).
- It only prints to the console.
- Quality is `r_screenshotJpegQuality` 90 (`:1588`).

Files go under the home path. On macOS that is `~/Library/Application Support/openmohaa/<game dir, main>/` (`sys/sys_unix.c:124-139`). The exact subdirectory is **UNVERIFIED**.

### 2.6 `wait` in command buffers (`qcommon/cmd.c:62-70`, `:196-205`)

- A bare `wait` stops execution until the next `Cbuf_Execute` pass. With two passes per frame, a bare `wait` is half a frame (measured: 600 bare waits ≈ 5 s at 60 fps).
- **`wait N` counts down N *milliseconds*** (it subtracts the frame msec), not frames. `wait 0` does nothing.
- `Cbuf_Execute` runs twice per `Com_Frame`: once with 0 before SV_Frame, and once with msec after it (`qcommon/common.c:2357`, `:2417`).
- `mohkit.game.run` uses bare-`wait` runs until the map is loaded, then `finishloadingscreen`, then `tele`/`face`/`fov`, `wait 700`, the same again, `wait 300`, `saveshot` (verified on stock mohdm1 and on mohkit maps).

### 2.7 Suggested script (not run)

```
set developer 0; set g_gametype 1; set thereisnomonkey 1; devmap dm/mymap
// after load:
ui_hud 0; cg_drawviewmodel 0; ui_crosshair 0; ui_gmbox 0; ui_compass 0
join_team allies; wait 1000; noclip; notarget; dog 1        // or: spectator; +moveup; wait; -moveup
tele 0 0 256; face 20 90 0; wait 1000; saveshot cam01        // or screenshotJPEG cam01
```

---

## 3. Bots

**Cvars and commands**
- `sv_maxbots` (default 0, **CVAR_LATCH**): reserves extra client slots at init. **It must be > 0 before the map loads** (`fgame/gamecvars.cpp:683`, `fgame/g_main.cpp:295-299`).
- `sv_numbots` (0): target bot count. `sv_minPlayers` (0): tops up with bots until this many non-spectator players are present. `sv_sharedbots` (0, latch): lets bots use normal client slots (`fgame/gamecvars.cpp:684-686`, `fgame/g_bot.cpp:215-236`, `:756-782`).
- Console commands (`fgame/gamecmds.cpp:72-77`, `:632-700`):
  - `addbot <n>`: sets numbots = min(n + numbots, sv_maxbots), so it **does nothing if sv_maxbots is 0**.
  - `addbotnamed <name>` and `removebot <n>`.
- `G_SpawnBots` reconciles the bot count every frame. It never spawns bots in single-player (`fgame/g_bot.cpp:956-990`).
- Bot names come from `g_bot<N>_name`, otherwise `bot<id>` (`fgame/g_bot.cpp:461-469`).

**`g_gametype`** (default 0, latched serverinfo; `fgame/gamecvars.cpp:485`, enum at `fgame/bg_public.h:126-137`)
- Values: 0 single-player, **1 FFA**, **2 TDM**, **3 round-based team**, **4 objective**, 5 GT_TOW, 6 GT_LIBERATION. 5 and 6 are Spearhead/Breakthrough-era modes; whether they work on AA maps is **UNVERIFIED**.
- The retail AA UI offers 1–4 (`Pak0.pk3:ui/multiplayerstart_*.urc`).

**Spawn point selection** (`fgame/dm_manager.cpp:1088-1113`)
- FFA and spectators use `info_player_deathmatch`.
- Team modes (gametype ≥ 2) use `info_player_allied` / `info_player_axis`.

**Navigation: Recast/Detour, OpenMoHAA-only**
- The navmesh is built in memory at every map load. It is **not cached**, and is built only when `g_navigation_legacy 0`, `g_gametype ≠ 0` and `sv_maxbots > 0` (`fgame/level.cpp:1540-1544`, `fgame/navigation_recast_load.cpp:728-731`).
- **Geometry used**: world brush sides of SOLID/PLAYERCLIP/FENCE brushes, excluding sky sides; patch meshes; LUMP_TERRAIN (`fgame/navigation_bsp.cpp:204-216`, `:453`, `:580`, `:1042-1082`).
- **Geometry not used**: static models, brush entities such as doors, and trisoups (`fgame/navigation_bsp.cpp:749-754`, `:1010`, `fgame/navigation_recast_load.cpp:769-772`).
  - So a static model that you block with clip brushes is handled correctly, because the clip brushes are in the navmesh. A static model without clip is walked *through* by bots (players too, see 1.4).
- **Agent parameters** (`fgame/navigation_recast_config.h:36-42`):
  - height = 94 (standing), so crouch-only passages are not in the navmesh.
  - maxClimb = 18, maxSlope 45.573°, radius 1.0, cell size 10.25, cell height 1.0.
  - Off-mesh links cover func_ladder, jumps of 56, and falls (`fgame/navigation_recast_config_ext.h`).
  - The mesh is a single tile covering ±8192.
- **Map requirements**: spawn points plus reachable walkable world brushes. **No `info_pathnode`s are needed**.
  - `info_pathnode` is still used by legacy AI and by `g_navigation_legacy 1`, cached as `maps/<map>.pth` (`fgame/level.cpp:1588`, `fgame/navigate.cpp:1289`).

---

## 4. Map loading and scripts

### 4.1 What is loaded for `map dm/NAME` (or `obj/NAME`)

The map name includes its subdirectory. `map dm/NAME$spot` picks the `info_player_start` whose targetname is `spot` (`fgame/level.cpp:1561-1570`).

| Step | File / action | Source |
|---|---|---|
| BSP | `maps/<map>.bsp`. `maps/<map>_sml.bsp` is used instead when it exists and `r_largemap` is 0 | `fgame/g_main.cpp:330-340` |
| Paths | script `maps/<map>.scr`, precache `maps/<map>_precache.scr`, AI path cache `maps/<map>.pth` | `fgame/level.cpp:1582-1588` |
| Precache | runs `<map>_precache.scr` if present, then compiles every `global/*.scr`. In MP, OpenMoHAA also auto-caches all `models/player/*.tik` except `*_fps` | `fgame/level.cpp:1626-1683` |
| Uncached model at runtime | prints "Add the following line to the *_precache.scr map script: cache X" | `tiki/tiki_cache.cpp:124-125` |
| `maps/<map>.snd` | run by SoundMan if present; none exist in retail | `fgame/worldspawn.cpp:614`, `fgame/soundman.cpp:1482-1505` |
| Entities | worldspawn first, then everything else. PreSpawnSentient then **runs `maps/<map>.scr` from the top of the file** (`main:` is only a convention) | `fgame/level.cpp:1123-1260`, `:1483-1499`, `script/scriptcompiler.cpp:1578` |
| Script events | `prespawn` fires after spawn points are collected (`dmManager.InitGame`); `spawn` fires in `ServerSpawned` | `fgame/level.cpp:1228-1244`, `:1527-1538` |
| Round events | `level waittill roundstart` exists only for gametype 3–6. `allieswin`, `axiswin` and `draw` exist for gametype > 1. Guard with `if(level.roundbased)` as retail does | `fgame/level.cpp:984-990` |

**Client side**
- **Loading screen.** The loader shows the UI menu whose *name* equals the map name, e.g. `menu "dm/mohdm1" …` in `Pak0.pk3:ui/loading_mohdm1.urc:1`. If none exists it falls back to `loading_default` (`client/cl_ui.cpp:5864-5871`). All `ui/*.urc` files are loaded at init, so the file name doesn't matter (`client/cl_ui.cpp:5432-5439`).
  - Retail loading pictures are shaders such as `mohdm1` → `textures/mohmenu/dmloading/mohdm1.tga` (`Pak0.pk3:scripts/mohmenu.shader:2097`).
- **`maps/<map>.min`** holds loading-bar progress data; the format starts with version `3` (`client/cl_ui.cpp:5496`, `:5883-5886`).
  - If it is missing, OpenMoHAA writes one after the load (`:5972-6013`).
  - Per an OpenMoHAA comment (`:5976-5983`), the original game can crash on custom maps without one. **Ship a `.min`** (for example, load the map once in OpenMoHAA and copy the file it writes).
- **`levelshots/<map>.tga`** is only written by `screenshot levelshot`. It is not used by the loader.
- **Scoreboard.** Scripts set the cvars `g_scoreboardpic`, `g_obj_alliedtext1..5` and `g_obj_axistext1..5`. They are SERVERINFO and reset on each map (`fgame/gamecvars.cpp:633-639`, `:666-671`).
- **Sound aliases.** An `aliascache` line with `maps "dm moh obj train"` is registered only if one of those tokens is a case-insensitive **prefix of `mapname`** (`fgame/scriptmaster.cpp:417-441`; example: `Pak0.pk3:ubersound/ubersound.scr:1117`).
  - **Put MP maps in `maps/dm/` or `maps/obj/`**, otherwise the DM sound aliases do not load.

### 4.2 Minimal DM script (condensed from `Pak5.pk3:maps/DM/mohdm1.scr`)

```
main:
    setcvar "g_obj_alliedtext1" "My Map"      // alliedtext1-3 / axistext1-3
    setcvar "g_scoreboardpic" "mymap"
    if(level.roundbased) thread roundbasedthread
    level waittill prespawn
    exec global/DMprecache.scr
    level.script = maps/dm/mymap.scr
    exec global/ambient.scr mymap              // music/mymap.mus + interior/exterior music triggers
    // $world farplane 5000 ; $world farplane_color (.333 .333 .329)
    level waittill spawn
end
roundbasedthread:
    level waittill prespawn
    level waittill spawn
    level.dmrespawning = 0 ; level.dmroundlimit = 5 ; level.clockside = kills   // axis|allies|kills|draw
    level waittill roundstart
end
```

- `maps/dm/<map>_precache.scr` contains just `exec global/DMprecache.scr` (`Pak5.pk3:maps/DM/mohdm1_precache.scr:1`).
- Objective variant (`Pak5.pk3:maps/obj/obj_team1.scr:20-93`):
  - sets `level.defusing_team`, `level.planting_team`, `level.targets_to_destroy`, `level.dmrespawning`, `level.dmroundlimit` and `level.clockside`;
  - waits `level waittill roundstart`;
  - runs `$bomb thread global/obj_dm.scr::bomb_thinker`;
  - calls `teamwin allies` once `level.targets_destroyed >= level.targets_to_destroy`.
  - The bomb is a `script_model` with `target` (the object to destroy) and `$trigger_name` (targetname of a trigger_use). Optional keys: `#exploder_set`, `$explosion_fx`, `$explosion_sound`, `$killarea` (`pak7.pk3:global/obj_dm.scr:11-41`).
- `global/DMprecache.scr` is nothing but `cache <tik>` lines: all weapons, flak88/mg42 turrets, every `models/player/*.tik` and its `_fps` variant, and vehicles (`Pak0.pk3:global/DMprecache.scr:1-77`).
- `global/ambient.scr <name>`:
  - It waits for `spawn`, then runs `soundtrack music/<name>.mus` and `forcemusic normal normal`.
  - It handles `$interior`/`$exterior` music triggers with `#set` (`Pak0.pk3:global/ambient.scr:1-98`).
  - It then runs `global/ambience.scr`, whose ambient loops are **hard-coded per retail map**. Custom maps add their own:
    ```
    local.s = spawn script_model model "fx/dummy.tik"
    local.s.origin = ( x y z )
    local.s loopsound <alias>
    local.s notsolid
    ```
    (pattern from `Pak0.pk3:global/ambience.scr:195-200`).

### 4.3 Spawn points

| Classname | Used for | Source |
|---|---|---|
| `info_player_deathmatch` | FFA (added to every team list when g_gametype is 1) and spectators. **Not used by team modes** | `fgame/dm_manager.cpp:1092-1100` |
| `info_player_allied` / `info_player_axis` | only when g_gametype ≥ 2 (TDM, round, objective) | `:1101-1110` |
| `info_player_intermission` | Camera for the end-of-match view; `target` aims it. If missing, the screen fades out. The code also appends it to the free-for-all spawn list (runtime effect **UNVERIFIED**) | `:1111-1113`, `fgame/g_main.cpp:1758-1768`, `:1836-1846` |
| `info_player_start` | not in the DM lists. It is the fallback, looked up by targetname (the `$spot` name or the default `playerstart`) | `fgame/g_client.cpp:610-630`, `fgame/playerstart.cpp:118-123` |

- **Keys.** `angle` sets yaw only (`fgame/playerstart.cpp:93-99`). The editor box is (−16 −16 0)–(16 16 96) (`entdefs.pk3:code/PlayerStart.cpp`).
- **Scripting.** Script events `enablespawn`, `disablespawn`, `deletespawn` and `keepspawn` are available (`fgame/playerstart.cpp:40-74`). QUAKED lists `thread` and `arena`, but no handler exists for either.
- **Choosing a spot.**
  - FFA picks the spot farthest from enemies. Team modes prefer far from enemies and near friends. Objective mode picks at random (`fgame/dm_manager.cpp:130-191`).
  - Spots that would telefrag are skipped. If every spot is blocked, the code tries ±48 u on x/y and +32 u on z around each spot (`fgame/dm_manager.cpp:398-481`).
  - The player is placed at `origin + (0,0,1)`, and `KillBox` telefrags anyone there in MP (`fgame/player.cpp:2672-2683`).
- **No spot in the team list.**
  1. Try `info_player_start` by targetname.
  2. OpenMoHAA only: fall back to any PlayerStart.
  3. Otherwise **ERR_DROP "No player spawn position named '…'. Can't spawn player."** (`fgame/g_client.cpp:632-658`).
- **Recommended set:**
  - **DM/TDM**: ≥ 16 `info_player_deathmatch`, ≥ 16 each of `info_player_allied`/`info_player_axis`, 1 `info_player_start`, 1 `info_player_intermission` (retail mohdm1 has 22 allied, 20 axis, 18 dm, 1 start, 1 intermission).
  - **OBJ**: allied, axis and start (obj_team1 has 18/18/1 and no dm).

### 4.4 Worldspawn keys (game, renderer and cgame)

Game side: `World` class (`fgame/worldspawn.cpp:491-543`), defaults in its constructor (`:549-626`). Its targetname is always `world`, so scripts can write `$world farplane 5000` (`:620`).

| Key | Effect / default | Source |
|---|---|---|
| `message` | level title (CS_MESSAGE) | `fgame/worldspawn.cpp:969-976` |
| `soundtrack` | `.mus` file | `:703-709` |
| `gravity` | sets `sv_gravity`; default **800** | `:570`, `:711-714` |
| `nextmap` | next map | `:964-967` |
| `farplane` | fog and far-clip distance; default 0 = off | `:721-731`, `:573` |
| `farplane_color` | "r g b" 0–1; default 0 0 0 | `:755-765` |
| `farplane_cull` | 0 none, **1 standard (default)**, 2 portal-sky only | `:767-775`, `renderergl1/tr_local.h:728-732` |
| `farplane_bias`, `skybox_farplane`, `skybox_speed`, `render_terrain`, `farclipoverride`, `farplaneclipcolor` | **not sent to AA-protocol clients**. For protocol 8 the fog configstring is only `cull dist r g b` | `:651-681` |
| `animated_farplane*` | varies farplane with player z; single-player only | `:788-856` |
| `skyalpha` | default 1 | `:597`, `:952-956` |
| `skyportal` | default 1. The portal sky needs a `script_skyorigin` entity | `:598`, `fgame/scriptslave.cpp:2237-2250` |
| `northyaw`, `ai_visiondistance` (2048), `watercolor`/`wateralpha`, `lavacolor`/`lavaalpha`, `numarenas` | misc | `:978-1011` |
| spawnflag 1 `CINEMATIC` | sets `sv_cinematic` | `:603-609` |
| `script` | **not a script file**: a list of inline commands, the generic mechanism available to any entity | `fgame/g_spawn.cpp:493-517` |
| `ambientlight`, `ambient`, `suncolor`, `sunlight`, `sundirection`, `sundiffuse`, `sundiffusecolor`, `lightmapdensity`, `sunflarename`, `sunflaredirection`, `overbright`, `vis_derived` | the game declares these with **NULL handlers, i.e. ignores them**. They are compiler keys (§6.5) | `fgame/worldspawn.cpp:523-535` |
| renderer entity lighting | reads from worldspawn only: `suncolor` **or** `sunlight` ("r g b" × overbrightMult; default 70 70 70); `sundirection` (angles); `sunflaredirection`; `sunflarename` (default `sun` when a sun exists); `ambientlight` (default 0 0 0); `overbright` (**any** value enables entity overbright because of the condition at `:1275`) | `renderergl1/tr_sphere_shade.cpp:1196-1287` |
| `map_time` | written by Q3map; ignored | `Q3map.exe (strings)` |
| `sunflare` "x y z" | used in retail mohdm1/mohdm3; no parser found (**UNVERIFIED**) | — |

---

## 5. Entities for DM/TDM/OBJ maps

### 5.1 Rules that apply to every entity (`fgame/g_spawn.cpp`, `fgame/level.cpp`)

- **Keys are events.**
  - Every key/value is posted as the event of that name (`fgame/g_spawn.cpp:518-543`).
  - `#key` creates a numeric script variable (`#set 1` becomes `self.set`) and `$key` a string one (`$type wood` becomes `self.type`) (`:416-491`).
  - `script` is a list of inline commands (`:493-517`).
- **Spawnflags common to all entities** (`fgame/g_spawn.h:32-39`, `fgame/level.cpp:1050-1062`):
  - 256/512/1024: not easy/medium/hard.
  - **2048 NOT_DEATHMATCH**: removed in every MP gametype.
  - 4096 DETAIL: removed when the cvar `detail` is 0.
  - 8192 DEVELOPMENT.
- **Unknown classnames** use the `classname` from the model TIKI's `init { server { classname … } }` (e.g. `interactobject_*`, `animate_*`). Otherwise they become a plain animated `Object`. The key `make_static 1` suppresses spawning (`fgame/g_spawn.cpp:236-301`).
- **Angle keys.** `angle −1` means up and `−2` means down (`fgame/g_utils.cpp:866-876`); `angles` takes "pitch yaw roll".
- **Brush entities.** Use an `origin` brush wherever rotation or placement depends on `origin`: doors and ladders. Otherwise Q3map sets origin to the centre of the brush bounds (§7.3).

### 5.2 Models and helpers

| Classname | Behaviour | Keys / spawnflags | Source |
|---|---|---|---|
| `static_<anything>` | **compile-time only.** Q3map moves it to LUMP_STATICMODELDEF, removes it from the entity lump, and MOHlight vertex-lights it. It is drawn by the renderer only: **no collision, no script access**. Block it with `*clip` brushes. Radiant takes the name from the `/*QUAKED static_… */` comment in each `models/static/*.tik` | `model` (e.g. `static//nazi_crate.tik`, stored verbatim; `models/` is prepended at load), `origin`, `angle` or `angles`, `scale` (not `modelscale`), `spawnflags` (retail 0/1, meaning **UNVERIFIED**). `testanim` is editor-only | `Q3map.exe (strings)`, `renderergl1/tr_staticmodels.cpp:82-86`, `MOHTools/maps/MP/*.map` (2657 uses) |
| `misc_model` | removed by the game at spawn, and Q3map does not handle it. **Don't use** | `model` | `fgame/misc.cpp:72-87` |
| `script_model` | animated TIKI entity (ET_MODELANIM), scriptable; a `.tik` model makes it SOLID_BBOX | `model`, `targetname`, `angle(s)`, `scale`; sf 1 NOT_SOLID, 2 ALWAYS_DRAW | `fgame/scriptslave.cpp:751-767`, `:902-904`, `:1959-2013` |
| `script_object` | scriptable brush model (MOVETYPE_PUSH; `speed` 100, `dmg` 2) | sf 1 NOT_SOLID | `fgame/scriptslave.cpp:633`, `:735-749` |
| `script_origin` | invisible, non-solid point for bind, sound or move | `targetname` | `fgame/scriptslave.cpp:2155-2201` |
| `script_skyorigin` | camera origin of the portal sky | — | `fgame/scriptslave.cpp:2237-2250` |
| `info_null` | removed at spawn; compile-time target such as a spotlight target | `targetname` | `fgame/misc.cpp:94-101` |
| `info_notnull` | persists; script-visible point | `targetname` | `fgame/misc.cpp:110` |
| `func_group`, `detail`, `vis_leafgroup`, `func_remove` | editor grouping, manual vis, and removal. Stripped by Q3map (func_remove is removed by the game) | — | `entdefs.pk3:code/misc.cpp`, `fgame/misc.cpp:64-71` |
| `light` | never spawned by the game, but kept in the lump for MOHlight (§6.6) | — | `fgame/g_spawn.cpp:224-233`, `fgame/light.cpp:147-150` |

**Static model limit: 4,095 per map.** Per-frame triangle counts live in
`staticModelNumIndexes[4095]` (`renderergl1/tr_model.cpp:33`), written for every drawn
static model by its number (`:1560`, `:1582`), and the draw sort key keeps that number in
12 bits (`(sort >> QSORT_ENTITYNUM_SHIFT) & 4095`, `renderergl1/tr_main.c:1241`; static
flag bit 20, shader from bit 21, `tr_local.h:1212-1216`). Larger counts corrupt memory
and draw the extra models with the wrong transform (de_inferno with 6,326: crash in
`R_PrintInfoWorldtris` during a bot match). Static models are frustum-culled only (the
leaf `visCount` test is commented out, `tr_staticmodels.cpp`) and at most 8,192 of their
surfaces are drawn per frame (`MAX_STATIC_MODELS_SURFS`, same file).

**Static model LOD (progressive meshes).** Every frame each static model in the frustum
gets a metric `m = R * (100 / fovX) / distance` (`ProjectRadius`, `renderergl1/tr_model.cpp:1825`;
`R` is the SKC frame radius times the TIKI scale, `tr_staticmodels.cpp:355-357`).
`GetLodCutoff` (`tr_model.cpp:472`) scales it, `m' = (m - maxMetric) * r_lodscale +
maxMetric`, caps it at `maxMetric + (minMetric - maxMetric) * r_lodcap` (retail high preset:
both 0.55, so the high preset never draws a LOD'd model at full detail), and reads a cutoff
off the SKD's LOD curve. `RB_StaticMesh` (`tr_model.cpp:1494-1590`) then draws only the
vertices whose `collapseIndex >= cutoff` (a prefix: the file sorts vertices by
non-increasing `collapseIndex`), maps each dropped vertex through `collapse[]` (always a
lower index) to a drawn one (`:1567`), and draws triangles in file order until the first
degenerate one, so triangles are sorted by the step at which they vanish. A surface with
`collapseIndex[2] < cutoff` is not drawn at all (`:1512`). The curve comes from
`<skd path up to the first "skd">lod` (`GetLODFile`, `tiki/tiki_skel.cpp:751`, `:778`): a
96-byte `lodControl_t` (minMetric, maxMetric, five `(pos, val)` points, four constants that
`TIKI_CalcLodConsts` recomputes, `:838`), linear in `m'` with `pos` 0 at minMetric and 1 at
maxMetric. Without a surface whose first and last `collapseIndex` differ there is no LOD
(`:766`) and the whole mesh is always drawn. Retail ships 275 `models/static/*.lod`
(Pak0.pk3; `alarmbell.lod`: 0.5 0.012, curve (0,0) (0.5,15) (0.8,28.8) (0.95,45) (1,58),
`collapseIndex` 58 for the base vertices down to 1). Converted props now carry LOD from
`mohkit.lod` (quadric half-edge collapses, curve for ~1 px error at 1920 wide); before it
de_cache drew 0.3-0.9 M prop vertices per frame and props were 70-85% of the frame time
(`mohkit test --perf --toggle r_drawstaticmodels=0`).

**`r_primitives` decides how every batch is drawn** (`R_DrawElements`,
`renderergl1/tr_shade.c:163-197`): 2 is one `glDrawElements` per batch; 1 (and 0 without
`GL_EXT_compiled_vertex_array`) walks the indexes into triangle strips and sends each strip
as `glBegin`/`glArrayElement`/`glEnd` (`R_DrawStripElements`). Apple's OpenGL 2.1-on-Metal
has no compiled vertex arrays ("...GL_EXT_compiled_vertex_array not found" in the log), so a
fresh macOS config (0) takes the strip path, and `sample` shows the frame inside
`glEnd_Exec` -> Metal `drawPrimitives`: one GPU draw per strip. de_inferno (converted) ran
at 6 fps mean with 0 and 84 with 2, same image, same resolution (resolution made no
difference: it is draw-call bound). Players should have `seta r_primitives "2"` (the
owner's `omconfig.cfg` does); the test harness sets it (`game.QUALITY_CVARS`).

**At most 2,048 shaders per level in practice.** `MAX_SHADERS` is 16,384
(`renderergl1/tr_local.h:70`), but the draw-surface sort key is a 32-bit `unsigned` with the
sorted shader index in bits 21-31 (`QSORT_SHADERNUM_SHIFT` 21, `tr_local.h:1212`;
`R_DecomposeSort` reads `(sort >> 21) & (MAX_SHADERS - 1)`), so sorted index 2,048 and up
wraps onto low indexes. Loaded at spawn (`shaderlist`): converted de_cache 1,168, de_nuke 894,
de_inferno 698. Static model surfaces whose single-pass shader has `alphaGen tikiDistFade
<near> <range>` are skipped beyond near + range from the model origin
(`tr_staticmodels.cpp`, `tr_shade.c` AGEN_TIKI_DIST_FADE); mohkit uses LOD vanish steps instead
(no extra shaders).

**How a runtime model is lit.** cgame sets `lightingOrigin = origin + centre of the
box packed into entityState.solid` (`cgame/cg_modelanim.c:1064-1067`). A NOT_SOLID
entity packs `solid = 0` (`server/sv_world.c:230-257`), which unpacks to the box
(0,0,-16)..(0,0,0) (`qcommon/q_math.c:1652`, `zd -= BBOX_MAX_BOTTOM_Z`), so it is lit
from **8 units below its origin**, with radius 8. With `r_fastentlight 0` (retail high)
the renderer then traces once from that point to the sun (`CONTENTS_SOLID |
CONTENTS_FENCE`, sun only if the trace hits a `surfaceparm sky` face), adds the
sphere lights of the leaves around it, and samples the light grid there for ambient
(`renderergl1/tr_sphere_shade.cpp:587-700`, `:790-812`). With `r_fastentlight 1`
(retail low/medium, and a fresh OpenMoHAA config) or a shader that asks for the grid,
it uses the light grid alone (`renderergl1/tr_backend.c:830-836`).

One trace decides the whole model, so its start point matters. A trace that starts
inside a brush is not stopped by that brush (`qcommon/cm_trace.c:654-661`), but it is
stopped by any other brush it enters: a car lit from inside its own multi-brush
collision hull got ambient light only (seen with a red test sun: cars blue = ambient,
rubble red = sun). The CS:GO converter puts the lighting point 8 units above the
mesh's top (`modelconv.LIGHT_ABOVE_TOP`). Patch collision is approximated to within
16 units of the curve (`qcommon/cm_patch.h:101`), so a point just above a bumpy
displacement floor can still be under its collision surface. A shader's `rgbGen
static` (vertex colours MOHlight bakes into static models) falls back to this
lighting on a runtime model (`renderergl1/tr_shade.c:846-856`), so one shader serves
both.

### 5.3 Doors (`fgame/doors.cpp`)

**Spawnflags:** 1 START_OPEN, 2 OPEN_DIRECTION, 4 DOOR_DONT_LINK, 8 NOT_PLAYERS, 16 NOT_MONSTERS, 32 TOGGLE, 64 AUTO_OPEN, 128 TARGETED (`:262-267`; `entdefs.pk3:code/doors.cpp`).

**Keys common to all doors** (`:42-86`, `:209-250`, `:343-347`, `:385-411`)
- `wait`: 3 (0 with TOGGLE; −1 = never return)
- `dmg`: 0
- `time`
- `health`: if set, the door must be shot open
- `targetname`: no touch field; opened by trigger or script
- `message`, `key`, `lock`/`unlock`
- `sound_open_start`, `sound_open_end`, `sound_close_start`, `sound_close_end`, `sound_locked`, `sound_message`
- **`doortype wood|metal`** (default wood): selects the `door_<t>_*` sound aliases and the travel time (wood 1.0 s, metal 1.5 s). Any other value is a ScriptError
- **`alwaysaway 1`**: the door opens away from the user

**Classes**
- **`func_rotatingdoor`** (`:1259`, `:1297`). Needs an **origin brush on the hinge**.
  - `openangle`: default 90 (`:1386`).
  - `angle`: points toward the middle of the door, away from the hinge.
  - Retail: 86 doors, typically `angle`, `alwaysaway 1`, `time 0.8`, `wait 1.0`, `doortype metal|wood` (`MOHTools/maps/MP/*.map`).
- **`func_door`** (`:1392`, `:1449`): sliding. `angle` = move direction, `lip` 8 (`:1512`), `speed` 100.
- **`script_door`** (`:1520`, `:1608`): scripted, via `initthread`/`openthread`/`closethread`.
- **Locked door (retail pattern).** Put a `trigger_use` with `targetname door_locked` and `$type wood|metal|…` in the doorway, then call `exec global/door_locked.scr::lock` before `spawn` (`Pak0.pk3:global/door_locked.scr:1-8`).

### 5.4 Triggers (`fgame/trigger.cpp`)

**Spawnflags:** 4 NOT_PLAYERS, 8 MONSTERS, 16 PROJECTILES, 128 DAMAGE (shoot to fire) (`:206-211`, `:285-317`).

**Keys**
- `wait` 0.2, `delay` 0, `cnt` −1 (infinite), `cone` 60, `angle` (facing gate)
- `message`, `noise`
- **`setthread <label>`** (or `file::label`): the thread receives `parm.other` = activator (`:47-193`, `:363-373`; `fgame/gamescript.cpp:968-1027`)
- `target`, `health`

**Classes**
- **`trigger_multiple`**; **`trigger_once`** (sf 1 NOTOUCH) (`:1118-1170`).
- **`trigger_use`** / **`trigger_useonce`**: fire on +use only (`:1919-1977`).
- **`trigger_hurt`**: `damage` 10 (`:1994-2044`).
- **`trigger_push`**: `speed` 1000; `angle`, or `target` for a computed arc (`:1324-1408`).
- **`trigger_teleport`** → `target` = `func_teleportdest`. sf 1 VISIBLE, 4 toggles players, 8 monsters, 16 projectiles, 32 NO_EFFECTS (`fgame/misc.cpp:596-642`, `:883`, `:898`).
- `trigger_relay`, `trigger_multipleall`, `trigger_music`, `trigger_changelevel` (single-player).

### 5.5 Breakables and ladder

- **`func_crate`** (`fgame/crateobject.cpp:30-116`): sf 1 INDESTRUCTABLE, 2 NOTSTACKEDON.
  - `health`: code default 100.
  - `debristype`: 0 32u wood, 1 64u wood, 2 16u cardboard, 3 32u cardboard.
  - Retail example: `health 50`, `debristype 0`.
- **`func_barrel`** (`fgame/barrels.cpp:74-178`): sf 1 INDESTRUCTABLE. `barreltype oil|water|gas|<empty>`; health is always 75, and `gas` clears INDESTRUCTABLE.
- **`func_window`** (`fgame/windows.cpp:47-175`): `health` 250.
  - `debristype`: 0 clear, 1 coloured.
  - `target`: a `script_object` that becomes the broken version.
  - sf 1 WINDOW_BROKEN_BLOCK.
- **`func_explodingwall`** (`fgame/misc.cpp:115-230`) and **`func_exploder`** / **`func_multi_exploder`** / **`func_explodeobject`** (`fgame/explosion.cpp:145-380`). Retail instead uses `script_object`s named `exploder`/`explodersmashed`/`exploderchunk` sharing `#set`, run through `thread global/exploder.scr::main` (`Pak0.pk3:global/exploder.scr:1-28`).
- **`func_ladder`**: `angle` only, plus an origin brush on the climb face (§1.3).

### 5.6 Sound

- **`sound_speaker`** (`fgame/trigger.cpp:1619-1646`, `fgame/trigger.h:271-273`)
  - sf 1 AMBIENT-ON, 2 AMBIENT-OFF, 4 NOT_PLAYERS, 8 MONSTERS, 16 PROJECTILES, 32 TOGGLE.
  - Keys `noise`, `volume`, `channel`, `setthread`.
  - **`sound_randomspeaker`** adds `mindelay` 3, `maxdelay` 10, `chance` 1.
- No retail MP map uses speakers. They use script loops instead:
  - `loopsound <alias> [vol] [mindist]` (`fgame/entity.cpp:719-727`)
  - `playsound <alias>` (`:526-534`)
  - `stoploopsound`
  - `soundtrack` / `forcemusic` (`fgame/scriptthread.cpp:590-621`)

---

## 6. Lighting and compiler reference

### 6.1 Build pipeline

The EA MOHRadiant menu (`MOHTools/default.qe4`) runs:

```
q3map -v -gamedir ../mohaa/ map.map          # BSP
q3map -vis -v [-fast] -gamedir ../mohaa/ map.map
mohlight -v [-fast|-final] -gamedir ../mohaa/ map.map
```

- `q3map -light` does no lighting. It prints "Light compiling is out on its own now. Run MOHLight.exe" (`Q3map.exe (strings)`).
- q3map `-info` reports "BSP weighs in at %.2f MB out of an allowed 10.00 MB". That limit is advisory.

### 6.2 Q3map.exe 1.34 options (BSP stage), from the usage text in strings

| Option | Meaning (from strings) |
|---|---|
| `-v`, `-threads N`, `-gamedir dir`, `-moddir dir` | verbose, thread count, paths |
| `-info` / `-vis` | print lump sizes of `<map>.bsp` / run the VIS stage (§6.3) |
| `-nowater -nofill -nodetail -nohint -fulldetail -leaktest -verboseentities` | the usual q3map switches (`-leaktest` aborts on a leak) |
| `-onlyents` / `-onlytextures` | replace the entity lump only (refused if brushes changed) / "isn't working now" |
| `-nosubdivide -nocurves -notjunc -nomerge` | no surface subdivision / no patches / no T-junction fixing / skip brush merging |
| `-expand`, `-fakemap`, `-tmpout` | write `expanded.map` / write `fakemap.map` / use `/tmp` |
| `-detailterrainborders` | "force terrain mesh boundaries to be flagged max detail" |
| `-fast`, `-all` | undocumented |
| `-snapdistance [d]` | default 0.1, but "Ignoring snap to grid; disabled in code due to lighting errors" |
| `-lightmapdensity [d]`, `-smoothangle [a]` | default lightmap density (overrides worldspawn); vertex smoothing angle |
| `-blocksize [size]`, `-chopblocklast` | BSP block chop, default 1024, 0 = off; chop blocks after the other chops |
| `-nomanvis` | ignore manual vis (`vis_leafgroup`) |
| `-nostatic` / `-visiblestatic` | disable "Static Collision Masks" / draw them with `textures/common/static_visible`. Mechanism **UNVERIFIED** |

### 6.3 Q3map VIS options (`q3map -vis …`)

- **Options:**
  - `-fast`: fast vis.
  - `-level N`: test level.
  - `-nosort`: undocumented.
  - `-deleteprt`: delete the .prt file afterwards.
  - `-tmpin` / `-tmpout`: use /tmp.
  - `-nofarplane`: ignore farplane culling.
  - `-farplane N`: override the farplane distance.
  - `-threads`, `-v`, `-gamedir`, `-moddir`.
- **Worldspawn keys VIS reads:** `farplane` and `farplane_cull` (portals beyond farplane_dist are culled), and `vis_derived` (`Q3map.exe (strings)`).

### 6.4 MOHlight.exe 1.48 options (verbatim help, defaults included)

| Option | Meaning / default |
|---|---|
| `-v`/`-verbose`, `-threads N` (default all CPUs), `-gamedir`, `-moddir` | general |
| `-area N` / `-point N` | surface-light / point-light scale, default 1.0 |
| `-ambient R G B` | ambient light on a 0–255 scale |
| `-notrace` | no occlusion (no shadows) |
| `-nosurfshadows`, `-nocurveshadows`, `-nopatchshadows` | brushes / curves / terrain cast no shadows |
| `-nocurvelight`, `-nopatchlight` | curves / terrain are not lit |
| `-staticshadows` | static models cast shadows (off by default) |
| `-nodiffusesun` | skip the diffuse sunlight pass |
| `-nogrid`, `-onlygrid`, `-extragrid`, `-radgrid` | no light grid / grid only / full-detail grid / radiosity into the grid |
| `-vertex` | vertex lighting |
| `-randomdir N` | random lighting direction, default 0 |
| `-bounce N` | radiosity bounces, default **8** |
| `-chop N`, `-minchop N` | radiosity patch size / smallest patch, both default 64. minchop < 32 warns ("use -extra") |
| `-radscale N` | radiosity scale, default 0.95; 0 = no radiosity |
| `-attenuate N` | percent of radiosity lost per 16 u, on top of 1/d²; default 4 |
| `-smoothangle N` | default 45 |
| `-extra` | high-detail sampling (currently sunlight only) |
| `-final` | all options to full detail except `-chop` |
| `-fast` | faster, lower quality |
| `-border`, `-raddebug 1-4` | debug lightmap borders / debug colouring |

- Radiosity is off when the BSP has no VIS data ("Radiosity turned off due to no VIS data being present").
- MOHlight re-lights static models per vertex ("Re-Radiositify Lighting For Static Models") and writes the vertex colours to LUMP_STATICMODELDATA.

### 6.5 Worldspawn lighting keys

Sources:
- MOHlight strings: `ambientlight`, `ambient`, `suncolor`, `sunlight`, `sundirection`, `sundiffuse`, `sundiffusecolor`, and `overbright` with the values `none/world/entities`.
- q3map strings: `lightmapdensity`.
- EA docs: `entdefs.pk3:code/worldspawn.cpp`.
- Retail `.map` values.

The game ignores all of these keys. The renderer reuses some of them for dynamic entity lighting (§4.4).

| Key | Semantics | Default / retail examples |
|---|---|---|
| `ambientlight` | "R G B" ambient; the renderer adds it to entity lighting too | retail "5 5 5" to "10 10 10" |
| `ambient` | scalar ambient, coloured by the worldspawn `_color` key | obj_team2: `ambient 35`, `_color "1.0 0.9 0.8"` |
| `suncolor` | "R G B" colour and intensity of the sun; "Full daylight would be 70 70 70" | retail "65 60 45" … "70 70 70" |
| `sunlight` | "R G B". The renderer treats it exactly like `suncolor`, and whichever appears last wins. MOHlight semantics **UNVERIFIED** | mohdm1 "255 243 171" together with suncolor |
| `sundirection` | "pitch yaw roll" of the sun (renderer: `AngleVectorsLeft`) | "320 150 0", "315 210 0" |
| `sundiffuse` | fraction of sunlight made diffuse | default 1; retail 1–3 |
| `sundiffusecolor` | "R G B" in suncolor scale | m2l1 "95 95 105" |
| `lightmapdensity` | world units per lightmap texel | **default 32** (measured: dlightdef.lightmapResolution = 32 when the key is absent, 16 in mohdm1 which sets 16). Per face: `surfaceDensity N` in .map |
| `overbright` | `none` / `world` / `entities` / `all` | EA: forces overbright on or off for world/entity lighting |
| `sunflarename`, `sunflaredirection` | renderer sun flare; the default name is `sun` | `sunflarename none` is common |

### 6.6 `light` entity keys (MOHlight)

Sources:
- EA def `entdefs.pk3:code/light.cpp`.
- MOHlight strings: `light`, `_color`, `_light`, `entity_light`, `no_entity_light`, `spawnflags`, `spot_angle`, `angles`, `target`, `targetname`, `overbright_range`, `falloff`, `spot_dir`, `spot_radiusbydistance`, `radius` (TIKI), `lightoffset` (TIKI).
- The game deletes `light` entities at spawn (`fgame/light.cpp:147-150`), but the compiler leaves them in the entity lump (measured: 5,415 in retail BSPs).

| Key / flag | Meaning |
|---|---|
| `light` | intensity, default 300. Retail values are often 3–100 (measured: 1,603 lights in the MP .maps) |
| `_color` (EA doc: `color`) | "r g b" 0–1 |
| spawnflags 1 `LINEAR` | linear falloff; `falloff` sets its rate (default 1) |
| spawnflags 2 `NO_ENTITIES` | lights only the world; same as key `no_entity_light` |
| spawnflags 4 `ENTITY_TRACE` | trace between light and entity; key `entity_trace` |
| spawnflags 8 `ENTITY_ONLY` | lights entities only, not the world (EA def; 2 uses in retail) |
| `overbright_range` | fraction of the overbright range, 0.01–2.5, default 1. Retail 0.1–1.05 |
| **spotlight** | EITHER `target` → an `info_null`/`info_notnull` ("If it targets another entity it will become a spot light"), OR `angles "pitch yaw roll"` + `radius N` ("make this a spot light of the given radius"). `spot_angle` is the cone angle, default 45. Retail example: `angles "90 0 0"` (pointing down) with `radius 60` and `light 300–400` (`MOHTools/maps/MP/obj_team2.map`). A missing target prints "light at … has missing target" |
| compiler output | Lights that affect entities become sphere lights: LUMP_SPHERELIGHTS with `spot_light`, `spot_dir` and `spot_radiusbydistance` (§7) |

### 6.7 Surface flags and contents (`qcommon/surfaceflags.h:31-121`)

**Contents bits**

| bit / name | bit / name | bit / name | bit / name |
|---|---|---|---|
| `0x1` SOLID | `0x2` LADDER | `0x8` LAVA | `0x10` SLIME |
| `0x20` WATER | `0x40` FOG | `0x80` CLAYPIDGEON / NOTTEAM1 | `0x100` NOTTEAM2 / BBOX |
| `0x200` NOBOTCLIP | `0x2000` FENCE | `0x8000` AREAPORTAL | `0x10000` PLAYERCLIP |
| `0x20000` MONSTERCLIP | `0x40000` WEAPONCLIP | `0x80000` VEHICLECLIP | `0x100000` SHOOTONLY |
| `0x200000` DONOTENTER | `0x400000` BOTCLIP | `0x800000` MOVER | `0x1000000` ORIGIN |
| `0x2000000` BODY | `0x4000000` CORPSE | `0x8000000` DETAIL | `0x10000000` STRUCTURAL |
| `0x20000000` TRANSLUCENT | `0x40000000` TRIGGER | `0x80000000` NODROP |  |

**Surface bits**

| bit / name | bit / name | bit / name | bit / name |
|---|---|---|---|
| `0x1` NODAMAGE | `0x2` SLICK | `0x4` SKY | `0x8` LADDER |
| `0x10` NOIMPACT | `0x20` NOMARKS | `0x40` CASTSHADOW | `0x80` NODRAW |
| `0x100` NOLIGHTMAP | `0x200` ALPHASHADOW | `0x400` NOSTEPS | `0x800` NONSOLID |
| `0x1000` OVERBRIGHT | `0x2000` PAPER | `0x4000` WOOD | `0x8000` METAL |
| `0x10000` ROCK | `0x20000` DIRT | `0x40000` GRILL | `0x80000` GRASS |
| `0x100000` MUD | `0x200000` PUDDLE | `0x400000` GLASS | `0x800000` GRAVEL |
| `0x1000000` SAND | `0x2000000` FOLIAGE | `0x4000000` SNOW | `0x8000000` CARPET |
| `0x10000000` BACKSIDE | `0x20000000` NODLIGHT | `0x40000000` HINT | `0x80000000` PATCH |

**surfaceparm names**
- Renderer table (`renderergl1/tr_shader.c:2129-2181`): water slime lava playerclip monsterclip fence weaponclip vehicleclip nodrop nonsolid origin trans detail structural areaportal fog sky alphashadow slick noimpact nomarks ladder nodamage nosteps paper wood metal rock dirt grill grass mud puddle glass gravel sand foliage snow carpet nodraw castshadow nolightmap nodlight hint.
- The **compiler** accepts the same set plus `shootonly` and `obscuring` (`Q3map.exe (strings)`).
- In .map face modifiers the compiler also accepts `overbright` and `window`.

**Material effects**
- Footsteps play `snd_step_<mat>` with mat = foliage, snow, carpet, sand, puddle, glass, gravel, mud, dirt, grill, grass, **stone (ROCK or none)**, paper, wood, metal. Water gives `wade`/`puddle` (`fgame/sentient.cpp:3092-3154`).
- Bullet impacts play `snd_bh_<mat>` plus the matching effect (`cgame/cg_parsemsg.cpp:83-160`).
- `nosteps` silences footsteps.

**Bullet penetration** (`fgame/weaputils.cpp:2254-2257`)
- Always through FOLIAGE, GLASS, PUDDLE and PAPER.
- Through WOOD if the weapon has `bulletthroughwood`.
- Through METAL or GRILL if it has `bulletthroughmetal`.

**How flags reach the BSP (important for generators)**
- **MOH .map faces carry explicit flags.** Radiant writes the shader's surfaceparm bits into each face:
  - Face format: `( p1 ) ( p2 ) ( p3 ) shader xoff yoff rot xscale yscale CONTENTS SURFFLAGS VALUE [+surfaceparm X] [-surfaceparm X] [surfaceDensity N] [subdivisions F]` (`MOHTools/maps/MP/*.map`).
  - Examples: `common/caulk … 0 160 0`, `common/clip … 196608 2193 0`, `common/origin … 16777216 2176 0`, `common/nodraw … 536870912 2224 0`.
- **Shader lump entries are unique (name, surfaceFlags, contentFlags) pairs**, so the same shader appears several times with different flags (measured: mohdm1).
- **Every lump entry has a material bit.** Entries with no material get **ROCK 0x10000** (measured: all shaders in mohdm1/mohdm2). The compiler logic behind this is **UNVERIFIED**.

### 6.8 Shader keywords that matter for compiling

- **Compiler** (`Q3map.exe`/`MOHlight.exe` strings):
  - `qer_editorimage`
  - `q3map_lightimage`
  - `q3map_surfacelight` / `surfacelight N`: area light
  - `surfacecolor`, `surfaceangle`
  - `surfacedensity N`: lightmap density
  - `q3map_lightsubdivide`, `q3map_globaltexture`, `q3map_backsplash`, `q3map_reflectivity`, `q3map_backshader`
  - `q3map_flare` / `flareshader`
  - `tesssize`, `subdivisions`, `tesselation`
  - `cull none|twosided|disable|back|backside|backsided`
  - `deformVertexes autosprite`: the surface must be a quad (MOHlight warns otherwise)
- **Renderer** (`ParseShader`, `renderergl1/tr_shader.c:2220` onward):
  - `q3map_sun r g b intensity yaw pitch` sets the renderer sun (`:2279-2305`). The default sun direction is (0.45, 0.3, 0.9) (`renderergl1/tr_bsp.c:2252-2261`).
  - Other keywords: `skyparms`, `portalsky`, `portal`, `sort`, `spritegen`, `spritescale`, `nomipmaps`, `nopicmip`, `force32bit`, `polygonOffset`, `entityMergable`, `noMerge`, `clampTime`, and `#if/#else/#endif` blocks.
- **Fence masks.** `dshader_t.fenceMaskImage` names a TGA whose alpha drives per-pixel collision for FENCE contents. `nomask` = none, `ignore` = fully passable (`qcommon/cm_fencemask.c:528-543`). Q3map warns "Fence masks must only be used with fence or nodraw".

---

## 7. BSP version 19 file format (as loaded by OpenMoHAA)

Everything is little-endian. Structure sizes below were checked against the `sizeof` values printed by `RE_PrintBSPFileSizes` (`renderergl1/tr_bsp.c:2467-2495`). Lump lengths of retail `mohdm1.bsp` and `m1l1.bsp` are exact multiples of these sizes (measured).

### 7.1 Header (236 bytes) (`qcommon/qfiles.h:358-364`, `:467-516`)

| Offset | Field | Notes |
|---|---|---|
| 0 | `char ident[4]` | = `"2015"` (BSP_IDENT = '2','0','1','5'). Not checked by the loaders |
| 4 | `int version` | = 19. Loaders accept 17–21 (`qcommon/cm_load.c:894`) |
| 8 | `int checksum` | returned as the map checksum (`qcommon/cm_load.c:887`, `:753-771`) |
| 12 | `lump_t lumps[28]` | `{int fileofs; int filelen;}`; offsets are from the file start. The first lump is at offset 236 |

For version ≤ 18, lumps after BRUSHES are shifted by +1 because slot 13 was FOGS (`Q_GetLumpByVersion`, `qcommon/qfiles.h:518-528`).

### 7.2 Lump table (v19) (`qcommon/qfiles.h:474-508`)

| # | Lump | Element (bytes) | Notes |
|---|---|---|---|
| 0 | SHADERS | dshader_t (140) | must be ≥ 1 |
| 1 | PLANES | dplane_t (16) | |
| 2 | LIGHTMAPS | 128×128×3 = **49152** per page | RGB, no alpha (`renderergl1/tr_bsp.c:211`) |
| 3 | SURFACES | dsurface_t (108) | |
| 4 | DRAWVERTS | drawVert_t (44) | |
| 5 | DRAWINDEXES | int (4) | |
| 6 | LEAFBRUSHES | int (4) | |
| 7 | LEAFSURFACES | int (4) | |
| 8 | LEAFS | dleaf_t (64) | |
| 9 | NODES | dnode_t (36) | |
| 10 | SIDEEQUATIONS | dsideequation_t (32) | index 0 = none |
| 11 | BRUSHSIDES | dbrushside_t (12) | |
| 12 | BRUSHES | dbrush_t (12) | |
| 13 | MODELS | dmodel_t (40) | |
| 14 | ENTITIES | text | limit 0x100000 bytes |
| 15 | VISIBILITY | `int numClusters; int clusterBytes; byte bits[numClusters*clusterBytes]` | `renderergl1/tr_bsp.c:294-321` (mohdm1: 699 clusters, 88 bytes) |
| 16 | LIGHTGRIDPALETTE | 768 bytes = 256 RGB | any other size disables the grid |
| 17 | LIGHTGRIDOFFSETS | uint16 | see 7.5 |
| 18 | LIGHTGRIDDATA | bytes (RLE) | see 7.5 |
| 19 | SPHERELIGHTS | dspherel_t (56) | count must be < 1532 |
| 20 | SPHERELIGHTVIS | int lists | see 7.6 |
| 21 | LIGHTDEFS | dlightdef_t (52) | **one per draw surface** (measured count = SURFACES count). OpenMoHAA does not load it |
| 22 | TERRAIN | cTerraPatch_t (388) | §8 |
| 23 | TERRAININDEXES | int16 patch index | referenced by leafs |
| 24 | STATICMODELDATA | 3 bytes (RGB) per static-model vertex | |
| 25 | STATICMODELDEF | cStaticModel_t (164) | |
| 26 | STATICMODELINDEXES | uint16 static-model index | referenced by leafs |
| 27 | DUMMY10 | unused (length 0) | |

Loaders: `qcommon/cm_load.c:899-1000` loads shaders, planes, surfaces+verts (patch collision), leafbrushes, leafsurfaces, leafs, nodes, sideequations, brushsides, brushes, models, entities, visibility and terrain, but no static models. `RE_LoadWorldMap` is at `renderergl1/tr_bsp.c:2244-2446`.

### 7.3 Structures (`qcommon/qfiles.h`)

**dshader_t, 140 bytes** (`:536-542`)
```
0   char  shader[64]
64  int   surfaceFlags
68  int   contentFlags
72  int   subdivisions          // per-shader patch subdivisions used for collision (cm_load.c:132)
76  char  fenceMaskImage[64]    // "nomask", "ignore", or a .tga path
```

**dplane_t, 16 bytes**: `float normal[3]; float dist;` (`:552-555`).

**dsurface_t, 108 bytes** (`:658-681`)
```
0   int   shaderNum
4   int   fogNum                // always -1 in v19
8   int   surfaceType           // 1 MST_PLANAR, 2 MST_PATCH, 3 MST_TRIANGLE_SOUP, 4 MST_FLARE (5 MST_TERRAIN is internal)
12  int   firstVert
16  int   numVerts
20  int   firstIndex
24  int   numIndexes
28  int   lightmapNum           // -1 = none
32  int   lightmapX, 36 lightmapY, 40 lightmapWidth, 44 lightmapHeight
48  float lightmapOrigin[3]
60  float lightmapVecs[3][3]    // patches: [0],[1] = LOD bounds; planar: [2] = face normal (measured)
96  int   patchWidth
100 int   patchHeight
104 float subdivisions          // MOH addition (float), patch subdivision
```

**drawVert_t, 44 bytes** (`:630-636`): `0 float xyz[3]; 12 float st[2]; 20 float lightmap[2]; 28 float normal[3]; 40 byte color[4]`.

**dleaf_t, 64 bytes** (`:564-582`). All fields are int:
```
cluster, area, mins[3], maxs[3],
firstLeafSurface, numLeafSurfaces, firstLeafBrush, numLeafBrushes,
firstTerraPatch, numTerraPatches,        // index into TERRAININDEXES
firstStaticModel, numStaticModels        // index into STATICMODELINDEXES
```
v17 leafs (`dleaf_t_ver17`, 56 bytes) lack the last two fields.

**dnode_t, 36 bytes** (`:557-562`): `int planeNum; int children[2]` (negative child = −(leaf+1)); `int mins[3], maxs[3]`.

**dsideequation_t, 32 bytes** (`:605-608`): `float fSeq[4]; float fTeq[4];`. Texture equations used for fence-mask lookups; `equationNum 0` means none (`qcommon/cm_load.c:554-559`).

**dbrushside_t, 12 bytes** (`:610-616`): `int planeNum; int shaderNum; int equationNum;`. The **extra MOH field** is `equationNum`.

**dbrush_t, 12 bytes** (`:618-622`): `int firstSide; int numSides; int shaderNum;`.

**dmodel_t, 40 bytes** (`:530-534`): `float mins[3], maxs[3]; int firstSurface, numSurfaces, firstBrush, numBrushes;`.
- **Submodels (index > 0) are stored in entity-local space**: vertices, planes and bounds are relative to the entity's `origin` key (measured: mohdm1 `*1` door bounds (−2,−2,−62)–(70,2,62) and verts at x = −2).
- Q3map writes `origin` for every brush entity. With an origin brush it uses that brush; otherwise it uses the **centre of the bounds** (measured: mohdm3 trigger_use `*1`, .map box 3592..3656 × −1472..−1468 × 200..328 → origin "3624 −1470 264", bounds ±32/±2/±64).

**dspherel_t / mapspherel_t, 56 bytes** (`:709-718`, `:740-749`)
```
0  float origin[3]; 12 float color[3]; 24 float intensity; 28 int leaf;
32 int needs_trace; 36 int spot_light; 40 float spot_dir[3]; 52 float spot_radiusbydistance
```

**dlightdef_t, 52 bytes** (`:726-738`)
```
int lightIntensity; int lightAngle; int lightmapResolution; int twoSided; int lightLinear;
float lightColor[3]; float lightFalloff; float backsplashFraction; float backsplashDistance;
float lightSubdivide; int autosprite
```
Typical measured values: resolution 32 (the lightmapdensity), backsplashFraction 0.05, backsplashDistance 24, and lightIntensity 1500/3000 on surfacelight faces.

**cTerraPatch_t, 388 bytes**: see §8.

**cStaticModel_t, 164 bytes** (`:453-460`; loader `renderergl1/tr_bsp.c:2103-2145`)
```
0   char  model[128]         // as written in the .map, e.g. "static//corona_orange.tik";
                              // "models/" is prepended unless it already starts with "models" (tr_staticmodels.cpp:82-86)
128 float origin[3]
140 float angles[3]
152 float scale
156 int   firstVertexData    // BYTE offset into STATICMODELDATA (multiple of 3)
160 int   numVertexData      // number of vertices (3 bytes each)
```
`dstaticModel_t` (`:700-707`) declares `short numVertexData`. It has the same size, but the loader reads `int` (measured: 0, 12, 138 for 4-, 42-, … vertex models).

### 7.4 Limits (`qcommon/qfiles.h:369-407`, others)

| Limit | Value |
|---|---|
| MAX_MAP_MODELS / MAX_SUBMODELS | 0x400 = 1024 (`qcommon/cm_local.h:32`) |
| MAX_MAP_BRUSHES | 0x8000 |
| MAX_MAP_ENTITIES | 0x2000 (OpenMoHAA, raised) |
| MAX_MAP_ENTSTRING | 0x100000 |
| MAX_MAP_SHADERS | 0x400 |
| MAX_MAP_AREAS | 0x100 (area mask is 32 bytes, `qcommon/q_shared.h:331`) |
| MAX_MAP_PLANES / NODES / BRUSHSIDES / LEAFS / LEAFFACES / PORTALS | 0x20000 each |
| MAX_MAP_LEAFBRUSHES | 0x40000 |
| MAX_MAP_LIGHTING / LIGHTGRID | 0x800000 |
| MAX_MAP_VISIBILITY | 0x200000 |
| MAX_MAP_DRAW_SURFS | 0x20000 |
| MAX_MAP_DRAW_VERTS / DRAW_INDEXES | 0x80000 |
| MAX_MAP_SPHERE_L_SIZE (sphere lights) | 1532 |
| MAX_PATCH_VERTS | 1024 (`qcommon/cm_load.c:609`) |
| LIGHTMAP_SIZE | **128** (`qfiles.h:405-407`) |
| MAX_GENTITIES (game entities incl. clients) | 1024 (`qcommon/q_shared.h:1662-1663`) |
| MAX_MODELS / MAX_SOUNDS (configstrings) | 1024 / 512 (`qcommon/q_shared.h:1675-1676`) |
| Coordinates | entity origins go over the network as `round(c·4 + 32768)` in 16 bits (`qcommon/msg.cpp:2525-2536`), so **keep the map within ±8192** on every axis. The navmesh also assumes ±8192 |

### 7.5 Light grid (`renderergl1/tr_bsp.c:1984-2056`, `renderergl1/tr_light.c:750-897`)

**Grid layout**
- Cell size is **32×32×32 for v19**. v20 uses 48×48×64 and v21 uses 80³ (`renderergl1/tr_bsp.c:2003-2019`).
- `gridMins[i] = size·ceil(model0.mins[i]/size)`
- `gridMaxs[i] = size·floor(model0.maxs[i]/size)`
- `bounds[i] = (gridMaxs−gridMins)/size + 1`

**Offsets lump**
- It holds exactly `bounds[0] + bounds[0]·bounds[1]` uint16 values; any other size disables the grid (measured: mohdm1 bounds 142×159×45 → 22720 ✓).
- The first `bounds[0]` values are per-X **high parts**.
- For column (x, y): `dataOfs = offsets[bounds[0] + y + bounds[1]·x] + (offsets[x] << 8)`.

**Data lump**
- Each column is RLE along Z.
- Read a signed byte n:
  - n < 0: `−n` literal palette indices follow.
  - n ≥ 0: a run of `n+2` copies of the next byte.
- Palette index 0 means "no sample" (inside solid).
- Colours are `palette[idx*3..+2]`. The engine blends 8 neighbours trilinearly.

### 7.6 Sphere-light vis (`renderergl1/tr_bsp.c:371-425`)

- The lump is a flat int array, walked leaf by leaf.
- Per leaf: optional `-2` (the sun), then sphere-light indices, terminated by `-1`. An empty leaf is just `-1`.
- If the array has exactly one entry per leaf, it is ignored.

### 7.7 Other lump semantics

- **Lightmaps** are 128×128 RGB pages. Brush and patch surfaces use `lightmapNum/X/Y/Width/Height`. Terrain patches use `iLightMap` and `s,t` (§8).
- **Static-model vertex colours**: `STATICMODELDATA[firstVertexData + 3·i]` = RGB for vertex i, in the order of the TIKI's surfaces and vertices.
- **Entity lump**:
  - Static models (`static_*` classnames) are **removed** from it and moved to STATICMODELDEF.
  - `light`, `info_pathnode` and similar entities stay (measured).
  - Only the fields `origin`, `angles`/`angle`, `scale`, `model` and `spawnflags` are read for static models (`Q3map.exe (strings)`).

---

## 8. Terrain (`terrainDef` → LUMP_TERRAIN)

### 8.1 Packed patch `cTerraPatch_t`, 388 bytes (`qcommon/qfiles.h:420-451`)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | u8 | flags | 0x40 TERPATCH_FLIP (flip triangle diagonal), 0x80 TERPATCH_NEIGHBOR (alternate root split). Retail has 0x00/0x80 about 50/50 (measured: 7,270 patches) |
| 1 | u8 | lmapScale | must be > 0, otherwise "invalid map" (`renderergl1/tr_bsp.c:475-477`). Lightmap is `lmapScale·8+1` texels square, `64/lmapScale` u per texel. **Retail always 2** (17×17 texels, 32 u/texel) |
| 2,3 | u8 | s, t | texel offset of the patch block inside lightmap page `iLightMap` |
| 4 | float[2][2][2] | texCoord[x][y][s/t] | texture st at the 4 corners: [0][0] = (x0,y0), [1][0] = (x0+512,y0), [0][1] = (x0,y0+512) (`renderergl1/tr_terrain.c:770-850`) |
| 36,37 | s8 | x, y | patch origin = `(x<<6, y<<6)`, i.e. **64-u grid**, range −8192..8128 |
| 38 | s16 | iBaseHeight | z of height 0 |
| 40 | u16 | iShader | shader index; collision takes contents/flags from it (`qcommon/cm_load.c:715-717`) |
| 42 | u16 | iLightMap | lightmap page |
| 44–50 | s16 ×4 | iNorth, iEast, iSouth, iWest | neighbour patch indices, −1 = none |
| 52 | u16[2][63] | varTree | ROAM variance trees for the 2 root triangles. Low 11 bits = variance; bits 12–15 = flags (4 INVISIBLE, 8 DELETE) (`renderergl1/tr_bsp.c:506-518`, `renderergl1/tr_terrain.c:62-63`) |
| 304 | u8[81] | heightmap | 9×9, index **`y*9 + x`**, **z = iBaseHeight + 2·h** |
| 385 | 3 | padding | |

### 8.2 Geometry (`qcommon/cm_terrain.c:240-326`)

- A patch is **8×8 cells of 64 u = 512×512 u**.
- Height resolution is **2 u**. The range above `iBaseHeight` is 0..510 u per patch.
  - The compiler errors "Terrain patch at (%d,%d): maximum height variation %d > %d" when a patch exceeds this. The limit value is presumably 510 (**UNVERIFIED**).
  - Retail patches always have min(h) = 0, i.e. baseZ = patch minimum (measured).
- Each cell is split into 2 triangles. The diagonal alternates in a checkerboard pattern `(i+j)&1`, and TERPATCH_FLIP inverts it.
- Collision bounds are `x0..x0+512`, `y0..y0+512`, `z0..max`.
- Leafs reference patches through TERRAININDEXES (int16).

### 8.3 LOD (renderer only; collision always uses the full 8×8)

- ROAM binary triangle tree with 2 roots per patch and 63 variance nodes each, so depth is ≤ 6.
- `ter_maxlod` 6 (range 3–6, latched)
- `ter_error` 4 (screen error, 0.1–16)
- `ter_maxtris` 24576 (16384–65536)
- `ter_cull` 1, `ter_lock` (cheat), `ter_restart` command
- Cvar definitions: `renderergl1/tr_terrain.c:1628-1645`.

### 8.4 `.map` terrainDef syntax (from EA sources; field meanings partly **UNVERIFIED**)

```
{
 terrainDef
 {
  W H 0                       // vertex grid, (W-1) and (H-1) are multiples of 8 (e.g. 17 9, 25 57, 233 249)
  X Y Z                       // origin of the grid (lower-left)
  {                            // ((W-1)/8+1)*((H-1)/8+1) lines (checked on 10 EA maps):
   F 0 ( shader xoff yoff rot N xscale yscale contents surfflags value [surfaceDensity N] )
  }
  {                            // W*H lines, one per vertex (order UNVERIFIED, likely row-major):
   height ( tokens ) ( tokens ) // height relative to Z; tokens from {nodraw invisible important trivial maxdetail nodetail locked}
  }
 }
}
```

- `F` alternates 0/1, probably the flip or neighbour flag.
- `N` is 256 or 512 in retail.
- Example: `MOHTools/maps/MP/mohdm6.map` (17×9 → 2 patches).
- q3map flag `-detailterrainborders` marks terrain borders as max detail.
