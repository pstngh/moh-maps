const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const result = {};
  for (let index = 2; index < argv.length; index++) {
    const key = argv[index];
    if (!key.startsWith("--")) continue;
    result[key.slice(2)] = argv[++index];
  }
  return result;
}

function sha256(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

const args = parseArgs(process.argv);
for (const required of ["audit", "vmf", "bsp", "vpk", "out"]) {
  if (!args[required]) {
    throw new Error(
      "Usage: node build_inferno_model_bounds.js --audit <full-audit.json> " +
        "--vmf <de_inferno_d.vmf> --bsp <de_inferno.bsp> " +
        "--vpk <pak01_dir.vpk> --out <inferno-model-bounds.json>"
    );
  }
}

const auditPath = path.resolve(args.audit);
const inputs = {
  vmf: path.resolve(args.vmf),
  bsp: path.resolve(args.bsp),
  vpkDirectory: path.resolve(args.vpk),
};
const audit = JSON.parse(fs.readFileSync(auditPath, "utf8"));
const models = audit.models.audit
  .filter((record) => record.header)
  .map((record) => ({
    model: record.model,
    references: record.references,
    hullMin: record.header.hullMin,
    hullMax: record.header.hullMax,
    mdlVersion: record.header.version,
    source: record.presentInBspPak ? "bsp-pak" : "vpk",
  }));

if (models.length !== audit.models.parsedHeaders || models.length !== 308) {
  throw new Error(
    `Expected all 308 model headers; audit=${audit.models.parsedHeaders}, emitted=${models.length}`
  );
}

const manifest = {
  formatVersion: 1,
  purpose:
    "Reference-only Source MDL hull metadata for measured AA-native substitutes; contains no model bytes.",
  method:
    "IDST v49 header hullMin/hullMax parsed with the proven Source VPK/BSP-pak audit.",
  source: Object.fromEntries(
    Object.entries(inputs).map(([key, filePath]) => [
      key,
      {
        file: path.basename(filePath),
        bytes: fs.statSync(filePath).size,
        sha256: sha256(filePath),
      },
    ])
  ),
  modelReferences: audit.models.references,
  uniqueModels: audit.models.unique,
  parsedHeaders: models.length,
  models,
};

const outputPath = path.resolve(args.out);
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(
  `${JSON.stringify({ output: outputPath, bytes: fs.statSync(outputPath).size, models: models.length }, null, 2)}\n`
);