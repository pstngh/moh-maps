# V2 Facility: East Annex

`codex_obj_team2_expanded` is the original Allied Assault `obj_team2` with a new playable east service compound. Revision 2 supersedes the visually rejected first pass: the original Objective map remains intact, while the annex is now a finished set of connected spaces rather than a sparse platform/facade.

The stock Objective scripts, 23 rotating doors, 88 targetnamed entities, and 16 Allied plus 16 Axis starts are retained. The addition has two broad connections, a raised yard, three-bay maintenance hall, internal stair/mezzanine, solid loading canopy, south and north two-bay service sheds, roof equipment, structural framing, utilities, cover, grounded props, 12 light groups, and eight neutral DM starts.

## Install and play

Copy `codex_obj_team2_expanded.pk3` into `main`, then use Objective mode:

```text
g_gametype 4
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

For bot-combat topology testing, the same BSP can run as FFA:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

The three-entry package contains only the BSP and two thin wrapper scripts. It executes the retail `obj_team2` scripts and resolves every material/model from stock AA data; no retail or custom asset bytes are redistributed.

## Revision 2 changes

- Increased the addition from 102 to 156 brushes and from 35 to 53 entities.
- Added complete north/south service sheds, facade awnings, ceiling ribs, roof vents, a dispatch island, utilities, bollards, crates, four more lighting groups, and two more neutral bot starts.
- Assigned a solid visible stock material to all six faces of all 156 added brushes.
- Removed `common/caulk`, `common/nodraw`, and both alpha `deckgrate` materials from added construction.
- Added mandatory stock-side cameras matching the human-reported failure angle.
- Retained the same two 288-unit connectors and the exact original Objective/door/target/team-spawn preservation policy.

The source validator strips the marked expansion ranges and requires byte-for-byte equality with the original source minus exactly nine documented untargeted foliage entities and five untargeted connector boundary entities.

## Validated revision 2

- Source: `aa/obj_team2.map`, 5,478,775 bytes; unchanged.
- Generated MAP: 5,585,462 bytes; 156 added brushes and 53 added entities.
- BSP 19: 19,053 surfaces, 63 lightmap pages, 58,528 visibility bytes.
- Compile: zero leaks, zero degenerate geometry, zero light clamps, and zero light hash warnings.
- Warnings: 136 classified stock/helper notices; revision 2's four additional corona groups account for the four-warning increase over revision 1.
- Visual QA: 14 exact-candidate screenshots including the reported stock-side angle; zero script errors.
- Objective QA: Recast 2.065 s, all 8 bots admitted, combat observed, and zero candidate diagnostics.
- FFA QA: Recast 2.091 s, all 8 bots admitted, 2 combat events in 45 s, and zero candidate diagnostics.

Rebuild from the repository root with:

```powershell
.\tools\build_stock_mirror.ps1 -GeneratedRoot generated\codex_obj_team2_expanded -Threads 4
```

## Artifact hashes

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,585,462 | `398f42625ea2970fbca01607c9c72ebf05465ec003fb6abdecf6214b42b231fc` |
| BSP | 13,000,688 | `48d0a46bee62f51db8164641bcc99fb26ddf5d005cce808673fe6a3e00811ba0` |
| PK3 | 2,317,942 | `b7c55baf2002aee31c8c53c322ba3289779f55053afc6bf69ce9ae7630a2a19e` |

## Known debt

Revision 1 failed human visual acceptance and is retained only as regression evidence. Revision 2 fixes the reported face/material cause and is visibly fuller in the exact outside-angle capture, but human re-testing remains authoritative. Please verify the same location in your renderer, walk both sheds and the hall/mezzanine routes, exercise the original doors/objective sequence, and judge the Axis-side annex balance. The annex adds combat space rather than another objective.
