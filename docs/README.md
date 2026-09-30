# Making MOHAA maps with mohkit

## Ten-minute start

```python
# maps/my_first/build.py
from mohkit.build import Carver, MapBuilder, Material as M
from mohkit import kit
from mohkit.game import Shot

META = {"name": "my_first", "title": "My First Map", "ambience": "mohdm2"}

FLOOR, WALL, STONE = M("central_europe/small_cobble"), M("general_structure/plaster_wall2"), M("general_structure/stonebricks1", (0.5, 0.5))

def build():
    b = MapBuilder("My First Map", suncolor="70 66 58", sundirection="315 210 0",
                   sundiffuse="1.2", sundiffusecolor="56 62 78", ambientlight="10 10 12")
    cv = Carver(16, sky_shader="sky/mohday2")
    b.carve(cv)
    yard = cv.room(-512, -512, 0, 512, 512, 256, floor=FLOOR, walls=[(0, STONE), (32, WALL)], sky=True)
    hall = cv.room(544, -128, 0, 1024, 128, 160, floor=M("general_structure/floor4"), walls=WALL,
                   ceiling=M("general_structure/plank_flat"))
    cv.room(512, -48, 0, 544, 48, 112, floor=STONE, walls=STONE, ceiling=STONE)      # doorway
    kit.window(cv, yard, "north", -64, 0, 64, 144, "general_structure/denmark_win2", (128, 180), STONE)
    kit.lamp(b, 784, 0, 160)
    b.prop("static/winecasks", 960, 90, 0, 180)
    for i, (x, y) in enumerate([(-400, -400), (400, 400), (-400, 400), (400, -400), (900, -80), (700, 80)]):
        b.spawn((x, y, 1), (i * 90 + 45) % 360)
    return b

SHOTS = [Shot.looking_at("yard", (-450, -450, 80), (300, 300, 60)),
         Shot.looking_at("hall", (580, -100, 80), (1000, 100, 40))]
```

```sh
python -m mohkit build maps/my_first -q draft     # validate → compile → package → screenshots
open dist/my_first_shots.png                    # look at it
python -m mohkit install dist/my_first.pk3        # then in game: g_gametype 1; map dm/my_first
```

## Guides

1. [toolchain.md](toolchain.md): setup, the compile pipeline, every compiler flag
   and error message.
2. [design.md](design.md): player dimensions, layout, the Carver
   construction method, what makes a map look like MOHAA, limits, bots.
3. [map-format.md](map-format.md): the `.map` text format (brushes, texture
   projection, patches, terrain).
4. [entities.md](entities.md): spawns, lights, props and collision, doors,
   ladders, triggers.
5. [materials.md](materials.md): stock textures, tool shaders, custom
   textures and shader scripts.
6. [lighting.md](lighting.md): sun, fill, ambient, fixtures; recipes from the
   stock maps.
7. [scripting.md](scripting.md): `.scr`, precache, objectives, loading
   screens.
8. [testing.md](testing.md): automated screenshots, bot matches, log triage.
9. [csgo-conversion.md](csgo-conversion.md): converting CS:GO maps.

## Reference

- [reference/engine.md](reference/engine.md): engine facts with OpenMoHAA
  source citations (movement, camera commands, bots, scripts, worldspawn keys,
  entities, compiler options, BSP v19 layout, terrain).
- [reference/materials.md](reference/materials.md) and
  [reference/entities.md](reference/entities.md): generated from the stock
  maps.
- `../data/*.json`: the same data, machine-readable (materials, entities,
  static models with bounds and collision, worldspawn lighting, palettes).
- `../reference/`: the stock EA `.map` sources, the best examples there are.

## mohkit modules

| module | what it does |
|---|---|
| `mapfile` | parse and write `.map` (brushes, patches, terrain) |
| `geom` | planes, windings, bounds |
| `build` | `MapBuilder`, `Carver`, brush constructors (`box`, `prism`, `hull`), materials |
| `kit` | stairs, ramps, window/door niches, texture fitting, trims, beams, columns, roofs, lamps |
| `props` | stock prop catalog (classname, bounds, collision) |
| `validate` | static checks before compiling |
| `compile` | run Q3map / VIS / MOHlight, parse output, BSP checks |
| `bsp` | read MOHAA BSP v19 (stats, shaders, surfaces, lightmaps, static models) |
| `pak`, `shaders` | retail PK3 file system, shader scripts |
| `project` | map projects: generate → validate → compile → package → test |
| `game` | run OpenMoHAA: screenshots, bots, log triage |
| `render` | top-down plan images |
| `propview` | render stock props in a test room |
| `catalog` | regenerate `data/` and `docs/reference/` from the stock maps |
| `source/` | CS:GO: VPK, VTF, VMT, BSP, MDL readers; converter |
