# Compile, package, bot, and human validation

## Compile

1. Run BSP, VIS, and full MOHlight with the intended AA toolchain and retail
   data boundary.
2. Classify every warning from source/tool behavior or controlled comparison.
3. Require valid expected outputs; record hashes and tool versions when useful.
4. Treat compile success as a compile result only, never a visual verdict.

## Package and runtime

1. Build the exact reproducible PK3 and inspect every member/path.
2. Test it in an isolated OpenMoHAA home with no loose file or unrelated package
   masking omissions.
3. Hash the candidate before launch and every runtime copy after exit. Require
   exact equality; a report that repeats an input hash is not proof of loaded
   bytes. Correlate the packaged BSP member to the compiled BSP by inner hash.
4. Record the engine executable hash, arguments, paths, cvars, full log, and
   exact retail/candidate package inventory.
5. Verify scripts, spawn classes, game mode, and precache behavior.
6. Record runtime diagnostics and compare inherited stock behavior only from a
   controlled baseline.

## Bots and gameplay

- Observe spawning, movement, combat, death, and respawn as separate events.
- Establish that bots use multiple meaningful routes; Recast generation alone
  is insufficient.
- Require position instrumentation or controlled route probes for route claims.
  Bot entry, kill strings, and combat frequency do not prove mapwide movement or
  route diversity.
- Inspect route width, headroom, collision, stalls, and spawn safety.
- Test doors and dynamic obstacles directly. Keep primary bot routes independent
  of unverified dynamic behavior.
- Separate optional FFA navigation exercises from intended Objective rules,
  doors, targets, and completion.

## Human handoff and acceptance

State known debt and provide the exact tested package/revision. Record user
feedback and its evidence path or provenance. Only explicit approval of that
tested candidate permits:

- map status `accepted`;
- a non-null `accepted_revision`;
- promotion to `accepted_baseline`.

Do not infer approval from silence, successful technical gates, bot movement,
automated screenshots, lack of criticism, or mildly positive feedback. A later
human rejection supersedes automated conclusions and requires checkpoint,
rejection, and regression-evidence updates.

For autonomous runs and the exact evidence schema, read
[autonomous-evidence-loop.md](autonomous-evidence-loop.md).
