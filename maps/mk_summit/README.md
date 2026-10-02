# mk_summit: Summit

A replica of **Summit** from *Call of Duty: Black Ops* (2010) for MOHAA / OpenMoHAA DM and
TDM: a Soviet listening post on a snowy mountain top with sheer drops on every side. It uses
only retail Allied Assault assets (the Norway mission's snow, concrete and control panels);
no Call of Duty files are in the map or the repo.

The layout is traced from the Black Ops minimap at 12 units per minimap pixel (CoD scale
times 1.3, the MOHAA/CoD player-height ratio), so routes and distances match the original.
Interiors and floor levels are reconstructed from a handful of screenshots and may differ.

- North yard: radio building, radar dome tower, a ledge behind the building.
- B row: barracks, the alley, the red garage with a truck; the cable-car station on the west
  edge with the gondola hanging over the drop.
- Control building: a two-storey hall with galleries, consoles under a glass skylight,
  window corridors on the west (cliff path) and east (catwalk) sides.
- West cliff path round the control building; south yard with the crane truck, the "2"
  garage, a generator shed; the guardhouse and the south plaza where the road arrives.

Axis spawn in the north, Allies in the south; DM spawns cover the whole map. Falling off
the plateau is fatal.

```sh
python -m mohkit generate maps/mk_summit     # .map, plan, and the plan over the minimap if local/summit_ref/ exists
python -m mohkit build maps/mk_summit -q normal --bots 8 --seconds 90
```
