# Codex Arena 01

`codex_arena01` is a small, symmetrical Medal of Honor: Allied Assault
deathmatch gray-box generated from code and designed for OpenMoHAA bots.

It contains:

- a sealed 2,560 × 2,560 × 512-unit arena;
- a central platform with four broad stairways;
- simple cover and circulating lanes;
- 16 neutral, 8 Allied, and 8 Axis spawns;
- four original procedural checker textures;
- a compiled AA version-19 BSP.

The original AA Q3map, VIS, and MOHlight stages completed successfully.
OpenMoHAA 0.82.1 loaded the distributed PK3 and generated Recast navigation.
A full-data playtest confirmed that a bot could spawn and walk around the map.

![In-game bot playtest](../../docs/codex_arena01-ingame.png)

## Install

Copy `codex_arena01.pk3` into the game's `main` directory, then run:

```text
sv_maxbots 8
sv_numbots 4
g_gametype 1
map dm/codex_arena01
```

## Source and rebuild

The editable `.map`, scripts, and textures are under `source/main`. The
generator and PowerShell build script are under `tools`.

With Node.js and
[MOHTools](https://github.com/pstngh/MOHTools) available:

```powershell
.\tools\build_map.ps1 `
  -MOHToolsDir "C:\path\to\MOHTools" `
  -BuildRoot ".\build"
```

The EA compilers are not included here. They are licensed for use with Medal
of Honor: Allied Assault. The retail game data is also required for standard
multiplayer scripts, player models, weapons, sounds, and other stock content.

## Prototype status

This first version proves the source-to-compiled-map pipeline and bot
navigation. Its checker materials and lighting are intentionally unfinished;
the first playtest showed that it needs a brighter lighting pass. The planned
visual direction is to reference the stock `obj_team2` industrial/bunker
materials without redistributing EA texture files.

See [the research notes](../../docs/MOHAA-map-generation-notes.md) for the map
format, compiler pipeline, corpus measurements, validation evidence, and the
candidate `obj_team2` material palette.
