# moh-maps

Tools and knowledge for making **Medal of Honor: Allied Assault / OpenMoHAA**
multiplayer maps, built so an AI agent (or you) can make any map, bug-free:

1. **convert CS:GO maps** to MOHAA;
2. **create maps from scratch**: invented, described in words, or recreated
   from a screenshot.

Every map goes from idea to a tested, playable `.pk3` in one automated loop.

![mk_village: square, street and town hall](docs/images/mk_village.jpg)

*`maps/mk_village`, written entirely in Python with mohkit.* Below: a room from
stock mohdm1 recreated from one screenshot (reference, recreation, blend; see
[docs/from-reference.md](docs/from-reference.md)).

![reference | recreation | blend](docs/images/ref_room_compare.jpg)

```text
maps/<name>/build.py ──▶ .map ──EA Q3map/VIS/MOHlight──▶ .bsp ──▶ .pk3 ──OpenMoHAA──▶ screenshots + bot match
```

## What's here

- **`mohkit/`**, the toolkit:
  - `.map` and BSP v19 read/write;
  - map authoring (`Carver`: describe the playable air, get a sealed,
    textured, caulked hull; `kit`: stairs, window/door niches, roofs, trims,
    lamps; stock props with collision data);
  - validation and top-down plans;
  - a driver for EA's original compilers (native or through Wine/CrossOver);
  - automated OpenMoHAA runs (scripted cameras, clean screenshots, bot
    matches, log triage);
  - a retail asset catalog;
  - CS:GO readers (VPK, VTF, VMT, BSP, MDL) and a CS:GO → MOHAA converter.
- **`docs/`**, a verified knowledge base: design rules, the `.map` format,
  compiler flags and errors, entities, lighting recipes, materials, scripting,
  testing, CS:GO conversion, engine facts with source citations. Start at
  [docs/README.md](docs/README.md).
- **`maps/`**, map projects. [`mk_village`](maps/mk_village) is a Normandy
  crossroads DM map written entirely in Python (squares, streets, a two-storey
  town hall, house, warehouse, stock props, gable roofs).
  [`mk_ref_room`](maps/mk_ref_room) is a room rebuilt from a single screenshot.
- **`reference/`**, the stock EA `.map` sources (Allied Assault, Spearhead,
  Breakthrough) plus a few community maps: the best examples of how real MOHAA
  maps are built.
- **`data/`**, catalogs generated from those sources: every material with
  size, scale and usage; every entity key; every stock prop with bounds and
  collision; the lighting of every MP map.

## Quick start

```sh
python3 -m venv .venv && .venv/bin/pip install pillow numpy
.venv/bin/python -m mohkit setup                    # fetch the EA compilers (MOHTools) into .toolchain/
.venv/bin/python -m mohkit doctor                   # finds your game, OpenMoHAA, Wine
.venv/bin/python -m mohkit build maps/mk_village -q draft
open dist/mk_village_shots.png
.venv/bin/python -m mohkit install dist/mk_village.pk3   # then: g_gametype 1; map dm/mk_village
```

Requirements: a retail Allied Assault install (the compilers need its shader
scripts), OpenMoHAA for testing, Wine or CrossOver off Windows, Python ≥ 3.10.

CS:GO conversion (local use only, since it decodes Valve's textures):

```sh
.venv/bin/python -m mohkit csgo de_dust2 --name cs_dust2
```

## For AI agents

Read [CLAUDE.md](CLAUDE.md) (other agents: [AGENTS.md](AGENTS.md)).

## Legal

Map sources in `reference/` are EA's released SDK sources. The EA compilers are
downloaded separately, not stored here. Nothing derived from Valve content
(textures, models, converted BSPs) is committed. Converter output goes to
`local/` (gitignored) and is for personal use.
