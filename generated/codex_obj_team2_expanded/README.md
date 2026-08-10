# V2 Facility: Expanded Complex

> **Current status: REJECTED.** A later human screenshot and explicit user
> rejection supersede revision 4's automated visual conclusions. The screenshot
> showed huge beige voids, disconnected-looking terrain/map islands, crude
> elevated causeway/slab construction, unfinished visible boundaries, and a
> result far below acceptable mapping quality. Preserve this revision as a
> negative experiment; do not use it as a positive construction baseline.

Revision 4's compile, package, runtime, bot, and capture records below remain
historical technical evidence within their narrow scope. They do not prove the
route, causeway, facade, landscape, or boundaries are complete, coherent,
polished, release-ready, or accepted. See `REJECTIONS.md` and `REVISION-4.md`.

## Historical revision 4 intent

`codex_obj_team2_expanded` retained the original Allied Assault `obj_team2` map
and Objective graph while attempting to expand its east service complex and add
a forest-side combat loop from Allied spawn around the bunker into the rear/east
yards.

The generator removed 59 untargeted fence/wire/post entities, 33 cooperating
curb/rail/collision brushes including four playerclips, and 24 foliage entities.
It described a broad Allied court, transition, stepped forest route, ridge,
1,024-unit elevated causeway, return, and annex. The later human screenshot
disproved the inference that this inventory and the selected automated views
established a finished, spatially continuous result.

## Historical install and test commands

The package is retained for evidence, not recommended as an accepted map. Its
historical Objective test command was:

```text
g_gametype 4
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

The same BSP was also exercised as an FFA topology test:

```text
g_gametype 1
sv_maxbots 8
sv_numbots 8
map obj/codex_obj_team2_expanded
```

The deterministic three-entry package contains only the BSP and two wrapper
scripts, executes the retail `obj_team2` scripts, and references stock AA data.
That package boundary says nothing about visual acceptance.

## Narrowly supported technical observations

- Canonical source: `aa/obj_team2.map`, 5,478,775 bytes, unchanged.
- Generated MAP: 5,637,967 bytes; the revision-4 structural validator passed its
  own encoded rules.
- BSP19: 19,624 surfaces, 67 lightmap pages, 131,080 visibility bytes, and 35
  neutral deathmatch starts.
- Q3map/VIS/MOHlight completed in 119.793/0.398/320.630 seconds; `.prt` existed
  and `.lin` did not.
- Objective QA recorded Recast generation, eight admitted bots, and five combat
  events in 60 seconds with no candidate diagnostic.
- FFA QA recorded Recast generation, eight admitted bots, and four combat
  events in 60 seconds with no candidate diagnostic.
- The automated suite captured 28 selected frames with no visual-script error.
- Package inventory contained one BSP and two wrapper scripts.

These observations establish tool/runtime behavior only. The 28-view suite did
not cover or correctly judge the human failure domain, large-scale continuity,
elevated slab/causeway construction, beige voids, disconnected-looking islands,
or unfinished visible edges. Its earlier no-void/floating/finished implications
are `SUPERSEDED`.

## Artifact hashes

| Historical artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| MAP | 5,637,967 | `871719b096129a5db24e94b77f5c3ba980aacdd4a796fd2fa9d48f415f2a8070` |
| BSP | 13,873,788 | `140ee2bf482ca4f83f1ecea11aee9d79d377cdf2974111a190fe1a9c1b1792eb` |
| PK3 | 2,543,033 | `4b85f8ede35726bbb6ea5f6f71480e2b8a2b10e47930f490c7082156e2833918` |
| Automated contact sheet | 13,031,828 | `fe8d438940bdd655dbbed927a2d336b9975490cc498972ce322aed07a530df62` |

## Disposition

- Status: `rejected`.
- Accepted revision: none.
- User approval evidence: none.
- Required action: preserve the experiment and human rejection. Do not compile,
  package, repair, or reuse its construction until a new evidence-driven plan is
  explicitly selected.
