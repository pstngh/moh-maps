# MOHAA map-building project charter

Goal version: 1

Canonical repository: https://github.com/pstngh/moh-maps

## Mission

Build compiled, installable, playable Medal of Honor: Allied Assault and
OpenMoHAA maps with editable, reproducible source. Prioritize DM/TDM layouts
that support enjoyable close- and medium-range OpenMoHAA bot combat without
excessively narrow routes.

Maps may use modern, clean, industrial, urban, or Counter-Strike-inspired
aesthetics and need not look WWII-themed. Reuse stock AA assets when visually
appropriate, and create original game-ready textures when stock art is
inadequate. Graffiti, warning signs, tiny decals, and similar cosmetics are low
priority unless they materially improve recognition or navigation. Prefer CS2
references over CS:GO references when both exist.

No map must imitate V2, `obj_team2`, or any earlier generated example. Treat
Valve assets available locally as private reference evidence only; do not
commit or redistribute proprietary Valve textures, models, VMFs, or other
copyrighted content without confirmed permission.

Full-resolution in-game screenshots and human playtesting outrank automated
visual claims. No generated map becomes an accepted baseline without explicit
user approval of that tested revision.

Commit and push every intentional validated change unless the user explicitly
directs otherwise.

## Goal control

Keep this stable mission separate from the mutable checkpoint in
`PROJECT_STATE.json`. A material mission change requires explicit user approval,
an incremented `goal_version`, an entry in `DECISIONS.md`, and coordinated
updates to both files.
