# Reference data

| file | what | how it's made |
|---|---|---|
| [engine.md](engine.md) | engine and tool facts with source citations: movement numbers, camera and cheat commands, bots, map loading, worldspawn keys, entities, compiler options, BSP v19 structures, terrain | researched from the OpenMoHAA source, EA compiler binaries, retail paks and stock maps |
| [materials.md](materials.md) | every material used by the stock maps: size, typical scale, floor/wall/ceiling use, footstep material, maps | `python -m mohkit.catalog` |
| [entities.md](entities.md) | every classname and key used by the stock maps, grouped by purpose | `python -m mohkit.catalog` |

Machine-readable versions are in `../../data/`:

- `materials.json`
- `entities.json`
- `static_models.json`: every prop with QUAKED classname, bounds, and collision-map
  flag and box.
- `worldspawn.json`: per-map worldspawn keys and light statistics.
- `palettes.json`: the top materials of each MP map.

Regenerate with `python -m mohkit.catalog --out data/`. It needs the retail
paks and takes about 30 s.
