#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function fail(message) {
  throw new Error(message);
}

function parseArguments(argv) {
  const options = {
    name: "control_displays",
    // MAP model keys are relative to the implicit "models/" root.
    model: "codex_nuke/source2/control_displays/control_displays.tik",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const take = () => {
      index += 1;
      if (index >= argv.length) fail(`Missing value after ${token}`);
      return argv[index];
    };
    if (token === "--output" || token === "-o") options.output = take();
    else if (token === "--name") options.name = take();
    else if (token === "--model") options.model = take();
    else if (token === "--manifest") options.manifest = take();
    else fail(`Unknown option: ${token}`);
  }
  if (!options.output) fail("--output is required");
  return options;
}

function point(values) {
  return `( ${values.map((value) => Math.round(value)).join(" ")} )`;
}

function face(points, texture, detail = false) {
  return `${points.map(point).join(" ")} ${texture} 0 0 0 0.5 0.5 0 32768 0${
    detail ? " +surfaceparm detail" : ""
  }`;
}

function box(minimum, maximum, texture, detail = false) {
  const [minX, minY, minZ] = minimum;
  const [maxX, maxY, maxZ] = maximum;
  return [
    "{",
    face([[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]], texture, detail),
    face([[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]], texture, detail),
    face([[16, minY, -16], [0, minY, 0], [16, minY, 16]], texture, detail),
    face([[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]], texture, detail),
    face([[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]], texture, detail),
    face([[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]], texture, detail),
    "}",
  ].join("\n");
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  let models = [{ name: options.name, model: options.model }];
  if (options.manifest) {
    const manifest = JSON.parse(fs.readFileSync(path.resolve(options.manifest), "utf8"));
    if (!Array.isArray(manifest.assets) || !manifest.assets.length) {
      fail("--manifest contains no model assets");
    }
    models = manifest.assets.map((asset) => ({
      name: String(asset.id || ""),
      model: String(asset.tiki || "")
        .replace(/\\/g, "/")
        .replace(/^models\//i, ""),
      compileMode: String(asset.compileMode || "static"),
      origin: Array.isArray(asset.origin) ? asset.origin.map(Number) : [0, 0, 0],
    }));
  }
  for (const model of models) {
    if (
      !/^[a-z0-9_]+$/.test(model.name) ||
      !/^codex_nuke\/source2\/[a-z0-9_./-]+\.tik$/i.test(model.model) ||
      model.model.split("/").includes("..") ||
      !["static", "runtime"].includes(model.compileMode || "static") ||
      !Array.isArray(model.origin || [0, 0, 0]) ||
      (model.origin || [0, 0, 0]).length !== 3 ||
      (model.origin || [0, 0, 0]).some((value) => !Number.isFinite(value))
    ) {
      fail(`Invalid probe model record: ${JSON.stringify(model)}`);
    }
  }
  const texture = "codex_nuke/concrete_floor";
  const brushes = [
    box([-768, -1024, -736], [1536, 768, -704], texture),
    box([-800, -1056, -736], [-768, 800, -128], texture),
    box([1536, -1056, -736], [1568, 800, -128], texture),
    box([-768, -1056, -736], [1536, -1024, -128], texture),
    box([-768, 768, -736], [1536, 800, -128], texture),
    box([-768, -1024, -160], [1536, 768, -128], texture),
  ];
  const modelEntities = models.flatMap((model) => [
    "{",
    `"classname" "${
      (model.compileMode || "static") === "runtime"
        ? "script_model"
        : `static_codex_nuke_${model.name}`
    }"`,
    `"model" "${model.model}"`,
    ...((model.compileMode || "static") === "runtime"
      ? ['"testanim" "idle"']
      : []),
    `"origin" "${(model.origin || [0, 0, 0]).join(" ")}"`,
    '"angles" "0 0 0"',
    '"scale" "1"',
    '"angle" "0"',
    "}",
  ]);
  const map = [
    "// Deterministic isolated proof for locally converted MOHAA static models.",
    "// Valve-derived model outputs are not part of this source file.",
    "{",
    '"classname" "worldspawn"',
    '"message" "CS2 to MOHAA static model proof"',
    '"ambientlight" "24 24 24"',
    ...brushes,
    "}",
    ...modelEntities,
    "{",
    '"classname" "light"',
    '"origin" "256 -128 -256"',
    '"light" "900"',
    '"_color" "1 0.95 0.88"',
    "}",
    "{",
    '"classname" "info_player_deathmatch"',
    '"origin" "256 -800 -656"',
    '"angle" "90"',
    "}",
    "",
  ].join("\n");
  const output = path.resolve(options.output);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, map);
  process.stdout.write(`Wrote ${output} (${Buffer.byteLength(map)} bytes)\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`ERROR: ${error.message}\n`);
  process.exitCode = 1;
}
