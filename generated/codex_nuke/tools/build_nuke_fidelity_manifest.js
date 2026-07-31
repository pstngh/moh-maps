const fs = require("fs");
const path = require("path");

const vmfPath = path.resolve(process.argv[2]);
const auditPath = path.resolve(
  process.argv[3] ||
    path.join(__dirname, "..", "reference-audit.json")
);
const outputPath = path.resolve(
  process.argv[4] ||
    path.join(__dirname, "..", "fidelity-manifest.json")
);

if (!process.argv[2]) {
  throw new Error(
    "Usage: node build_nuke_fidelity_manifest.js <de_nuke_d.vmf> [reference-audit.json] [fidelity-manifest.json]"
  );
}

function tokenize(text) {
  const tokens = [];
  let index = 0;
  while (index < text.length) {
    const char = text[index];
    if (/\s/.test(char)) {
      index++;
      continue;
    }
    if (char === "/" && text[index + 1] === "/") {
      index += 2;
      while (index < text.length && text[index] !== "\n") index++;
      continue;
    }
    if (char === "{" || char === "}") {
      tokens.push(char);
      index++;
      continue;
    }
    if (char === '"') {
      index++;
      let token = "";
      while (index < text.length) {
        const current = text[index++];
        if (current === "\\") {
          if (index < text.length) token += text[index++];
        } else if (current === '"') {
          break;
        } else {
          token += current;
        }
      }
      tokens.push(token);
      continue;
    }
    const start = index;
    while (
      index < text.length &&
      !/\s/.test(text[index]) &&
      text[index] !== "{" &&
      text[index] !== "}"
    ) {
      index++;
    }
    tokens.push(text.slice(start, index));
  }
  return tokens;
}

function parseEntries(tokens, state, stopAtBrace = false) {
  const entries = [];
  while (state.index < tokens.length) {
    const key = tokens[state.index++];
    if (key === "}") {
      if (!stopAtBrace) throw new Error("Unexpected closing brace");
      return entries;
    }
    const next = tokens[state.index++];
    if (next === "{") {
      entries.push({ key, children: parseEntries(tokens, state, true) });
    } else if (next === undefined || next === "}") {
      throw new Error(`Missing value for ${key}`);
    } else {
      entries.push({ key, value: next });
    }
  }
  if (stopAtBrace) throw new Error("Unexpected EOF inside block");
  return entries;
}

function children(entries, key) {
  return entries.filter((entry) => entry.key === key && entry.children);
}

function value(entries, key, fallback = "") {
  return (
    entries.find((entry) => entry.key === key && entry.value !== undefined)
      ?.value ?? fallback
  );
}

function keyValues(entries) {
  return Object.fromEntries(
    entries
      .filter((entry) => entry.value !== undefined)
      .map((entry) => [entry.key, entry.value])
  );
}

function parseVector(text) {
  return text
    .trim()
    .replace(/^[\[(]/, "")
    .replace(/[\])]$/, "")
    .trim()
    .split(/\s+/)
    .map(Number);
}

function inPlayableArea(origin) {
  return (
    origin[0] >= -6400 &&
    origin[0] <= 6720 &&
    origin[1] >= -5504 &&
    origin[1] <= 4608 &&
    origin[2] >= -1536 &&
    origin[2] <= 3584
  );
}

function classifyModel(model) {
  const rules = [
    ["autocombine", /\/autocombine\//],
    ["railing", /railing/],
    ["fence", /chainlink|fence/],
    ["ladder", /ladder/],
    ["pipe", /pipe|gas_meter/],
    ["ventilation", /vent|duct|roof_ac|roof_cap/],
    ["lighting", /light_fixture|light_pole|controlroom_light/],
    ["door", /door|floor_hatch/],
    ["window", /window/],
    ["crate_cover", /crate|container|barrier|bollard/],
    ["foliage", /foliage|weed|grass|tree|bush/],
    ["vehicle", /\/nuke_(?:cars|forklift|hand_truck)\/|nuke_truck/],
    ["office", /office|desk|chair|locker|bench|control_room/],
    ["industrial", /industrial|reactor|silo|tank|crane|transformer/],
    ["structure", /joist|column|beam|catwalk|stair|trim/],
    ["utility", /electric|power|current_transformer|recycling/],
    ["signage", /sign/],
  ];
  return rules.find(([, pattern]) => pattern.test(model))?.[0] || "other";
}

function increment(map, key) {
  map[key] = (map[key] || 0) + 1;
}

const audit = JSON.parse(fs.readFileSync(auditPath, "utf8"));
const headers = new Map(
  audit.models.audit
    .filter((record) => record.header)
    .map((record) => [record.model, record.header])
);
const root = parseEntries(tokenize(fs.readFileSync(vmfPath, "utf8")), {
  index: 0,
});
const instances = [];

for (const entity of children(root, "entity")) {
  const properties = keyValues(entity.children);
  const model = (properties.model || "")
    .toLowerCase()
    .replace(/\\/g, "/");
  if (!model.startsWith("models/")) continue;
  const origin = parseVector(properties.origin || "0 0 -9999");
  if (!inPlayableArea(origin)) continue;
  const angles = parseVector(properties.angles || "0 0 0");
  const header = headers.get(model) || null;
  instances.push({
    id: properties.id || "",
    classname: properties.classname || "",
    model,
    category: classifyModel(model),
    origin,
    angles,
    sourceSolid: properties.solid || "",
    skin: properties.skin || "",
    uniformscale: Number(properties.uniformscale || 1),
    measuredHull: header
      ? {
          min: header.hullMin,
          max: header.hullMax,
        }
      : null,
    source: model.includes("/autocombine/") ? "bsp-pak" : "vpk",
  });
}

const counts = {
  instances: instances.length,
  byCategory: {},
  byClass: {},
  byModel: {},
  embeddedAutocombines: instances.filter(
    (instance) => instance.category === "autocombine"
  ).length,
  measuredInstances: instances.filter((instance) => instance.measuredHull)
    .length,
};
for (const instance of instances) {
  increment(counts.byCategory, instance.category);
  increment(counts.byClass, instance.classname);
  increment(counts.byModel, instance.model);
}
counts.byCategory = Object.fromEntries(
  Object.entries(counts.byCategory).sort((left, right) => right[1] - left[1])
);
counts.byClass = Object.fromEntries(
  Object.entries(counts.byClass).sort((left, right) => right[1] - left[1])
);
counts.byModel = Object.fromEntries(
  Object.entries(counts.byModel).sort((left, right) => right[1] - left[1])
);

const manifest = {
  formatVersion: 1,
  policy: {
    derivedFactsOnly:
      "This file records model identifiers, transforms, and measured header bounds. It contains no Valve mesh, texture, or model payload.",
    use:
      "Treat bounds as envelopes. Reconstruct only family-specific primitives whose topology is independently understood.",
  },
  source: {
    vmfFile: path.basename(vmfPath),
    auditFile: path.basename(auditPath),
  },
  playableBounds: {
    min: [-6400, -5504, -1536],
    max: [6720, 4608, 3584],
  },
  counts,
  instances,
};

fs.writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(counts, null, 2)}\n`);
