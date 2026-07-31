#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function fail(message) {
  throw new Error(message);
}

function fixedString(buffer, offset, length) {
  const terminator = buffer.indexOf(0, offset);
  const end =
    terminator >= offset && terminator < offset + length
      ? terminator
      : offset + length;
  return buffer.toString("ascii", offset, end);
}

function parseSkd(filename) {
  const buffer = fs.readFileSync(filename);
  if (buffer.length < 148 || buffer.toString("ascii", 0, 4) !== "SKMD") {
    fail("SKD header is missing SKMD");
  }
  const version = buffer.readInt32LE(4);
  if (version !== 5) fail(`Expected retail SKD version 5, found ${version}`);
  const header = {
    bytes: buffer.length,
    name: fixedString(buffer, 8, 64),
    numSurfaces: buffer.readInt32LE(72),
    numBones: buffer.readInt32LE(76),
    ofsBones: buffer.readInt32LE(80),
    ofsSurfaces: buffer.readInt32LE(84),
    ofsEnd: buffer.readInt32LE(88),
    numBoxes: buffer.readInt32LE(132),
    ofsBoxes: buffer.readInt32LE(136),
    numMorphTargets: buffer.readInt32LE(140),
    ofsMorphTargets: buffer.readInt32LE(144),
  };
  if (header.ofsEnd !== buffer.length) fail("SKD ofsEnd does not match file size");
  if (header.numBones !== 1) fail("Static model must contain exactly one root bone");
  if (header.numSurfaces < 1 || header.numSurfaces > 24) {
    fail(`Static model has ${header.numSurfaces} surfaces; original TIKI setup supports at most 24`);
  }

  let boneCursor = header.ofsBones;
  const bones = [];
  for (let index = 0; index < header.numBones; index += 1) {
    if (boneCursor + 84 > buffer.length) fail("SKD bone header is truncated");
    const bone = {
      name: fixedString(buffer, boneCursor, 32),
      parent: fixedString(buffer, boneCursor + 32, 32),
      boneType: buffer.readInt32LE(boneCursor + 64),
      ofsBaseData: buffer.readInt32LE(boneCursor + 68),
      ofsChannelNames: buffer.readInt32LE(boneCursor + 72),
      ofsBoneNames: buffer.readInt32LE(boneCursor + 76),
      ofsEnd: buffer.readInt32LE(boneCursor + 80),
    };
    if (bone.ofsEnd <= 84 || boneCursor + bone.ofsEnd > buffer.length) {
      fail(`SKD bone ${index} has an invalid ofsEnd`);
    }
    if (
      bone.name !== "ORIGIN" ||
      bone.parent !== "worldbone" ||
      bone.boneType !== 1
    ) {
      fail("Static SKD root must be POSROT ORIGIN parented to worldbone");
    }
    bones.push(bone);
    boneCursor += bone.ofsEnd;
  }
  if (boneCursor !== header.ofsSurfaces) {
    fail("SKD bone records do not end at ofsSurfaces");
  }

  let surfaceCursor = header.ofsSurfaces;
  const surfaces = [];
  const surfaceNames = new Set();
  let totalTriangles = 0;
  let totalVertices = 0;
  const bounds = {
    minimum: [Infinity, Infinity, Infinity],
    maximum: [-Infinity, -Infinity, -Infinity],
  };
  for (let index = 0; index < header.numSurfaces; index += 1) {
    if (
      surfaceCursor + 100 > buffer.length ||
      buffer.toString("ascii", surfaceCursor, surfaceCursor + 4) !== "SKL "
    ) {
      fail(`SKD surface ${index} is truncated or missing SKL`);
    }
    const surface = {
      name: fixedString(buffer, surfaceCursor + 4, 64),
      numTriangles: buffer.readInt32LE(surfaceCursor + 68),
      numVertices: buffer.readInt32LE(surfaceCursor + 72),
      staticProcessed: buffer.readInt32LE(surfaceCursor + 76),
      ofsTriangles: buffer.readInt32LE(surfaceCursor + 80),
      ofsVertices: buffer.readInt32LE(surfaceCursor + 84),
      ofsCollapse: buffer.readInt32LE(surfaceCursor + 88),
      ofsEnd: buffer.readInt32LE(surfaceCursor + 92),
      ofsCollapseIndex: buffer.readInt32LE(surfaceCursor + 96),
    };
    if (!surface.name || surface.name.length > 28 || surfaceNames.has(surface.name)) {
      fail(`SKD surface name is empty, too long, or duplicated: ${surface.name}`);
    }
    surfaceNames.add(surface.name);
    if (
      surface.numVertices <= 0 ||
      surface.numTriangles <= 0 ||
      surface.numVertices > 999 ||
      surface.numTriangles > 1999
    ) {
      fail(`SKD surface ${surface.name} violates the retail count limits`);
    }
    if (surfaceCursor + surface.ofsEnd > buffer.length) {
      fail(`SKD surface ${surface.name} exceeds the file`);
    }

    const triangleEnd =
      surfaceCursor + surface.ofsTriangles + surface.numTriangles * 12;
    if (triangleEnd > surfaceCursor + surface.ofsEnd) {
      fail(`SKD surface ${surface.name} has invalid triangles`);
    }
    for (let triangle = 0; triangle < surface.numTriangles * 3; triangle += 1) {
      const vertexIndex = buffer.readUInt32LE(
        surfaceCursor + surface.ofsTriangles + triangle * 4,
      );
      if (vertexIndex >= surface.numVertices) {
        fail(`SKD surface ${surface.name} has an out-of-range triangle index`);
      }
    }

    let vertexCursor = surfaceCursor + surface.ofsVertices;
    for (let vertex = 0; vertex < surface.numVertices; vertex += 1) {
      if (vertexCursor + 28 > surfaceCursor + surface.ofsEnd) {
        fail(`SKD surface ${surface.name} has truncated vertex data`);
      }
      for (let component = 0; component < 5; component += 1) {
        if (!Number.isFinite(buffer.readFloatLE(vertexCursor + component * 4))) {
          fail(`SKD surface ${surface.name} contains a non-finite normal or UV`);
        }
      }
      const numWeights = buffer.readInt32LE(vertexCursor + 20);
      const numMorphs = buffer.readInt32LE(vertexCursor + 24);
      if (numWeights !== 1 || numMorphs !== 0) {
        fail(`Static vertex must have one weight and zero morphs`);
      }
      const weightCursor = vertexCursor + 28;
      if (weightCursor + 20 > surfaceCursor + surface.ofsEnd) {
        fail(`SKD surface ${surface.name} has a truncated weight`);
      }
      if (
        buffer.readInt32LE(weightCursor) !== 0 ||
        Math.abs(buffer.readFloatLE(weightCursor + 4) - 1) > 1e-6
      ) {
        fail("Static vertex must be fully weighted to root bone zero");
      }
      for (let axis = 0; axis < 3; axis += 1) {
        const value = buffer.readFloatLE(weightCursor + 8 + axis * 4);
        if (!Number.isFinite(value)) fail("Static vertex position is not finite");
        bounds.minimum[axis] = Math.min(bounds.minimum[axis], value);
        bounds.maximum[axis] = Math.max(bounds.maximum[axis], value);
      }
      vertexCursor += 48;
    }
    const expectedCollapse = vertexCursor - surfaceCursor;
    const expectedCollapseIndex =
      expectedCollapse + surface.numVertices * 4;
    const expectedEnd = expectedCollapseIndex + surface.numVertices * 4;
    if (
      surface.ofsCollapse !== expectedCollapse ||
      surface.ofsCollapseIndex !== expectedCollapseIndex ||
      surface.ofsEnd !== expectedEnd
    ) {
      fail(`SKD surface ${surface.name} has invalid collapse-array offsets`);
    }
    for (let collapse = expectedCollapse; collapse < expectedEnd; collapse += 4) {
      if (buffer.readInt32LE(surfaceCursor + collapse) !== 0) {
        fail(`SKD surface ${surface.name} has nonzero unauthored collapse data`);
      }
    }
    totalTriangles += surface.numTriangles;
    totalVertices += surface.numVertices;
    surfaces.push(surface);
    surfaceCursor += surface.ofsEnd;
  }
  if (surfaceCursor !== buffer.length) fail("SKD surfaces do not end at EOF");
  return { header, bones, surfaces, totalTriangles, totalVertices, bounds };
}

function parseSkc(filename) {
  const buffer = fs.readFileSync(filename);
  if (buffer.length < 96 || buffer.toString("ascii", 0, 4) !== "SKAN") {
    fail("SKC header is missing SKAN");
  }
  const version = buffer.readInt32LE(4);
  if (version !== 13) fail(`Expected retail SKC version 13, found ${version}`);
  const numChannels = buffer.readInt32LE(36);
  const ofsChannelNames = buffer.readInt32LE(40);
  const numFrames = buffer.readInt32LE(44);
  if (buffer.readInt32LE(12) !== buffer.length) {
    fail("SKC nBytesUsed does not match file size");
  }
  if (numChannels !== 2 || numFrames !== 1) {
    fail("Static SKC must have two channels and one frame");
  }
  if (ofsChannelNames + numChannels * 32 !== buffer.length) {
    fail("Static SKC channel names do not end at EOF");
  }
  if (buffer.readInt32LE(92) !== 96) fail("Static SKC frame channel offset is invalid");
  const names = [
    fixedString(buffer, ofsChannelNames, 32),
    fixedString(buffer, ofsChannelNames + 32, 32),
  ];
  if (names[0] !== "ORIGIN rot" || names[1] !== "ORIGIN pos") {
    fail(`Unexpected static SKC channel order: ${names.join(", ")}`);
  }
  const quaternion = [0, 4, 8, 12].map((offset) =>
    buffer.readFloatLE(96 + offset),
  );
  if (
    Math.abs(quaternion[0]) > 1e-6 ||
    Math.abs(quaternion[1]) > 1e-6 ||
    Math.abs(quaternion[2]) > 1e-6 ||
    Math.abs(quaternion[3] - 1) > 1e-6
  ) {
    fail("Static SKC rotation channel is not the identity quaternion");
  }
  for (let offset = 112; offset < 128; offset += 4) {
    if (Math.abs(buffer.readFloatLE(offset)) > 1e-6) {
      fail("Static SKC position channel is not zero");
    }
  }
  return {
    bytes: buffer.length,
    frameTime: buffer.readFloatLE(16),
    numChannels,
    numFrames,
    names,
  };
}

function main() {
  const target = process.argv[2];
  if (!target) {
    process.stderr.write(
      "Usage: node inspect_mohaa_static_model.js path/to/model.skd\n",
    );
    process.exitCode = 2;
    return;
  }
  const skdPath = path.resolve(target);
  const skcPath = skdPath.replace(/\.skd$/i, ".skc");
  const parsed = {
    skd: parseSkd(skdPath),
    skc: parseSkc(skcPath),
  };
  process.stdout.write(`${JSON.stringify(parsed, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`ERROR: ${error.message}\n`);
  process.exitCode = 1;
}
