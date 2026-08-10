# Rejections and superseded claims

Human rejection overrides automated validation. Preserve rejected artifacts as
negative evidence; never use them as positive construction baselines without a
new cause-level audit.

## R-001 - `codex_reactor` revision 1

- Date recorded: 2026-08-09
- Status: REJECTED
- Authority: Explicit user feedback that the map was extremely buggy and a
  mess.
- Supersedes: Earlier compile, Recast, bot-combat, fixed-camera, no-void, and
  visual-pass implications of quality or readiness.
- Conclusion: Technical loadability did not establish coherent construction,
  polish, or human acceptance. Retain only as a negative case.

## R-002 - `codex_obj_team2_expanded` revision 4

- Date recorded: 2026-08-09
- Status: REJECTED
- Authority: Explicit user rejection and a later human screenshot.
- Human-visible defects: huge beige voids, disconnected-looking terrain and map
  islands, crude elevated causeway/slab construction, unfinished visible
  boundaries, and an overall visibly unfinished result.
- Why automated QA failed: the 28-view suite proved only that its scripted
  cameras captured selected frames without script errors. Its coverage and
  viewpoints did not expose or correctly judge the large-scale spatial
  continuity, elevated construction, newly visible map edges, and human failure
  angle. Surface counts, `.prt` without `.lin`, Recast, combat events, and
  captured screenshots could not establish visual coherence.
- Supersedes: Revision-4 documentation describing the route, causeway, facade,
  boundaries, or visual result as complete, finished, free of voids, visually
  accepted, polished, release-ready, or suitable as a positive baseline.
- Conclusion: Preserve revision 4 as an experiment and rejection case. Do not
  repair it during the bootstrap and do not use its generated construction as a
  template without fresh primary-evidence verification.

## Current non-acceptance constraints

- `codex_nuke` remains incomplete, empty in places, visually broken, and not
  accepted.
- `codex_inferno` revision 5 improved after direct source conversion but still
  has substantial missing content and is not accepted.
- `codex_cobblestone` revision 4 still has unresolved visual and structural
  defects and is not accepted.
- `codex_cache` has no explicit final acceptance.
- `codex_dust2_v2` received comparatively positive feedback but no explicit
  final approval.
- Mirror maps, arena experiments, V2 Depot, and other generated maps are not
  accepted merely because they compiled or lack recorded criticism.
- No current Codex-generated map is an accepted baseline.
