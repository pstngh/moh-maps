const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const argument = argv[i];
    if (!argument.startsWith("--")) {
      throw new Error(`Unexpected argument: ${argument}`);
    }
    const key = argument.slice(2);
    const value = argv[++i];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    args[key] = value;
  }
  return args;
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
      let value = "";
      while (index < text.length) {
        const current = text[index++];
        if (current === "\\") {
          if (index < text.length) value += text[index++];
        } else if (current === '"') {
          break;
        } else {
          value += current;
        }
      }
      tokens.push(value);
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
    if (key === "{") throw new Error("Unexpected opening brace");
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
  return entries.find(
    (entry) => entry.key === key && entry.value !== undefined
  )?.value ?? fallback;
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

function parsePlane(text) {
  const matches = [...text.matchAll(/\(([^)]+)\)/g)];
  if (matches.length !== 3) return [];
  return matches.flatMap((match) => [parseVector(match[1])]);
}

function increment(map, key, amount = 1) {
  map.set(key, (map.get(key) || 0) + amount);
}

function sortedObject(map) {
  return Object.fromEntries(
    [...map].sort((left, right) => {
      if (right[1] !== left[1]) return right[1] - left[1];
      return left[0].localeCompare(right[0]);
    })
  );
}

function boundsForPoints(points) {
  if (!points.length) return null;
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const point of points) {
    for (let axis = 0; axis < 3; axis++) {
      min[axis] = Math.min(min[axis], point[axis]);
      max[axis] = Math.max(max[axis], point[axis]);
    }
  }
  return { min, max };
}

function centerOfBounds(bounds) {
  return bounds.min.map((minimum, axis) => (minimum + bounds.max[axis]) / 2);
}

function expandBounds(bounds, margin) {
  return {
    min: bounds.min.map((coordinate, axis) => coordinate - margin[axis]),
    max: bounds.max.map((coordinate, axis) => coordinate + margin[axis]),
  };
}

function boundsIntersect(left, right) {
  return left.min.every(
    (minimum, axis) =>
      minimum <= right.max[axis] && left.max[axis] >= right.min[axis]
  );
}

function readNullTerminated(buffer, state) {
  const start = state.offset;
  while (state.offset < buffer.length && buffer[state.offset] !== 0) {
    state.offset++;
  }
  if (state.offset >= buffer.length) {
    throw new Error("Unexpected EOF in VPK directory string");
  }
  const result = buffer.toString("utf8", start, state.offset);
  state.offset++;
  return result;
}

function parseVpkDirectory(vpkPath) {
  const buffer = fs.readFileSync(vpkPath);
  const signature = buffer.readUInt32LE(0);
  if (signature !== 0x55aa1234) {
    throw new Error(`Not a Source VPK: signature 0x${signature.toString(16)}`);
  }
  const version = buffer.readUInt32LE(4);
  if (version !== 1 && version !== 2) {
    throw new Error(`Unsupported VPK version: ${version}`);
  }
  const treeSize = buffer.readUInt32LE(8);
  const headerSize = version === 2 ? 28 : 12;
  const state = { offset: headerSize };
  const treeEnd = headerSize + treeSize;
  const entries = new Map();

  while (state.offset < treeEnd) {
    const extension = readNullTerminated(buffer, state);
    if (!extension) break;
    while (state.offset < treeEnd) {
      const directory = readNullTerminated(buffer, state);
      if (!directory) break;
      while (state.offset < treeEnd) {
        const filename = readNullTerminated(buffer, state);
        if (!filename) break;
        if (state.offset + 18 > treeEnd) {
          throw new Error("Truncated VPK directory entry");
        }
        const crc = buffer.readUInt32LE(state.offset);
        const preloadBytes = buffer.readUInt16LE(state.offset + 4);
        const archiveIndex = buffer.readUInt16LE(state.offset + 6);
        const entryOffset = buffer.readUInt32LE(state.offset + 8);
        const entryLength = buffer.readUInt32LE(state.offset + 12);
        const terminator = buffer.readUInt16LE(state.offset + 16);
        state.offset += 18;
        if (terminator !== 0xffff) {
          throw new Error(
            `Invalid VPK entry terminator at offset ${state.offset - 2}`
          );
        }
        const preloadData = buffer.subarray(
          state.offset,
          state.offset + preloadBytes
        );
        state.offset += preloadBytes;
        const normalizedDirectory = directory === " " ? "" : `${directory}/`;
        const entryPath =
          `${normalizedDirectory}${filename}.${extension}`.toLowerCase();
        entries.set(entryPath, {
          path: entryPath,
          crc,
          preloadBytes,
          archiveIndex,
          entryOffset,
          entryLength,
          preloadData,
        });
      }
    }
  }

  if (state.offset > treeEnd) {
    throw new Error("VPK tree parser ran past the declared tree size");
  }

  function readEntry(entryPath, maximumBytes = Infinity) {
    const entry = entries.get(entryPath.toLowerCase());
    if (!entry) return null;
    const preloadData = entry.preloadData.subarray(
      0,
      Math.min(entry.preloadData.length, maximumBytes)
    );
    const remainingBytes = Math.max(0, maximumBytes - preloadData.length);
    let archiveData = Buffer.alloc(0);
    const archiveBytes = Math.min(entry.entryLength, remainingBytes);
    if (archiveBytes) {
      if (entry.archiveIndex === 0x7fff) {
        const offset = headerSize + treeSize + entry.entryOffset;
        archiveData = buffer.subarray(offset, offset + archiveBytes);
      } else {
        const archivePath = vpkPath.replace(
          /_dir\.vpk$/i,
          `_${String(entry.archiveIndex).padStart(3, "0")}.vpk`
        );
        const file = fs.openSync(archivePath, "r");
        try {
          archiveData = Buffer.alloc(archiveBytes);
          fs.readSync(
            file,
            archiveData,
            0,
            archiveBytes,
            entry.entryOffset
          );
        } finally {
          fs.closeSync(file);
        }
      }
    }
    return Buffer.concat([preloadData, archiveData]);
  }

  return {
    signature: `0x${signature.toString(16)}`,
    version,
    treeSize,
    fileDataSectionSize: version === 2 ? buffer.readUInt32LE(12) : null,
    archiveMd5SectionSize: version === 2 ? buffer.readUInt32LE(16) : null,
    otherMd5SectionSize: version === 2 ? buffer.readUInt32LE(20) : null,
    signatureSectionSize: version === 2 ? buffer.readUInt32LE(24) : null,
    entries,
    readEntry,
  };
}

function parseSourceBspPak(bspPath) {
  const file = fs.openSync(bspPath, "r");
  let header;
  try {
    header = Buffer.alloc(8 + 64 * 16 + 4);
    fs.readSync(file, header, 0, header.length, 0);
  } finally {
    fs.closeSync(file);
  }
  if (header.toString("ascii", 0, 4) !== "VBSP") {
    throw new Error("Not a Source BSP: missing VBSP identifier");
  }
  const version = header.readInt32LE(4);
  const pakLumpOffset = 8 + 40 * 16;
  const pakOffset = header.readInt32LE(pakLumpOffset);
  const pakLength = header.readInt32LE(pakLumpOffset + 4);
  if (pakOffset < 0 || pakLength <= 0) {
    throw new Error("Source BSP has no embedded pakfile lump");
  }
  const bspFile = fs.openSync(bspPath, "r");
  let pak;
  try {
    pak = Buffer.alloc(pakLength);
    fs.readSync(bspFile, pak, 0, pakLength, pakOffset);
  } finally {
    fs.closeSync(bspFile);
  }

  let eocdOffset = -1;
  const minimumEocdOffset = Math.max(0, pak.length - 0xffff - 22);
  for (let offset = pak.length - 22; offset >= minimumEocdOffset; offset--) {
    if (pak.readUInt32LE(offset) === 0x06054b50) {
      eocdOffset = offset;
      break;
    }
  }
  if (eocdOffset < 0) {
    throw new Error("Embedded pakfile is not a readable ZIP archive");
  }
  const entryCount = pak.readUInt16LE(eocdOffset + 10);
  const centralDirectoryOffset = pak.readUInt32LE(eocdOffset + 16);
  const entries = new Map();
  let offset = centralDirectoryOffset;
  for (let index = 0; index < entryCount; index++) {
    if (pak.readUInt32LE(offset) !== 0x02014b50) {
      throw new Error(`Invalid ZIP central directory entry ${index}`);
    }
    const compressionMethod = pak.readUInt16LE(offset + 10);
    const crc = pak.readUInt32LE(offset + 16);
    const compressedSize = pak.readUInt32LE(offset + 20);
    const uncompressedSize = pak.readUInt32LE(offset + 24);
    const filenameLength = pak.readUInt16LE(offset + 28);
    const extraLength = pak.readUInt16LE(offset + 30);
    const commentLength = pak.readUInt16LE(offset + 32);
    const localHeaderOffset = pak.readUInt32LE(offset + 42);
    const entryPath = pak
      .toString("utf8", offset + 46, offset + 46 + filenameLength)
      .replace(/\\/g, "/")
      .toLowerCase();
    entries.set(entryPath, {
      path: entryPath,
      compressionMethod,
      crc,
      compressedSize,
      uncompressedSize,
      localHeaderOffset,
    });
    offset += 46 + filenameLength + extraLength + commentLength;
  }

  function readEntry(entryPath, maximumBytes = Infinity) {
    const entry = entries.get(entryPath.toLowerCase());
    if (!entry) return null;
    const localOffset = entry.localHeaderOffset;
    if (pak.readUInt32LE(localOffset) !== 0x04034b50) {
      throw new Error(`Invalid ZIP local header for ${entryPath}`);
    }
    const filenameLength = pak.readUInt16LE(localOffset + 26);
    const extraLength = pak.readUInt16LE(localOffset + 28);
    const dataOffset = localOffset + 30 + filenameLength + extraLength;
    const compressed = pak.subarray(
      dataOffset,
      dataOffset + entry.compressedSize
    );
    let uncompressed;
    if (entry.compressionMethod === 0) {
      uncompressed = compressed;
    } else if (entry.compressionMethod === 8) {
      uncompressed = zlib.inflateRawSync(compressed);
    } else {
      throw new Error(
        `Unsupported ZIP compression method ${entry.compressionMethod} for ${entryPath}`
      );
    }
    return uncompressed.subarray(
      0,
      Math.min(uncompressed.length, maximumBytes)
    );
  }

  return {
    version,
    pakOffset,
    pakLength,
    entries,
    readEntry,
  };
}

function parseVmt(text) {
  const clean = text.replace(/\/\/.*$/gm, "");
  const shaderMatch = clean.match(/^\s*"?([^"\s{]+)"?\s*\{/);
  const properties = {};
  for (const match of clean.matchAll(
    /"?\$(basetexture2?|detail|bumpmap|normalmap|envmapmask)"?\s+"?([^"\s{}]+)"?/gi
  )) {
    properties[`$${match[1].toLowerCase()}`] = match[2].toLowerCase();
  }
  return {
    shader: shaderMatch ? shaderMatch[1] : "[unparsed]",
    properties,
  };
}

function parseVtfHeader(buffer) {
  if (!buffer || buffer.length < 64) return null;
  if (buffer.toString("ascii", 0, 4) !== "VTF\0") return null;
  return {
    version: `${buffer.readUInt32LE(4)}.${buffer.readUInt32LE(8)}`,
    headerSize: buffer.readUInt32LE(12),
    width: buffer.readUInt16LE(16),
    height: buffer.readUInt16LE(18),
    flags: `0x${buffer.readUInt32LE(20).toString(16)}`,
    frames: buffer.readUInt16LE(24),
    bumpScale: Number(buffer.readFloatLE(48).toFixed(4)),
    highResolutionFormat: buffer.readUInt32LE(52),
    mipmapCount: buffer.readUInt8(56),
    lowResolutionFormat: buffer.readUInt32LE(57),
    lowResolutionWidth: buffer.readUInt8(61),
    lowResolutionHeight: buffer.readUInt8(62),
  };
}

function readFloatVector(buffer, offset) {
  return [
    buffer.readFloatLE(offset),
    buffer.readFloatLE(offset + 4),
    buffer.readFloatLE(offset + 8),
  ].map((coordinate) => Number(coordinate.toFixed(4)));
}

function parseSourceMdlHeader(buffer) {
  if (!buffer || buffer.length < 156) return null;
  const identifier = buffer.toString("ascii", 0, 4);
  if (identifier !== "IDST") return null;
  return {
    identifier,
    version: buffer.readInt32LE(4),
    checksum: buffer.readInt32LE(8),
    internalName: buffer
      .toString("utf8", 12, 76)
      .replace(/\0.*$/, ""),
    length: buffer.readInt32LE(76),
    eyePosition: readFloatVector(buffer, 80),
    illuminationPosition: readFloatVector(buffer, 92),
    hullMin: readFloatVector(buffer, 104),
    hullMax: readFloatVector(buffer, 116),
    viewBoundsMin: readFloatVector(buffer, 128),
    viewBoundsMax: readFloatVector(buffer, 140),
    flags: buffer.readInt32LE(152),
  };
}

function sourceTexturePath(textureName) {
  const normalized = textureName
    .replace(/\\/g, "/")
    .replace(/^materials\//i, "")
    .replace(/\.(vmt|vtf)$/i, "")
    .toLowerCase();
  return `materials/${normalized}.vtf`;
}

function modelFamily(model) {
  const normalized = model.toLowerCase().replace(/\\/g, "/");
  const parts = normalized.split("/");
  if (parts.length <= 4) return parts.slice(0, -1).join("/");
  return parts.slice(0, 4).join("/");
}

const args = parseArgs(process.argv);
if (!args.vmf || !args.vpk) {
  throw new Error(
    "Usage: node audit_nuke_reference.js --vmf <de_nuke_d.vmf> --vpk <pak01_dir.vpk> [--bsp <de_nuke.bsp>] [--out <audit.json>]"
  );
}

const vmfPath = path.resolve(args.vmf);
const vpkPath = path.resolve(args.vpk);
const bspPath = args.bsp ? path.resolve(args.bsp) : null;
const vmfText = fs.readFileSync(vmfPath, "utf8");
const vmfEntries = parseEntries(tokenize(vmfText), { index: 0 });
const world = children(vmfEntries, "world")[0];
if (!world) throw new Error("VMF has no world block");
const entities = children(vmfEntries, "entity");

const classCounts = new Map();
const materialCounts = new Map();
const visibleMaterialCounts = new Map();
const modelCounts = new Map();
const modelFamilyCounts = new Map();
const solidRecords = [];
const entityOrigins = [];
const selectedEntities = {
  doors: [],
  lighting: [],
  spawns: [],
  sky: [],
};
let sideCount = 0;
let displacementSides = 0;

function inspectSolid(solid, ownerClass, ownerId) {
  const points = [];
  const materials = [];
  let hasDisplacement = false;
  for (const side of children(solid.children, "side")) {
    sideCount++;
    const material = value(
      side.children,
      "material",
      "[missing]"
    ).toLowerCase();
    increment(materialCounts, material);
    if (!material.startsWith("tools/")) {
      increment(visibleMaterialCounts, material);
    }
    materials.push(material);
    if (children(side.children, "dispinfo").length) {
      displacementSides++;
      hasDisplacement = true;
    }
    points.push(...parsePlane(value(side.children, "plane")));
    const vertices = children(side.children, "vertices_plus")[0];
    if (vertices) {
      for (const vertex of vertices.children.filter(
        (entry) => entry.key === "v"
      )) {
        points.push(parseVector(vertex.value));
      }
    }
  }
  const bounds = boundsForPoints(points);
  if (bounds) {
    solidRecords.push({
      id: value(solid.children, "id"),
      ownerClass,
      ownerId,
      bounds,
      center: centerOfBounds(bounds),
      hasDisplacement,
      materials: [...new Set(materials)].sort(),
    });
  }
}

for (const solid of children(world.children, "solid")) {
  inspectSolid(solid, "worldspawn", value(world.children, "id"));
}

const lightClasses = new Set([
  "light",
  "light_spot",
  "light_environment",
  "env_sun",
  "env_sprite",
]);
const spawnClasses = new Set([
  "info_player_counterterrorist",
  "info_player_terrorist",
  "info_player_start",
]);
const skyClasses = new Set(["sky_camera"]);

for (const entity of entities) {
  const properties = keyValues(entity.children);
  const classname = properties.classname || "[missing]";
  const entityId = properties.id || "";
  increment(classCounts, classname);
  if (properties.origin) {
    entityOrigins.push({
      id: entityId,
      classname,
      origin: parseVector(properties.origin),
    });
  }
  for (const solid of children(entity.children, "solid")) {
    inspectSolid(solid, classname, entityId);
  }
  if (properties.model?.toLowerCase().startsWith("models/")) {
    const model = properties.model.toLowerCase().replace(/\\/g, "/");
    increment(modelCounts, model);
    increment(modelFamilyCounts, modelFamily(model));
  }
  if (classname === "prop_door_rotating") {
    selectedEntities.doors.push(properties);
  }
  if (lightClasses.has(classname)) {
    selectedEntities.lighting.push(properties);
  }
  if (spawnClasses.has(classname)) {
    selectedEntities.spawns.push(properties);
  }
  if (skyClasses.has(classname)) {
    selectedEntities.sky.push(properties);
  }
}

const worldBounds = boundsForPoints(
  solidRecords.flatMap((solid) => [solid.bounds.min, solid.bounds.max])
);
const spawnBounds = boundsForPoints(
  selectedEntities.spawns
    .filter((spawn) => spawn.origin)
    .map((spawn) => parseVector(spawn.origin))
);
const playableEnvelope = spawnBounds
  ? expandBounds(spawnBounds, [4096, 4096, 2048])
  : null;
const playableCandidateSolids = playableEnvelope
  ? solidRecords.filter((solid) => boundsIntersect(solid.bounds, playableEnvelope))
  : [];
const outlierSolids = playableEnvelope
  ? solidRecords.filter(
      (solid) => !boundsIntersect(solid.bounds, playableEnvelope)
    )
  : [];

const centerYHistogram = new Map();
for (const solid of solidRecords) {
  const bucket = Math.floor(solid.center[1] / 1024) * 1024;
  increment(centerYHistogram, `${bucket}..${bucket + 1023}`);
}

const vpk = parseVpkDirectory(vpkPath);
const bspPak = bspPath ? parseSourceBspPak(bspPath) : null;
const materialAudit = [];
for (const [material, references] of [...visibleMaterialCounts].sort((a, b) =>
  a[0].localeCompare(b[0])
)) {
  const vmtPath = `materials/${material}.vmt`;
  const vmtEntry = vpk.entries.get(vmtPath);
  let vmt = null;
  const dependencyAvailability = {};
  if (vmtEntry) {
    const vmtData = vpk.readEntry(vmtPath);
    vmt = parseVmt(vmtData.toString("utf8"));
    for (const [property, texture] of Object.entries(vmt.properties)) {
      const texturePath = sourceTexturePath(texture);
      dependencyAvailability[property] = {
        sourcePath: texturePath,
        presentInVpk: vpk.entries.has(texturePath),
        header: parseVtfHeader(vpk.readEntry(texturePath, 80)),
      };
    }
  }
  materialAudit.push({
    material,
    references,
    vmtPath,
    presentInVpk: Boolean(vmtEntry),
    shader: vmt?.shader ?? null,
    dependencies: dependencyAvailability,
  });
}

const modelAudit = [...modelCounts]
  .sort((left, right) => {
    if (right[1] !== left[1]) return right[1] - left[1];
    return left[0].localeCompare(right[0]);
  })
  .map(([model, references]) => ({
    model,
    references,
    presentInVpk: vpk.entries.has(model),
    presentInBspPak: Boolean(bspPak?.entries.has(model)),
    header: parseSourceMdlHeader(
      vpk.entries.has(model)
        ? vpk.readEntry(model, 156)
        : bspPak?.entries.has(model)
          ? bspPak.readEntry(model, 156)
          : null
    ),
  }));

const result = {
  formatVersion: 1,
  policy: {
    referenceOnly:
      "Valve VMF, VMT, VTF, MDL, and related game content remain outside this repository.",
    distributableOutput:
      "Only original assets, stock MOHAA references, generated map source, scripts, and derived factual manifests may be committed.",
  },
  source: {
    vmfFile: path.basename(vmfPath),
    vmfBytes: Buffer.byteLength(vmfText),
    vpkFile: path.basename(vpkPath),
    vpk: {
      signature: vpk.signature,
      version: vpk.version,
      treeSize: vpk.treeSize,
      entryCount: vpk.entries.size,
      fileDataSectionSize: vpk.fileDataSectionSize,
      archiveMd5SectionSize: vpk.archiveMd5SectionSize,
      otherMd5SectionSize: vpk.otherMd5SectionSize,
      signatureSectionSize: vpk.signatureSectionSize,
    },
    bspFile: bspPath ? path.basename(bspPath) : null,
    bsp: bspPak
      ? {
          version: bspPak.version,
          pakOffset: bspPak.pakOffset,
          pakLength: bspPak.pakLength,
          pakEntryCount: bspPak.entries.size,
        }
      : null,
  },
  geometry: {
    worldSolids: children(world.children, "solid").length,
    totalSolids: solidRecords.length,
    sideCount,
    displacementSides,
    worldBounds,
    spawnBounds,
    playableEnvelope,
    playableCandidateSolids: playableCandidateSolids.length,
    outlierSolids: outlierSolids.length,
    centerYHistogram: sortedObject(centerYHistogram),
  },
  entities: {
    total: entities.length,
    classes: sortedObject(classCounts),
    selected: selectedEntities,
    originCount: entityOrigins.length,
  },
  materials: {
    totalReferences: [...materialCounts.values()].reduce(
      (sum, count) => sum + count,
      0
    ),
    unique: materialCounts.size,
    counts: sortedObject(materialCounts),
    visibleReferences: [...visibleMaterialCounts.values()].reduce(
      (sum, count) => sum + count,
      0
    ),
    visibleUnique: visibleMaterialCounts.size,
    resolvedVmt: materialAudit.filter((material) => material.presentInVpk)
      .length,
    audit: materialAudit,
  },
  models: {
    references: [...modelCounts.values()].reduce(
      (sum, count) => sum + count,
      0
    ),
    unique: modelCounts.size,
    resolvedMdl: modelAudit.filter((model) => model.presentInVpk).length,
    resolvedEmbeddedMdl: modelAudit.filter(
      (model) => model.presentInBspPak
    ).length,
    resolvedTotalMdl: modelAudit.filter(
      (model) => model.presentInVpk || model.presentInBspPak
    ).length,
    parsedHeaders: modelAudit.filter((model) => model.header).length,
    families: sortedObject(modelFamilyCounts),
    audit: modelAudit,
  },
};

const output = `${JSON.stringify(result, null, 2)}\n`;
if (args.out) {
  const outputPath = path.resolve(args.out);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, output);
  process.stderr.write(`Wrote ${outputPath}\n`);
} else {
  process.stdout.write(output);
}
