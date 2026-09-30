# mk_village: Village Crossroads

A Normandy crossroads for DM/TDM (8–24 players), generated entirely by
[`build.py`](build.py) with mohkit. It's the reference example for original maps.

- Cobbled square with a fountain, surrounded by streets on all four sides;
  lanes and a west passage make several loops.
- Enterable buildings:
  - a **town hall** (two floors, stairwell, upper windows over the square and
    the east street);
  - a **house** (three doors, beams, wine casks);
  - a **warehouse** (crates, three doors).
- Facades with stone base course, plaster, brick or half-timbered upper
  storeys, window niches with shutters, mouldings, and gable roofs with overhang
  on every block.
- Stock props with collision (produce cart, wagon, wine casks, crates, sandbags,
  bushes), hanging lamps indoors, bracket lanterns outside.
- Afternoon sun with a cool sky fill (`sky/mohday2`), light fog.
- 24 DM spawns and 24 team spawns (allied south-west, axis north-east).

```sh
python -m mohkit build maps/mk_village -q normal --bots 8 --seconds 60
python -m mohkit install dist/mk_village.pk3      # in game: g_gametype 1; map dm/mk_village
```

Uses only retail Allied Assault assets; the package contains just the BSP and
scripts.
