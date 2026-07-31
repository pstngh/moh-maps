#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

function fail(message) {
  throw new Error(message);
}

function sha256File(filename) {
  return crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
}

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!["--build-root", "--manifest", "--map-name"].includes(token)) {
      fail(`Unknown option: ${token}`);
    }
    index += 1;
    if (index >= argv.length) fail(`Missing value after ${token}`);
    options[
      token === "--build-root"
        ? "buildRoot"
        : token === "--map-name"
          ? "mapName"
          : "manifest"
    ] = argv[index];
  }
  if (!options.buildRoot || !options.manifest) {
    fail("--build-root and --manifest are required");
  }
  options.mapName ||= "codex_nuke_source2";
  return options;
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  const buildRoot = path.resolve(options.buildRoot);
  const manifestPath = path.resolve(options.manifest);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const localRoot = path.dirname(manifestPath);
  const textureReport = JSON.parse(
    fs.readFileSync(path.join(localRoot, "texture-conversion.json"), "utf8"),
  );
  const texturesByShader = new Map();
  for (const texture of textureReport.textures || []) {
    if (
      typeof texture.shader !== "string" ||
      !/^[a-z0-9_/-]+$/i.test(texture.shader) ||
      texturesByShader.has(texture.shader)
    ) {
      fail(`Invalid or duplicate texture report shader: ${texture.shader}`);
    }
    texturesByShader.set(texture.shader, texture);
  }
  const localMain = path.join(localRoot, "mohaa", "main");
  const buildMain = path.join(buildRoot, "main");
  const mapPath = path.join(buildMain, "maps", "dm", `${options.mapName}.map`);
  const precachePath = path.join(
    buildMain,
    "maps",
    "dm",
    `${options.mapName}_precache.scr`,
  );
  const reportPath = path.join(
    buildRoot,
    `${options.mapName}-conversion-report.json`,
  );
  const map = fs.readFileSync(mapPath, "utf8");
  const precache = fs.readFileSync(precachePath, "utf8");
  const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));

  if (manifest.assets.length !== report.stats.source2Models) {
    fail("Manifest asset count does not match generator report");
  }
  const expectedStaticModels = manifest.assets.filter(
    (asset) => (asset.compileMode || "static") === "static",
  ).length;
  const expectedRuntimeModels = manifest.assets.length - expectedStaticModels;
  if (
    report.stats.source2StaticModels !== expectedStaticModels ||
    report.stats.source2RuntimeModels !== expectedRuntimeModels
  ) {
    fail("Generator static/runtime model counts do not match the manifest");
  }
  if (report.stats.source2ProxyInstancesSuppressed <= 0) {
    fail("Local generator did not suppress any covered brush proxies");
  }
  if (report.stats.rotatingDoors !== 4) {
    fail(`Expected four interactive doors, found ${report.stats.rotatingDoors}`);
  }
  if (report.terroristSpawns !== 16 || report.counterSpawns !== 16) {
    fail("The local build changed the 16/16 team spawn set");
  }
  if (/"model"\s+"models\//i.test(map)) {
    fail('MAP model qpaths must not include the implicit "models/" prefix');
  }

  const assets = [];
  const referencedTextureShaders = new Set();
  for (const asset of manifest.assets) {
    const expectedQpath = asset.tiki.replace(/^models[\\/]/i, "").replace(/\\/g, "/");
    const escaped = expectedQpath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const matches = map.match(new RegExp(`"model"\\s+"${escaped}"`, "g")) || [];
    if (matches.length !== 1) {
      fail(`${asset.id} must appear exactly once in the MAP; found ${matches.length}`);
    }
    const expectedClassname =
      (asset.compileMode || "static") === "runtime"
        ? "script_model"
        : `static_codex_nuke_${asset.id}`;
    const classAndModel = new RegExp(
      `"classname"\\s+"${expectedClassname}"\\r?\\n` +
        `"model"\\s+"${escaped}"`,
      "g",
    );
    if ((map.match(classAndModel) || []).length !== 1) {
      fail(`${asset.id} is not emitted with classname ${expectedClassname}`);
    }
    const expectedOrigin = (asset.origin || [0, 0, 0]).map(Number);
    if (
      expectedOrigin.length !== 3 ||
      expectedOrigin.some((value) => !Number.isFinite(value))
    ) {
      fail(`${asset.id} has an invalid placement origin`);
    }
    const escapedOrigin = expectedOrigin
      .join(" ")
      .replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const entityBinding = new RegExp(
      `"classname"\\s+"${expectedClassname}"[^}]*` +
        `"model"\\s+"${escaped}"[^}]*` +
        `"origin"\\s+"${escapedOrigin}"`,
      "g",
    );
    if ((map.match(entityBinding) || []).length !== 1) {
      fail(`${asset.id} does not have the expected placement origin`);
    }
    const cacheLine = `cache ${asset.tiki.replace(/\\/g, "/")}`;
    const cacheMatches = precache
      .split(/\r?\n/)
      .filter((line) => line.trim() === cacheLine).length;
    if (
      ((asset.compileMode || "static") === "runtime" && cacheMatches !== 1) ||
      ((asset.compileMode || "static") === "static" && cacheMatches !== 0)
    ) {
      fail(
        `${asset.id} precache count must match compile mode; found ${cacheMatches}`,
      );
    }

    const sourceDirectory = path.join(
      localMain,
      "models",
      "codex_nuke",
      "source2",
      asset.id,
    );
    const buildDirectory = path.join(
      buildMain,
      "models",
      "codex_nuke",
      "source2",
      asset.id,
    );
    const conversionPath = path.join(
      sourceDirectory,
      `${asset.id}.conversion.json`,
    );
    const conversion = JSON.parse(fs.readFileSync(conversionPath, "utf8"));
    for (const extension of ["skd", "skc", "tik"]) {
      const filename = `${asset.id}.${extension}`;
      const sourcePath = path.join(sourceDirectory, filename);
      const buildPath = path.join(buildDirectory, filename);
      if (!fs.existsSync(sourcePath) || !fs.existsSync(buildPath)) {
        fail(`Missing staged ${filename}`);
      }
      const expected = conversion.outputs[filename]?.sha256;
      if (!expected || sha256File(sourcePath) !== expected || sha256File(buildPath) !== expected) {
        fail(`Hash mismatch for ${filename}`);
      }
    }

    for (const material of conversion.materials) {
      if (!material.baseColorImage) continue;
      const textureQpath = `${material.shader}.tga`.replace(/\//g, path.sep);
      const sourceTexture = path.join(localMain, textureQpath);
      const buildTexture = path.join(buildMain, textureQpath);
      if (!fs.existsSync(sourceTexture) || !fs.existsSync(buildTexture)) {
        fail(`Missing converted base color: ${material.shader}`);
      }
      const textureRecord = texturesByShader.get(material.shader);
      if (
        !textureRecord ||
        typeof textureRecord.outputSha256 !== "string" ||
        sha256File(sourceTexture) !== textureRecord.outputSha256 ||
        sha256File(buildTexture) !== textureRecord.outputSha256
      ) {
        fail(`Converted base-color hash mismatch: ${material.shader}`);
      }
      referencedTextureShaders.add(material.shader);
    }
    assets.push({
      id: asset.id,
      compileMode: asset.compileMode || "static",
      origin: expectedOrigin,
      vertices: conversion.geometry.verticesAfterSplitting,
      triangles: conversion.geometry.triangles,
      surfaces: conversion.geometry.surfaces,
      bounds: conversion.geometry.bounds,
    });
  }
  if (
    referencedTextureShaders.size !== texturesByShader.size ||
    [...texturesByShader.keys()].some(
      (shader) => !referencedTextureShaders.has(shader),
    )
  ) {
    fail("Texture conversion report contains unreferenced or missing shaders");
  }

  const result = {
    mapName: options.mapName,
    mapBytes: fs.statSync(mapPath).size,
    mapSha256: sha256File(mapPath),
    source2Models: assets.length,
    source2StaticModels: expectedStaticModels,
    source2RuntimeModels: expectedRuntimeModels,
    source2Vertices: assets.reduce((sum, asset) => sum + asset.vertices, 0),
    source2StaticVertices: assets
      .filter((asset) => asset.compileMode === "static")
      .reduce((sum, asset) => sum + asset.vertices, 0),
    source2RuntimeVertices: assets
      .filter((asset) => asset.compileMode === "runtime")
      .reduce((sum, asset) => sum + asset.vertices, 0),
    source2Triangles: assets.reduce((sum, asset) => sum + asset.triangles, 0),
    source2StaticTriangles: assets
      .filter((asset) => asset.compileMode === "static")
      .reduce((sum, asset) => sum + asset.triangles, 0),
    source2RuntimeTriangles: assets
      .filter((asset) => asset.compileMode === "runtime")
      .reduce((sum, asset) => sum + asset.triangles, 0),
    source2Textures: referencedTextureShaders.size,
    suppressedProxyInstances: report.stats.source2ProxyInstancesSuppressed,
    fidelityBrushesRemaining: report.stats.fidelityBrushes,
    rotatingDoors: report.stats.rotatingDoors,
    assets,
  };
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`ERROR: ${error.message}\n`);
  process.exitCode = 1;
}
