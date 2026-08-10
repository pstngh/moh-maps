# OpenMoHAA source guide

Use this guide to route runtime questions into the canonical OpenMoHAA source.
It is an index, not a substitute for reading the implementation at the pinned
revision.

## Inspected source

- Canonical repository: `https://github.com/openmoh/openmohaa`
- Inspected branch: `main`
- Inspected commit: `a2f340195975f4f042e28a60b62561dd9a0b2700`
- Local reference checkout:
  `C:/Users/plex/Documents/Codex/2026-07-24/pstngh-moh-maps-https-github-com/work/openmohaa`
- Inspection date: `2026-08-09` America/New_York (`2026-08-10` UTC)
- Verification: a fresh `git fetch origin main` left clean `main`, local HEAD,
  and `origin/main` at the inspected commit.

The canonical URL and commit are the durable locator. The local path is only a
convenience and may differ on another machine. Do not clone or vendor
OpenMoHAA inside this repository.

## Evidence rules

1. Start at the route below, then search and read the actual source at the
   inspected commit. If the route is insufficient, continue through callers,
   declarations, configuration, and compatibility branches; do not guess.
2. Record the canonical URL, exact commit, target variant, source paths,
   symbols, line anchors, conclusion, evidence label, confidence, and remaining
   uncertainty. Line numbers are commit-specific; symbols are the durable
   search anchors.
3. Distinguish AA (`TG_MOH`), Spearhead (`TG_MOHTA`), Breakthrough
   (`TG_MOHTT`), and OpenMoHAA-specific behavior. A branch for one target or
   protocol does not prove the others.
4. Treat source-derived conclusions as `PROVEN` only for the semantics that the
   inspected code establishes. Use `OBSERVED` for controlled runtime results,
   `HYPOTHESIS` for a proposed explanation, and `OPEN` when evidence is
   incomplete.
5. For important behavior conclusions, pair source inspection with a
   controlled runtime check when practical. Record the OpenMoHAA build or
   source commit, target game/protocol, map and asset revision, cvars/commands,
   console or log evidence, observed result, and negative control. If a runtime
   check is impractical, say so and do not imply that it occurred.
6. Existing repository documents, old Codex map behavior, generated reports,
   and prior console summaries are untrusted indexes until the specific claim
   is traced to primary source, original data, or a controlled runtime result.
   They are never proof of engine behavior by themselves.

## Verified routing index

Every entry below was inspected at commit
`a2f340195975f4f042e28a60b62561dd9a0b2700`.

| Question | Verified implementation route and symbol anchors | Inspected commit |
| --- | --- | --- |
| Entity classes, properties, solidity, model assignment, and general game behavior | `code/fgame/entity.cpp:1537`, `CLASS_DECLARATION(SimpleEntity, Entity, NULL)` and its event table; declarations in `code/fgame/entity.h`. Follow a concrete event from the class table into its `Entity::` handler and engine import calls. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Entity-string parsing, class resolution, map spawning, and spawn classes | `code/fgame/g_spawn.cpp:71` `SpawnArgs::Parse`, `:204` `SpawnArgs::getClassDef`, `:317` `SpawnArgs::Spawn`, `:337` `SpawnArgs::SpawnInternal`; `code/fgame/level.cpp:1123` `Level::SpawnEntities`; registrations in `code/fgame/playerstart.cpp:77,146,161,176,187` and `code/fgame/worldspawn.cpp:491`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Doors, movers, blocking, activation, locking, and brush motion | `code/fgame/mover.cpp:38` mover registration and `:123` `Mover::MoveTo`; `code/fgame/doors.cpp:287` `Door` event table, `:1297` `RotatingDoor`, `:1449` `SlidingDoor`, and `:1608` `ScriptDoor`; declarations in `code/fgame/mover.h` and `code/fgame/doors.h`. Check the exact registered classname and handler rather than inferring it from editor labels. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Script commands, events, dispatch, threads, and VM execution | `code/corepp/listener.h:251,301,505` for `EventDef`, `Event`, and `Listener`; `code/corepp/listener.cpp:3233` `Listener::PostEventInternal` and `:3373` `Listener::ProcessEvent`; `code/fgame/scriptmaster.cpp:627` `ScriptMaster::CreateThread` and `:648` `ExecuteThread`; `code/fgame/scriptthread.cpp:2125` event table; `code/script/scriptvm.cpp:1018` `ScriptVM::Execute`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Bot creation, removal, control loop, combat state, and generated commands | `code/fgame/g_bot.cpp:441` `G_AddBot` and `:538` `G_RemoveBot`; `code/fgame/playerbot.cpp:40` `BotController` registration, `:1210` `BotController::Think`, and `:1372` `BotControllerManager::ThinkControllers`; manager wiring in `code/fgame/playerbot_master.cpp:36,40,56`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Bot movement, path requests, jump checks, obstacle avoidance, and reachability | `code/fgame/playerbot_movement.cpp:58` `BotMovement::MoveThink`, `:307` `CheckJump`, `:517` `AvoidPath`, `:564` `MoveNear`, `:597` `MoveTo`, and `:988` `CanMoveTo`; path interface and parameters in `code/fgame/navigation_path.h:35,61,99`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Recast/Detour build inputs, agent configuration, nav-mesh construction, and map load | `code/fgame/navigation_recast_config.h:34-54` (`NavigationMapConfiguration`, walkable/busy flags); extension areas in `code/fgame/navigation_recast_config_ext.h:34-47`; `code/fgame/navigation_recast_load.cpp:180` `BuildDetourData`, `:415` `BuildRecastMesh`, `:645` `BuildWorldMesh`, `:670` `BuildMeshesForEntities`, and `:713` `LoadWorldMap`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Recast path queries, route restrictions, dynamic obstacles, route costs, and route visualization | `code/fgame/navigation_recast_path.cpp:71,95` `RecastPather::FindPath`/Detour `findPath`; `code/fgame/navigation_recast_load.cpp:130` excludes `RECAST_POLYFLAG_BUSY` and `:139` sets extension-area costs; `code/fgame/navigation_recast_obstacle.cpp:130,160` sets/clears busy flags; `code/fgame/navigation_recast_debug.cpp:205` routes `ai_showroutes`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Player and bot dimensions, stance bounds, step height, movement, and collision traces | Constants in `code/fgame/bg_public.h:38-44,190`; bounds selection in `code/fgame/bg_pmove.cpp:1016-1064`; `PmoveSingle` at `:1295` and `Pmove` at `:1514`; server setup in `code/fgame/player.cpp:3662`; trace implementation in `code/qcommon/cm_trace.c`. Verify the active stance and target variant before applying a dimension. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| BSP versions, lumps, collision loading, brushes, patches, terrain, and entity text | Format/version and lump routing in `code/qcommon/qfiles.h:358-364,472-521`; `code/qcommon/cm_load.c:828` `CM_LoadMap`, including version checks at `:895` and lump loads at `:903-995`; tracing in `code/qcommon/cm_trace.c`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Render-time BSP and surface loading in the two renderer paths | GL1: `code/renderergl1/tr_bsp.c:1596` `R_LoadSurfaces` and `:2244` `RE_LoadWorldMap`; GL2: `code/renderergl2/tr_bsp.c:1727` `R_LoadSurfaces` and `:3299` `RE_LoadWorldMap`. Follow the active renderer; do not transfer a renderer-specific conclusion without checking both paths. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Shader/material discovery, parsing, stages, registration, and fallback | GL1: `code/renderergl1/tr_shader.c:840` `ParseStage`, `:2220` `ParseShader`, `:3367` `R_FindShader`, `:3792` `ScanAndLoadShaderFiles`; GL2: `code/renderergl2/tr_shader.c:628` `ParseStage`, `:2363` `ParseShader`, `:4045` `R_FindShaderEx`, `:4459` `ScanAndLoadShaderFiles`, `:4690` `R_InitShaders`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Models, TIKI loading, model registration, surfaces, bounds, and failures | `code/tiki/tiki_cache.cpp:150` `TIKI_RegisterTikiFlags`, `:205` `TIKI_LoadTikiModel`, and `:220` `TIKI_RegisterTiki`; setup parsing in `code/tiki/tiki_parse.cpp:949` `TIKI_LoadSetup` and `:1006` `TIKI_ParseSetup`; renderer registration in both `code/renderergl1/tr_model.cpp:174,295` and `code/renderergl2/tr_model.cpp:174,295`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| Console output, developer diagnostics, runtime errors, spawn/script failures, and nav diagnostics | `code/qcommon/common.c:230` `Com_Printf`, `:376` `Com_DPrintf`, `:451` `Com_Error`, and `:268-360` `qconsole.log`; game wrappers in `code/fgame/g_main.cpp:93,110,377`; spawn failures in `code/fgame/g_spawn.cpp:386,885,949`; script status/errors in `code/fgame/scriptmaster.cpp:643,668,818,1162`; Recast output in `code/fgame/navigation_recast_load.cpp:718-792` and visualization in `code/fgame/navigation_recast_debug.cpp:205`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |
| AA, Spearhead, Breakthrough, demo/protocol, and BSP compatibility differences | Product/target/protocol definitions in `code/qcommon/q_shared.h:40-67,261-274`; target initialization in `code/qcommon/common.c:3164-3235`; AA versus SH/BT movement conversion in `code/qcommon/bg_compat.cpp:60,82,132-197`; BSP range and version-dependent lump routing in `code/qcommon/qfiles.h:361-364,518`. | `a2f340195975f4f042e28a60b62561dd9a0b2700` |

## Scope boundary

OpenMoHAA source can establish runtime semantics implemented at the inspected
commit: parsing, registration, movement, collision, loading, rendering paths,
navigation, diagnostics, and compatibility branches. It cannot prove good map
architecture, faithful geometry, visual quality, appropriate materials,
lighting quality, combat layout, enjoyment, or human acceptance.

Those questions still require the editable map and generator provenance, stock
examples or original reference data, NetRadiant and compiler behavior, retail
or redistributable assets, full-resolution screenshots, controlled playtests,
and explicit human review as applicable. A clean load, successful compile,
working script, traversable nav mesh, moving bot, or quiet console cannot
override a human-visible defect or rejection.
