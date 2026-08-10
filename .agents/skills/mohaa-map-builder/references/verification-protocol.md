# Evidence and uncertainty protocol

## Labels

- `PROVEN`: Directly verified through authoritative source behavior and/or
  repeated controlled runtime evidence within the stated scope.
- `OBSERVED`: Seen in concrete evidence but not safe to generalize.
- `HYPOTHESIS`: Plausible and awaiting a controlled test.
- `OPEN`: Unresolved and unusable as a production rule.
- `REJECTED`: Contradicted by evidence or explicitly rejected by the user.
- `SUPERSEDED`: Replaced by newer, stronger evidence.

Compilation cannot promote an observation or hypothesis to proven visual or
gameplay quality. State the scope of every proof.

## Priority

1. Explicit current user requirements and approval or rejection.
2. Original source files and directly observed engine behavior.
3. Engine, editor, and compiler source code.
4. Controlled runtime and compile experiments.
5. Original reference screenshots and geometry.
6. Verified repository documentation.
7. Codex-generated artifacts.

Newer generated output is not automatically stronger evidence.

## Uncertainty procedure

1. Stop making assumptions about the uncertain decision.
2. State the exact question.
3. Inspect primary evidence such as original MOHAA maps/shaders/scripts/entities,
   local retail assets, OpenMoHAA source, NetRadiant Custom/MOHAA configuration,
   compiler source/logs/output, original reference geometry, or full-resolution
   in-game screenshots.
4. When practical, use one primary source plus an independent check.
5. Record exact paths, relevant lines/entities/coordinates/materials/images,
   result, label, confidence, and remaining uncertainty.
6. If evidence remains inconclusive, leave the question `OPEN` and ask the user.

## Claim review

For every meaningful use of accepted, final, complete, polished, release-ready,
proven, no-void, no-floating, visually complete, or ready-to-play language:

1. Identify the precise property claimed.
2. Identify evidence that actually tests that property and viewing domain.
3. Separate source, compile, package, runtime, bot, visual, gameplay, and human
   acceptance claims.
4. Downgrade unsupported language to the narrowest supported label.
5. Mark contradicted claims `SUPERSEDED` and record the stronger evidence.

Human rejection always overrides an earlier automated pass. Preserve the failed
experiment and explain why its validation surface missed the defect.

## Skill-improvement evidence

Do not convert one generated result into a universal skill rule. Classify a
lesson as map-specific, harness-specific, engine-specific, or reusable. Promote
reusable guidance only when authoritative source proves it or controlled
exact-hash runs repeat it within a stated scope. Add a regression test, validate
the complete skill, and forward-test a fresh agent on raw evidence without
supplying the expected diagnosis. A generated audit cannot certify itself, and
no skill improvement can supply human map acceptance.
