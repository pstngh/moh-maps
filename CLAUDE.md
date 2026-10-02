# Working in moh-maps (instructions for coding agents)

**Goal.** Make any Medal of Honor: Allied Assault / OpenMoHAA multiplayer map
the user asks for, bug-free and looking like a finished stock map:

1. **Convert CS:GO maps** to MOHAA (`python -m mohkit csgo <map>`).
2. **Create maps from scratch**: invented by you, described in words, or
   recreated from a screenshot/photo the user sends.

Both have equal priority (the user, 2026-09-30).

Everything goes through `mohkit/`, a Python toolkit. **Do not write one-off
generators or format code. Extend mohkit instead.**

## How to work (the user's rules)

- **Keep going until the task is done or the user says stop.** Don't pause to
  ask what's next when the next step is clear; don't invent busywork either.
  When the work is done, stop and summarize: open with one plain line ("Done. Nothing is
  running; all pushed."). When a turn ends while builds run, open with "Not done: waiting
  on <builds>", each one's expected finish in US Eastern time, and whether the user must act.
- **A newly named priority comes after the work in progress**, not instead of it: finish or
  time-box the current item first, and keep HANDOFF's next steps an ordered queue that
  reaches past the current map.
- **Unattended runs** (the user says they're AFK, or authorizes a run until a set time):
  no 75% pause (auto-compaction is fine), no questions (log each judgement call under
  "Decisions made while the user was away" in HANDOFF.md), HANDOFF updated and pushed after
  every verified step, nothing irreversible, a long job always running in the background
  until the end time; then park, push and summarize at the top of HANDOFF.md. Write the
  run's rules into HANDOFF.md (it survives compaction) and delete them when the run ends:
  the 75% rule returns.
- **Other sessions and agents** may be working in this repo: at session start check
  `list_sessions` and `ps` (Q3map, MOHlight, openmohaa, mohkit) and say what runs;
  re-read HANDOFF.md at milestones; when chat and HANDOFF disagree, the newer instruction
  wins (note the conflict in HANDOFF).
- **Never let a script install over what the user plays.** Install a rebuilt map only after
  its sheet was compared with the installed build's on the same cameras (sky band
  included), and after the user's OK for look/fps variants.
- **`HANDOFF.md` is the continuity file**, injected automatically at every
  session start, clear and compaction by the hook in `.claude/settings.json`.
  Keep it current at each milestone: state, running processes, exact next
  steps.
- **Pause before the context fills.** Check `mcp__ccd_session_mgmt__get_usage`
  (context `percentUsed`; auto-compact starts near 97%) after each milestone.
  At **75%** or more:
  1. finish the current step;
  2. harvest the session's lessons into their permanent homes (see "The learning loop");
  3. update `HANDOFF.md`;
  4. commit and push to `main`;
  5. stop and give the user a one-line handoff to paste into a fresh chat
     ("Read CLAUDE.md and HANDOFF.md, then continue").
  Do the same whenever the user ends or moves work to a fresh session. Stop any Monitor or
  background watcher you started first. Never clear, schedule or relay sessions yourself:
  the user opens the fresh chat.
- **Git**: push small commits straight to `main` after tests pass. Never
  force-push or rewrite history without asking. Commit only your own paths (another agent
  may be writing in the same checkout).

## Environment (check first)

```sh
python -m mohkit doctor        # game dir, retail paks, EA tools, wine, OpenMoHAA, CS:GO
python -m mohkit setup         # fetch Q3map.exe/MOHlight.exe into .toolchain/ if missing
```

Use a Python with Pillow + numpy (on the owner's Mac: `~/Documents/moh-toolchain/venv/bin/python`;
no scipy). On macOS the EA compilers run under CrossOver Wine. System `git`/`clang` may be
blocked by an unaccepted Xcode license; dulwich works for git: `<venv python>
~/Documents/moh-toolchain/gitc.py commit "msg" <paths…>` (always pass paths: without them
it stages everything, once a background agent's half-written map), `status`, `log N`, and
`GH_TOKEN=$(gh auth token) <venv python> ~/Documents/moh-toolchain/gitc.py push main`.
dulwich's "Exception ignored … sys.meta_path is None" at exit is noise. Sources to cite:
OpenMoHAA `~/Documents/moh-toolchain/openmohaa-src` (engine.md paths are relative to its
`code/`), Source `~/source-engine/` (VRAD, VBSP, mathlib). The shell is zsh on macOS
(quote globs, no `timeout`): the traps are in docs/testing.md "Long builds, background
jobs and the shell".

## The loop (always close it)

1. **Author**: `python -m mohkit new <name>` scaffolds `maps/<name>/build.py`
   (a working yard + hall to replace). It defines `build()` → `MapBuilder`,
   plus `META` and `SHOTS`. Use the `Carver` for all playable space (sealed by
   construction), `kit` for stairs, windows, doors, roofs and lamps, and
   `MapBuilder.prop()` for stock props.
2. **Check**: `python -m mohkit generate maps/<name>` writes
   `maps/<name>/<name>.map` from `build.py`, validates it and draws the top-down
   plan `dist/<name>_plan.png` (seconds, no compile). Look at the plan.
3. **Build**: `python -m mohkit build maps/<name> -q draft`. This generates,
   validates, compiles, packages `dist/<name>.pk3`, runs OpenMoHAA with your
   `SHOTS`, and writes `dist/<name>_shots.png`.
4. **Look** at the contact sheet with the Read tool. Fix what you see and
   repeat. Judge lighting only on `-q preview` or `normal` builds (radiosity; preview is
   within 2.5% of normal).
5. **Play-test with bots**: `--bots 8 --seconds 90`, and check the kill count
   and log.

Never claim a map is finished from a compile alone. Screenshots and bots are
part of the definition of done. Human feedback outranks both.

## Rules that bite (each cost real time before)

- Compile only against the **retail paks** (the driver does this). Otherwise
  caulk and skies break into black holes.
- **Texture scale 1.0** is the MOHAA norm (not Quake's 0.5).
- **Max 64 vertices per face** after T-junction fixing, or the face renders as
  a checkerboard. Split long brushes at 512 (the Carver, `MapBuilder.box` and
  `kit.gable_roof` do). The compile's bsp-check reports offenders.
- No `func_detail` (it becomes an unlit, black game entity): use `+surfaceparm detail` (the default
  for `MapBuilder.box`/`prism`/`hull`).
- Props (`static_*`) have **no collision** unless the model ships a
  `models/<path>.map` (`mohkit.props.get(x).collision`). Add clip brushes
  otherwise. Pivots vary: check with `python -m mohkit.propview static/x`.
- Patch visible side = cross(row step, column step). Patch dims are `(rows cols)`, odd, ≤ 17.
- Cheat commands in tests need `cheats 1` **and** `thereisnomonkey 1`. `wait N`
  is milliseconds.
- `surfaceparm stone` does nothing; use `rock`.
- Lights: sun + cool sky fill + low ambient + fixtures. No fill lights on spawns.
- Bots need `sv_maxbots` > 0 before map load. They ignore doors, props without
  collision and crouch-only gaps.
- Keep the map within ±8192; ≤ 170 lightmap pages when MOHlight lights it (the renderer
  takes 256); ≤ 60 lights per leaf.
- Converted CS:GO content (textures, models, BSPs) is local-only: write it under
  `local/` (gitignored) and never commit it.
- Shell wait loops: `pgrep -f "pattern"` also matches the shell running the loop, so it
  never ends, and `pkill -f` kills your own loops. Wait on a marker line in a log, or a pid,
  in the background. Kill your leftover heredoc scripts (`python -`) by pid before timing
  anything.
- fps numbers only compare within one interleaved run (docs/testing.md "Frame rate"), and
  compile times only on an idle machine: concurrent builds slow each other ~2x.
- A build started before you edit mohkit runs the old code to the end: re-shoot or rebuild
  before judging the fix.
- The session scratchpad dies with the session: keep backups and logs a later session needs
  under `local/`, and turn any script used twice into mohkit code (scripts in gitignored
  `local/` are invisible to a fresh clone).

## Where knowledge lives

| need | read |
|---|---|
| start here / index | `docs/README.md` |
| a shot looks wrong: known symptoms, causes, fixes | `docs/symptoms.md` |
| design, dimensions, layout, budgets | `docs/design.md` |
| `build.py` API: MapBuilder, Carver, kit, material specs, side conventions | `docs/api.md` |
| `.map` syntax, texture projection, patches, terrain | `docs/map-format.md` |
| compiling, flags, error messages | `docs/toolchain.md` |
| entities, props, doors, ladders | `docs/entities.md` |
| lighting recipes | `docs/lighting.md` |
| textures, tool shaders, custom shaders | `docs/materials.md` + `docs/reference/materials.md` |
| scripts, precache, loading screens | `docs/scripting.md` |
| automated screenshots and bots | `docs/testing.md` |
| CS:GO conversion | `docs/csgo-conversion.md` |
| recreating a screenshot/photo | `docs/from-reference.md` (`mohkit.camera`, `looks-like`, `swatches`, `compare`) |
| engine facts with source citations | `docs/reference/engine.md` |
| stock data (materials, entities, props, lighting) | `data/*.json` (regenerate: `python -m mohkit.catalog`) |
| real examples | `reference/aa/*.map` (mohdm1–3, 5–7, obj_team1–4; no mohdm4), `reference/sh`, `reference/bt`; `maps/mk_village/build.py`; `maps/mk_ref_room/build.py` (from a screenshot) |

## The learning loop (the point of this repo)

The repo must get better with every map until it can one-shot any map: a CS:GO conversion,
a description, a photo. Agents don't remember between sessions; only what is written down
or coded survives. So **everything learned is made permanent, at the moment it is learned**,
not only bugs: a calibration or threshold that worked, a technique, an engine or tool fact,
a look that was wrong against the reference and what fixed it, an approach that was tried
and failed (with the numbers, so nobody tries it blind again), a user preference.

Where each lesson goes, strongest first:

1. **Code**: a better default, a converter/kit feature, a `validate` or compile check, a
   test. The tool then does it right without anyone remembering. Prefer this.
2. **The topic doc** (table above), with evidence: a source line, a binary string, an
   in-game test, before/after numbers. Include "tried and rejected" results there too.
3. **`docs/symptoms.md`** for anything that looked or played wrong in a build: what it
   looked like, cause, fix, guard (none yet = a guard is worth writing).
4. **Memory** (`~/.claude/.../memory/`) only for facts about the user: preferences, how
   they decide.

`HANDOFF.md` is in-flight state (what runs, what's next), not knowledge: anything durable
in it moves to 1-3 before the session ends (the harvest step in "Pause before the context
fills"). A lesson left only in HANDOFF, a commit message or the chat is lost.
Enforced by hooks in `.claude/settings.json`: the session-start output ends with this rule,
and `.claude/hooks/learning_loop_stop.sh` blocks a turn that hands the session off once,
until the harvest is done or confirmed.

A claim without evidence is marked **UNVERIFIED** until a test settles it (then the wording
goes in the same commit), or it is deleted: of 8 claims inherited from the pre-restart
attempt, 3 were false. Two checks of the whole system: (1) a fresh subagent with no session
context builds a new map from CLAUDE.md and docs/ alone (writing only in its own map folder)
and lists every gap, wrong claim and toolkit bug it hit; the first run (mk_medina,
2026-09-30) found 12, all fixed the same day. Repeat after big doc changes. (2) A history
harvest: the raw session transcripts are
`~/.claude/projects/-Users-pstn-Documents-moh-maps/*.jsonl` (desktop-app sessions are not
swept by `cleanupPeriodDays`; deleting a session deletes its transcript; copies up to
2026-10-02 in `~/Library/Caches/mohkit/transcripts-backup/`). The 2026-10-02 harvest
condensed each to user messages, agent text and clipped tool calls (`python -m
mohkit.harvest <jsonl…> --git . -o <dir>`, which also writes the commit log and the
HANDOFF.md history), had one subagent per file list candidate lessons checked against the
repo, then wrote the new ones down.

## Repo layout

```text
mohkit/            toolkit (mapfile, geom, build, kit, compile, game, bsp, pak, shaders, props, validate, render, catalog, source/)
maps/<name>/       map projects (build.py or <name>.map, assets/, README.md)
reference/         stock EA .map sources (aa, sh, bt) + community maps; read-only
data/              generated catalogs of stock materials/entities/props/lighting
docs/              knowledge base
tests/             python tests/test_*.py (plain asserts; run as scripts)
local/             (ignored) CS:GO conversions and anything derived from commercial assets
dist/ .toolchain/  (ignored) packages + contact sheets, EA tools; compile roots and test homes live in the user cache dir
```

## Conventions

- Python 3.10+, typed dataclasses, stdlib-first (Pillow/numpy where needed).
- Tests: `python tests/test_<x>.py`. Keep them fast; skip when game data is missing. A
  regression test counts only if it fails on the code before the fix (testing.md "Long
  builds, background jobs and the shell" has the recipe).
- Deterministic outputs (same inputs → identical `.map` and `.pk3` bytes).
- Commits: small and descriptive. Never commit `dist/`, `local/`,
  `.toolchain/` or retail/Valve files.
