# Repository instructions for map work

This repository is a cumulative MOHAA/OpenMoHAA map-generation knowledge base.
Future map work must improve the system as well as the individual map.

## Required reading before changing a map

1. Read [`docs/README.md`](docs/README.md).
2. Read [`docs/MAP-GENERATION-PLAYBOOK.md`](docs/MAP-GENERATION-PLAYBOOK.md).
3. Read the target map's `generated/<map>/README.md`, when it exists.
4. Read the relevant case-study sections in
   [`docs/MOHAA-map-generation-notes.md`](docs/MOHAA-map-generation-notes.md).
5. Consult [`docs/STOCK-AA-ASSET-CATALOG.md`](docs/STOCK-AA-ASSET-CATALOG.md)
   before choosing textures or stock models.
6. Consult [`docs/MAP-SOURCE-FORMAT.md`](docs/MAP-SOURCE-FORMAT.md) for the
   measured `.map` grammar, flag decodes, and entity vocabulary of the
   retail AA/SH/BT sources before reading them for reference.

Do not begin by copying the most recent generator blindly. Identify which
rules are general, which are map-specific, and which remain experiments.

## Definition of complete

A playable-map change is not complete until all applicable items are true:

- editable source and generator changes are reproducible;
- Q3map BSP, VIS, and MOHlight stages succeed against real retail AA data;
- the exact packaged PK3 loads from an isolated OpenMoHAA home;
- multiplayer scripts and spawn classes are present;
- OpenMoHAA bots spawn, move, and fight on the exact package;
- representative exterior, interior, transition, long-sightline, and map-edge
  views have been inspected;
- known visual or gameplay debt is stated honestly;
- the map README and conversion report are current;
- new evidence is added to the research log;
- any confirmed reusable rule is promoted into the playbook;
- artifact sizes and SHA-256 hashes are recorded;
- changes are committed and pushed unless the user explicitly says not to.

Never describe a map as polished, complete, or ready to play based only on a
successful compile.

## Knowledge maintenance

Use [`docs/templates/MAP-REVISION-REPORT.md`](docs/templates/MAP-REVISION-REPORT.md)
for every material revision.

- Put normative production rules in the playbook.
- Put chronological evidence, experiments, measurements, and postmortems in
  the research log.
- Put map-specific status, installation, fingerprints, and remaining debt in
  the generated map's README.
- Put verified stock asset names and visual/use notes in the asset catalog.

If new evidence contradicts the playbook, update both documents in the same
change. Do not leave a known-bad rule as the primary instruction.

## Compatibility and content boundaries

- Target AA BSP version 19 and AA assets unless the user explicitly requests
  Spearhead or Breakthrough dependencies.
- Do not redistribute retail PK3 contents, Valve/CS textures, reference VMFs,
  or Source models.
- Stock AA asset references are allowed because the player supplies the retail
  data. New bundled art must be original or clearly redistributable.
- Prefer simple static collision for bots. Dynamic obstacles in primary routes
  require explicit testing.
