# V2 Facility: East Annex

`codex_obj_team2_expanded` is the original Allied Assault `obj_team2` with a new playable service annex built into its wooded eastern edge. The stock map, objective scripts, 23 rotating doors, 88 targetnamed entities, and 16 Allied plus 16 Axis starts are retained. The addition supplies more close-range combat space without replacing the familiar V2 facility.

The annex consists of a raised concrete service yard, two broad connections to the original grounds, three permanently open maintenance bays, an internal stair and mezzanine, a loading canopy, grounded stock props, cover, and eight caged-lamp lighting groups. Six neutral deathmatch starts make the added space useful for bot FFA while leaving team-start balance unchanged.

## Install and play

Copy `codex_obj_team2_expanded.pk3` into `main`, then use the normal Objective mode:

```text
g_gametype 4
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

For a bot-combat topology test, the same BSP can run as FFA:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

The three-entry package contains only the BSP and two thin wrapper scripts. It executes the retail `obj_team2` scripts and resolves every material/model from stock AA data; no retail or custom asset bytes are redistributed.

## What changed

- Added 102 brushes and 35 entities in the east-annex footprint.
- Added two 288-unit-wide, stepped connections and three permanently open hall bays.
- Added six supported neutral DM starts, eight lights, stock caged lamps/coronas, an Opel truck, crates, and structural dressing.
- Removed nine untargeted foliage entities occupying the annex footprint.
- Removed five untargeted fence/wire detail entities that physically blocked the two new connections.
- Preserved the original objective/target graph, 23 doors, and all Allied/Axis starts.

The source validator removes the marked expansion blocks and requires byte-for-byte equality with the original source minus exactly those 14 documented untargeted decorative entities.

## Validated revision 1

- Source: `aa/obj_team2.map`, 5,478,775 bytes; the source file is unchanged.
- Generated MAP: 5,544,555 bytes; 102 added brushes, 35 added entities.
- BSP 19: 18,735 surfaces, 62 lightmap pages, 47,448 visibility bytes.
- Compile: no leaks, no degenerate geometry, no light clamps, and no light hash warnings.
- Warnings: 132, consisting of the stock-source warning classes plus exactly eight optional corona-helper notices from the new lamps.
- Objective QA: exact Pak0-Pak6-plus-candidate root, Recast 1.957 s, all 8 bots admitted, zero candidate diagnostics.
- FFA QA: Recast 1.973 s, all 8 bots admitted, 4 combat events in 45 s, zero candidate diagnostics.
- Visual QA: 10 fixed player-height/overview views, 10 screenshots/markers, and zero script errors.

Rebuild from the repository root with:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_obj_team2_expanded -Threads 4
```

The configuration invokes the map-specific generator/validator and the common stock-derived build, inspection, and deterministic packaging pipeline.

## Artifact hashes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,544,555 | `3a7fd859484b6392a54812f21eb12155ad624a56f77e202ad32ad0cf749148ce` |
| BSP | 12,779,232 | `7d01a19b7354278a990d940528d4666c52ced196c788a3648589feb22c9b1239` |
| PK3 | 2,280,274 | `f7aa8769474666a16d588280c44a025b811af14dc2374993d917f59e6fca6ea7` |

## Known debt

This is an automated release candidate, not a claim of perfect human play. The Objective run inherits the same five retail `global/obj_dm.scr` errors as stock `obj_team2`; the optional FFA exercise inherits seven. Human play must still verify every original door and end-to-end objective completion, judge the annex's Axis-side proximity and route feel, and report any view not represented by the fixed-camera sheet. The annex intentionally adds combat space rather than another objective.
