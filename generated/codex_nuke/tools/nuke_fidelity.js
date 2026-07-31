"use strict";

function createNukeFidelityBuilder({
  face,
  cylinderBrush,
  frustumBrush,
  materials,
  nonBlockingDetail,
}) {
  const seen = new Set();

  function add(...vectors) {
    return vectors[0].map((_, axis) =>
      vectors.reduce((sum, vector) => sum + vector[axis], 0)
    );
  }

  function subtract(a, b) {
    return a.map((value, axis) => value - b[axis]);
  }

  function scale(vector, amount) {
    return vector.map((value) => value * amount);
  }

  function dot(a, b) {
    return a.reduce((sum, value, axis) => sum + value * b[axis], 0);
  }

  function cross(a, b) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ];
  }

  function normalized(vector) {
    const length = Math.sqrt(dot(vector, vector));
    return length > 0.0001 ? scale(vector, 1 / length) : [1, 0, 0];
  }

  function brushFromCorners(
    corners,
    material,
    surfaceParms = nonBlockingDetail,
    isDetail = true
  ) {
    const faces = [
      [4, 0, 7],
      [6, 2, 5],
      [1, 0, 5],
      [3, 2, 7],
      [3, 0, 2],
      [5, 4, 6],
    ];
    return [
      "{",
      ...faces.map((indices) =>
        face(
          indices.map((index) => corners[index]),
          material,
          isDetail,
          surfaceParms
        )
      ),
      "}",
    ].join("\n");
  }

  function yawPoint(origin, yaw, local) {
    const radians = (yaw * Math.PI) / 180;
    const cosine = Math.cos(radians);
    const sine = Math.sin(radians);
    return [
      origin[0] + local[0] * cosine - local[1] * sine,
      origin[1] + local[0] * sine + local[1] * cosine,
      origin[2] + local[2],
    ];
  }

  function localBox(
    origin,
    yaw,
    min,
    max,
    material,
    surfaceParms = nonBlockingDetail
  ) {
    const localCorners = [
      [min[0], min[1], min[2]],
      [max[0], min[1], min[2]],
      [max[0], max[1], min[2]],
      [min[0], max[1], min[2]],
      [min[0], min[1], max[2]],
      [max[0], min[1], max[2]],
      [max[0], max[1], max[2]],
      [min[0], max[1], max[2]],
    ];
    return brushFromCorners(
      localCorners.map((corner) => yawPoint(origin, yaw, corner)),
      material,
      surfaceParms
    );
  }

  function basisBox(center, axes, halfExtents, material, surfaceParms) {
    const corners = [];
    for (const z of [-1, 1]) {
      for (const y of [-1, 1]) {
        for (const x of [-1, 1]) {
          corners.push(
            add(
              center,
              scale(axes[0], x * halfExtents[0]),
              scale(axes[1], y * halfExtents[1]),
              scale(axes[2], z * halfExtents[2])
            )
          );
        }
      }
    }
    // The nested loop above produces 0,1,2,3 on the lower side and 4,5,6,7
    // on the upper side, but swaps corners 2/3 and 6/7 relative to localBox.
    [corners[2], corners[3]] = [corners[3], corners[2]];
    [corners[6], corners[7]] = [corners[7], corners[6]];
    return brushFromCorners(corners, material, surfaceParms);
  }

  function beamBetween(start, end, width, material, surfaceParms) {
    const vector = subtract(end, start);
    const length = Math.sqrt(dot(vector, vector));
    if (length < 0.5) return null;
    const longitudinal = scale(vector, 1 / length);
    const helper =
      Math.abs(dot(longitudinal, [0, 0, 1])) > 0.92
        ? [0, 1, 0]
        : [0, 0, 1];
    const lateral = normalized(cross(helper, longitudinal));
    const vertical = normalized(cross(longitudinal, lateral));
    return basisBox(
      scale(add(start, end), 0.5),
      [longitudinal, lateral, vertical],
      [length / 2, width / 2, width / 2],
      material,
      surfaceParms
    );
  }

  function hullBrush(instance, material, surfaceParms = nonBlockingDetail) {
    return localBox(
      instance.origin,
      instance.yaw,
      instance.header.hullMin,
      instance.header.hullMax,
      material,
      surfaceParms
    );
  }

  function groundedHull(instance) {
    const minimum = instance.header.hullMin[2];
    return minimum >= -8 && instance.header.hullMax[2] > 12;
  }

  function collisionParms(instance) {
    return instance.sourceSolid && instance.sourceSolid !== "0"
      ? ""
      : nonBlockingDetail;
  }

  function panelFrame(instance, material) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const ySpan = max[1] - min[1];
    const zSpan = max[2] - min[2];
    const frame = Math.min(12, Math.max(5, ySpan * 0.08));
    const depthMin = min[0];
    const depthMax = max[0];
    return [
      localBox(
        instance.origin,
        instance.yaw,
        [depthMin, min[1], min[2]],
        [depthMax, min[1] + frame, max[2]],
        material
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [depthMin, max[1] - frame, min[2]],
        [depthMax, max[1], max[2]],
        material
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [depthMin, min[1] + frame, max[2] - frame],
        [depthMax, max[1] - frame, max[2]],
        material
      ),
    ];
  }

  function railing(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const lengthAlongX = max[0] - min[0] >= max[1] - min[1];
    const start = lengthAlongX ? min[0] : min[1];
    const end = lengthAlongX ? max[0] : max[1];
    const otherMin = lengthAlongX ? min[1] : min[0];
    const otherMax = lengthAlongX ? max[1] : max[0];
    const thickness = Math.max(2.5, otherMax - otherMin);
    const localRail = (alongMin, alongMax, zMin, zMax) =>
      lengthAlongX
        ? [alongMin, otherMin, zMin, alongMax, otherMax, zMax]
        : [otherMin, alongMin, zMin, otherMax, alongMax, zMax];
    const brushes = [];
    for (const z of [max[2] - thickness, min[2] + (max[2] - min[2]) * 0.5]) {
      const box = localRail(start, end, z, z + thickness);
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          box.slice(0, 3),
          box.slice(3),
          materials.safetyYellow
        )
      );
    }
    const postStep = 128;
    for (let along = start; along <= end + 0.1; along += postStep) {
      const box = localRail(
        along - thickness / 2,
        Math.min(end, along + thickness / 2),
        min[2],
        max[2]
      );
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          box.slice(0, 3),
          box.slice(3),
          materials.safetyYellow
        )
      );
    }
    return brushes;
  }

  function chainlink(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const panel = localBox(
      instance.origin,
      instance.yaw,
      min,
      max,
      materials.chainlink,
      `${collisionParms(instance)} +surfaceparm nolightmap`.trim()
    );
    const brushes = [panel];
    const ySpan = max[1] - min[1];
    if (ySpan > 24 && max[2] - min[2] > 48) {
      for (const y of [min[1], max[1]]) {
        brushes.push(
          localBox(
            instance.origin,
            instance.yaw,
            [min[0] - 2, y - 2, min[2]],
            [max[0] + 2, y + 2, max[2]],
            materials.metalTrim,
            collisionParms(instance)
          )
        );
      }
    }
    return brushes;
  }

  function ladder(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const railWidth = 3;
    const brushes = [];
    for (const y of [min[1], max[1]]) {
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], y - railWidth, min[2]],
          [max[0], y + railWidth, max[2]],
          materials.safetyYellow
        )
      );
    }
    for (let z = min[2] + 8; z < max[2]; z += 16) {
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], min[1], z - 1.5],
          [max[0], max[1], z + 1.5],
          materials.safetyYellow
        )
      );
    }
    return brushes;
  }

  function vehicle(instance, color) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const length = max[0] - min[0];
    const width = max[1] - min[1];
    const height = max[2] - min[2];
    const baseTop = min[2] + height * 0.43;
    const cabinStart = min[0] + length * 0.28;
    const cabinEnd = min[0] + length * 0.72;
    const wheelZ = min[2] + height * 0.2;
    const brushes = [
      localBox(
        instance.origin,
        instance.yaw,
        [min[0], min[1], min[2] + 7],
        [max[0], max[1], baseTop],
        color,
        collisionParms(instance)
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [cabinStart, min[1] + width * 0.08, baseTop],
        [cabinEnd, max[1] - width * 0.08, max[2]],
        color,
        collisionParms(instance)
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [cabinStart + 5, min[1] - 0.5, baseTop + 4],
        [cabinEnd - 5, min[1] + 1.5, max[2] - 5],
        materials.windowBacking
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [cabinStart + 5, max[1] - 1.5, baseTop + 4],
        [cabinEnd - 5, max[1] + 0.5, max[2] - 5],
        materials.windowBacking
      ),
    ];
    for (const x of [min[0] + length * 0.22, min[0] + length * 0.78]) {
      for (const y of [min[1] - 1, max[1] - width * 0.16]) {
        brushes.push(
          localBox(
            instance.origin,
            instance.yaw,
            [x - length * 0.08, y, wheelZ - height * 0.14],
            [x + length * 0.08, y + width * 0.17, wheelZ + height * 0.14],
            materials.rubber,
            collisionParms(instance)
          )
        );
      }
    }
    return brushes;
  }

  function truckPart(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    if (/trailer/.test(instance.model)) {
      return [
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], min[1], min[2] + 18],
          [max[0], max[1], max[2]],
          materials.cleanWhiteMetal,
          collisionParms(instance)
        ),
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], min[1] - 2, min[2] + 4],
          [max[0], min[1] + 12, min[2] + 30],
          materials.rubber,
          collisionParms(instance)
        ),
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], max[1] - 12, min[2] + 4],
          [max[0], max[1] + 2, min[2] + 30],
          materials.rubber,
          collisionParms(instance)
        ),
      ];
    }
    return vehicle(instance, materials.equipmentBlue);
  }

  function forklift(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    if (/forklift_fork/.test(instance.model)) {
      const brushes = [];
      for (const x of [min[0] + 8, max[0] - 8]) {
        brushes.push(
          localBox(
            instance.origin,
            instance.yaw,
            [x - 3, min[1], min[2]],
            [x + 3, max[1], min[2] + 5],
            materials.metalTrim
          )
        );
      }
      return brushes;
    }
    const zBase = min[2] + (max[2] - min[2]) * 0.36;
    const brushes = [
      localBox(
        instance.origin,
        instance.yaw,
        [min[0], min[1], min[2] + 8],
        [max[0], max[1], zBase],
        materials.safetyYellow,
        collisionParms(instance)
      ),
    ];
    for (const x of [min[0] + 6, max[0] - 10]) {
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          [x - 3, min[1] + 5, zBase],
          [x + 3, max[1] - 5, max[2] - 5],
          materials.safetyYellow
        )
      );
    }
    brushes.push(
      localBox(
        instance.origin,
        instance.yaw,
        [min[0], min[1], max[2] - 8],
        [max[0], max[1], max[2]],
        materials.safetyYellow
      )
    );
    return brushes;
  }

  function chair(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const centerX = (min[0] + max[0]) / 2;
    const centerY = (min[1] + max[1]) / 2;
    const seatZ = min[2] + (max[2] - min[2]) * 0.48;
    return [
      localBox(
        instance.origin,
        instance.yaw,
        [min[0], min[1], seatZ],
        [max[0], max[1], seatZ + 5],
        materials.equipmentBlue
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [min[0], max[1] - 4, seatZ],
        [max[0], max[1], max[2]],
        materials.equipmentBlue
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [centerX - 2, centerY - 2, min[2]],
        [centerX + 2, centerY + 2, seatZ],
        materials.metalTrim
      ),
    ];
  }

  function controlDesk(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const depth = max[0] - min[0];
    return [
      localBox(
        instance.origin,
        instance.yaw,
        min,
        max,
        materials.controlPanel,
        collisionParms(instance)
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [max[0] - Math.max(3, depth * 0.08), min[1] + 12, min[2] + 12],
        [max[0] + 1, max[1] - 12, max[2] - 8],
        materials.windowBacking
      ),
    ];
  }

  function scaffold(instance, material, longitudinalAxis = 0) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const spans = max.map((value, axis) => value - min[axis]);
    const width = Math.max(7, Math.min(18, Math.min(...spans) * 0.5));
    const center = min.map((value, axis) => (value + max[axis]) / 2);
    const brushes = [];
    const crossAxis = longitudinalAxis === 0 ? 1 : 0;
    for (const crossSide of [min[crossAxis] + width, max[crossAxis] - width]) {
      const boxMin = [...min];
      const boxMax = [...max];
      boxMin[crossAxis] = crossSide - width / 2;
      boxMax[crossAxis] = crossSide + width / 2;
      boxMin[2] = center[2] - width / 2;
      boxMax[2] = center[2] + width / 2;
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          boxMin,
          boxMax,
          material
        )
      );
    }
    for (const longitudinalSide of [
      min[longitudinalAxis],
      max[longitudinalAxis] - width,
    ]) {
      const boxMin = [...min];
      const boxMax = [...max];
      boxMin[longitudinalAxis] = longitudinalSide;
      boxMax[longitudinalAxis] = longitudinalSide + width;
      boxMin[2] = center[2] - width / 2;
      boxMax[2] = center[2] + width / 2;
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          boxMin,
          boxMax,
          material
        )
      );
    }
    return brushes;
  }

  function crossBraces(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const centerY = (min[1] + max[1]) / 2;
    const endpoints = [
      [
        [min[0], centerY, min[2]],
        [max[0], centerY, max[2]],
      ],
      [
        [min[0], centerY, max[2]],
        [max[0], centerY, min[2]],
      ],
    ];
    return endpoints
      .map(([start, end]) =>
        beamBetween(
          yawPoint(instance.origin, instance.yaw, start),
          yawPoint(instance.origin, instance.yaw, end),
          7,
          materials.metalTrim,
          nonBlockingDetail
        )
      )
      .filter(Boolean);
  }

  function cargoCrane(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    if (/crane_base/.test(instance.model)) {
      const brushes = [];
      const leg = 54;
      for (const x of [min[0] + 80, max[0] - 80]) {
        for (const y of [min[1] + 28, max[1] - 28]) {
          brushes.push(
            localBox(
              instance.origin,
              instance.yaw,
              [x - leg / 2, y - leg / 2, min[2]],
              [x + leg / 2, y + leg / 2, max[2] - 35],
              materials.safetyYellow,
              collisionParms(instance)
            )
          );
        }
      }
      brushes.push(
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], min[1], max[2] - 55],
          [max[0], max[1], max[2]],
          materials.safetyYellow
        )
      );
      return brushes;
    }
    return [hullBrush(instance, materials.safetyYellow)];
  }

  function powerPole(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const radius = Math.max(8, Math.min(18, (max[0] - min[0]) * 0.35));
    const top = instance.origin[2] + max[2];
    return [
      cylinderBrush(
        instance.origin,
        instance.origin[2] + min[2],
        top,
        radius,
        materials.concreteDark,
        8,
        nonBlockingDetail
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [-12, min[1], max[2] - 80],
        [12, max[1], max[2] - 62],
        materials.metalTrim
      ),
    ];
  }

  function transformer(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const height = max[2] - min[2];
    if (/current_transformer/.test(instance.model)) {
      return [
        cylinderBrush(
          instance.origin,
          instance.origin[2] + min[2],
          instance.origin[2] + max[2],
          Math.max(12, (max[0] - min[0]) * 0.28),
          materials.cleanWhiteMetal,
          8,
          nonBlockingDetail
        ),
        localBox(
          instance.origin,
          instance.yaw,
          [min[0], min[1], min[2]],
          [max[0], max[1], min[2] + Math.min(24, height * 0.08)],
          materials.metalTrim
        ),
      ];
    }
    return [
      hullBrush(instance, materials.equipmentBlue, collisionParms(instance)),
      localBox(
        instance.origin,
        instance.yaw,
        [min[0] + 10, min[1] + 10, max[2] - Math.min(28, height * 0.2)],
        [max[0] - 10, max[1] - 10, max[2] + 8],
        materials.cleanWhiteMetal
      ),
    ];
  }

  function siteSilo(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const radius =
      Math.min(max[0] - min[0], max[1] - min[1]) * 0.49;
    const minZ = instance.origin[2] + min[2];
    const maxZ = instance.origin[2] + max[2];
    const brushes = [
      cylinderBrush(
        instance.origin,
        minZ,
        maxZ,
        radius,
        materials.cleanWhiteMetal,
        16,
        nonBlockingDetail
      ),
    ];
    for (const amount of [0.08, 0.5, 0.9]) {
      const z = minZ + (maxZ - minZ) * amount;
      brushes.push(
        cylinderBrush(
          instance.origin,
          z,
          z + 8,
          radius + 7,
          materials.safetyYellow,
          16,
          nonBlockingDetail
        )
      );
    }
    return brushes;
  }

  function reactorHead(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const radius =
      Math.min(max[0] - min[0], max[1] - min[1]) * 0.48;
    const minZ = instance.origin[2] + min[2];
    const maxZ = instance.origin[2] + max[2];
    const midZ = minZ + (maxZ - minZ) * 0.55;
    return [
      cylinderBrush(
        instance.origin,
        minZ,
        midZ,
        radius,
        materials.cleanWhiteMetal,
        12,
        nonBlockingDetail
      ),
      frustumBrush(
        instance.origin,
        midZ,
        maxZ,
        radius,
        radius * 0.2,
        materials.cleanWhiteMetal,
        12,
        nonBlockingDetail
      ),
    ];
  }

  function foliage(instance) {
    const min = instance.header.hullMin;
    const max = instance.header.hullMax;
    const xMid = (min[0] + max[0]) / 2;
    const yMid = (min[1] + max[1]) / 2;
    const thickness = 1.5;
    const brushes = [
      localBox(
        instance.origin,
        instance.yaw,
        [min[0], yMid - thickness, min[2]],
        [max[0], yMid + thickness, max[2]],
        materials.foliage,
        `${nonBlockingDetail} +surfaceparm nolightmap`
      ),
      localBox(
        instance.origin,
        instance.yaw,
        [xMid - thickness, min[1], min[2]],
        [xMid + thickness, max[1], max[2]],
        materials.foliage,
        `${nonBlockingDetail} +surfaceparm nolightmap`
      ),
    ];
    if (/tree/.test(instance.model) && max[2] - min[2] > 96) {
      brushes.push(
        cylinderBrush(
          instance.origin,
          instance.origin[2] + min[2],
          instance.origin[2] + min[2] + (max[2] - min[2]) * 0.55,
          Math.max(5, Math.min(14, (max[0] - min[0]) * 0.08)),
          materials.crate,
          6,
          nonBlockingDetail
        )
      );
    }
    return brushes;
  }

  function build({
    model,
    origin,
    angles,
    header,
    sourceSolid,
    skin = "",
  }) {
    if (!header || model.includes("/autocombine/")) return null;
    const pitch = Number.isFinite(angles[0]) ? angles[0] : 0;
    const yaw = Number.isFinite(angles[1]) ? angles[1] : 0;
    const roll = Number.isFinite(angles[2]) ? angles[2] : 0;
    const instance = {
      model,
      origin,
      angles,
      pitch,
      yaw,
      roll,
      header,
      sourceSolid,
      skin,
    };
    const duplicateKey = (family) =>
      `${family}:${origin.map((value) => value.toFixed(2)).join(":")}`;
    const handled = (family, brushes, grounded = groundedHull(instance)) => ({
      family,
      brushes: brushes.filter(Boolean),
      grounded,
    });
    const skipDuplicate = (family) => {
      const key = duplicateKey(family);
      if (seen.has(key)) return true;
      seen.add(key);
      return false;
    };

    if (/\/foliage\//.test(model) && !/skybox/.test(model)) {
      return handled("foliage", foliage(instance), true);
    }

    if (
      /\/nuke_cars\/nuke_(?:station_wagon|sedan|compact)/.test(model)
    ) {
      const palette = [
        materials.safetyRed,
        materials.equipmentBlue,
        materials.cleanWhiteMetal,
      ];
      return handled(
        "vehicle",
        vehicle(instance, palette[Math.abs(Number(skin) || 0) % palette.length]),
        true
      );
    }
    if (/\/nuke_cars\/nuke_truck_/.test(model)) {
      return handled("truck", truckPart(instance), true);
    }
    if (/\/nuke_forklift\/nuke_forklift_(?:base|fork)/.test(model)) {
      return handled("forklift", forklift(instance), true);
    }
    if (/\/nuke_cargo_crane\//.test(model)) {
      return handled("cargo_crane", cargoCrane(instance), true);
    }

    if (/\/metal_railing_001\//.test(model)) {
      return handled("railing", railing(instance), false);
    }
    if (/\/chainlink_fence_001\//.test(model)) {
      return handled("chainlink", chainlink(instance), false);
    }
    if (/\/metal_ladder_001\/metal_ladder_001_(?:32|64|128|256|512)\.mdl$/.test(model)) {
      return handled("ladder", ladder(instance), false);
    }

    if (/\/nuke_industrial_props\/nuke_industrial_silo_001\.mdl$/.test(model)) {
      if (skipDuplicate("a_site_silo")) return handled("a_site_silo_component", []);
      return handled("a_site_silo", siteSilo(instance), false);
    }
    if (/\/nuke_industrial_props\/nuke_industrial_silo_002\.mdl$/.test(model)) {
      return handled("a_site_silo_component", []);
    }
    if (/\/nuke_reactor_vessel_head\/nuke_reactor_vessel_head\.mdl$/.test(model)) {
      return handled("reactor_head", reactorHead(instance), false);
    }
    if (/\/nuke_reactor_vessel_head\/nuke_spent_fuel_racks\.mdl$/.test(model)) {
      return handled(
        "fuel_racks",
        [hullBrush(instance, materials.safetyYellow)],
        false
      );
    }

    if (/\/nuke_industrial_props\/nuke_industrial_upper_platform_001a\.mdl$/.test(model)) {
      if (skipDuplicate("upper_platform")) return handled("upper_platform_component", []);
      return handled(
        "upper_platform",
        [hullBrush(instance, materials.grating)],
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_upper_platform_001[b-d]\.mdl$/.test(model)) {
      return handled("upper_platform_component", []);
    }
    if (/\/nuke_industrial_props\/nuke_industrial_upper_beam_001\.mdl$/.test(model)) {
      return handled(
        "upper_beam",
        scaffold(instance, materials.safetyYellow, 0),
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_upper_crane_001a_new\.mdl$/.test(model)) {
      return handled(
        "upper_crane",
        scaffold(instance, materials.safetyYellow, 1),
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_upper_crane_001b_new\.mdl$/.test(model)) {
      return handled(
        "upper_crane_hoist",
        scaffold(instance, materials.safetyYellow, 1),
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_upper_crane_001[de]\.mdl$/.test(model)) {
      return handled(
        "upper_crane_detail",
        [hullBrush(instance, materials.safetyYellow)],
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_(?:upper|silo)_crane_.*hook/.test(model)) {
      return handled(
        "crane_hook",
        [hullBrush(instance, materials.safetyYellow)],
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_core_crane_001\.mdl$/.test(model)) {
      if (skipDuplicate("core_crane")) return handled("core_crane_component", []);
      return handled(
        "core_crane",
        scaffold(instance, materials.safetyYellow, 0),
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_core_crane_001[b-d]\.mdl$/.test(model)) {
      return handled("core_crane_component", []);
    }

    if (/\/nuke_industrial_props\/nuke_industrial_core_computer_001a(?:_low)?\.mdl$/.test(model)) {
      if (skipDuplicate("core_computer")) return handled("core_computer_component", []);
      return handled("core_computer", controlDesk(instance), false);
    }
    if (/\/nuke_industrial_props\/nuke_industrial_core_computer_001[bc](?:_low)?\.mdl$/.test(model)) {
      return handled("core_computer_component", []);
    }
    if (/\/nuke_office_desk\/nuke_control_room_(?:desk|flat_monitor)/.test(model)) {
      return handled("control_room_console", controlDesk(instance), false);
    }
    if (/\/control_room_displays\//.test(model)) {
      return handled(
        "control_room_display",
        [hullBrush(instance, materials.controlPanel)],
        false
      );
    }

    if (/\/nuke_power_pole\/nuke_power_pole(?:_02)?\.mdl$/.test(model)) {
      return handled("power_pole", powerPole(instance), true);
    }
    if (
      /\/(?:current_transformer|substation_transformer|transformer_add_01)\//.test(
        model
      )
    ) {
      return handled("transformer", transformer(instance), true);
    }

    if (/\/nuke_cross_bracing_beams\//.test(model)) {
      return handled("cross_bracing", crossBraces(instance), false);
    }
    if (
      /\/(?:nuke_columns|web_joist_001)\//.test(model) ||
      /\/nuke_industrial_props\/nuke_industrial_upper_column_/.test(model)
    ) {
      return handled(
        "structural_column",
        [hullBrush(instance, materials.metalTrim)],
        false
      );
    }
    if (/\/nuke_catwalk\//.test(model)) {
      return handled(
        "catwalk",
        [hullBrush(instance, materials.grating)],
        false
      );
    }

    if (
      /\/metal_crate_001\//.test(model) ||
      /\/nuke_recycling_bins\//.test(model)
    ) {
      return handled(
        "cover",
        [hullBrush(instance, materials.metalTrim, collisionParms(instance))],
        true
      );
    }
    if (
      /\/nuke_office_desk\/nuke_(?:office_desk|conference_table|office_cupboard)/.test(
        model
      ) ||
      /\/nuke_locker\//.test(model) ||
      /\/nuke_locker_bench\//.test(model) ||
      /\/nuke_vending_machine\//.test(model) ||
      /\/nuke_clothes\/nuke_(?:overall_locker|tank_top_locker)/.test(model) ||
      /\/nuke_office_props\/nuke_office_cabinet/.test(model)
    ) {
      return handled(
        "furniture",
        [hullBrush(instance, materials.controlPanel, collisionParms(instance))],
        true
      );
    }
    if (/\/(?:nuke_office_chair|nuke_chair)\//.test(model)) {
      return handled("chair", chair(instance), true);
    }

    if (/\/metal_door_001\/metal_door_(?:double_)?frame_/.test(model)) {
      return handled("door_frame", panelFrame(instance, materials.metalTrim), false);
    }
    if (/\/metal_door_001\/metal_door_00[1-5]b?(?:_low)?\.mdl$/.test(model)) {
      return handled(
        "static_door",
        [hullBrush(instance, materials.equipmentBlue)],
        false
      );
    }
    if (/\/metal_door_001\/metal_door_00[1-5].*(?:lock|window)/.test(model)) {
      return handled("static_door_component", []);
    }
    if (/\/rollup_door_001\/rollup_door_001_frame_/.test(model)) {
      return handled("rollup_frame", panelFrame(instance, materials.metalTrim), false);
    }
    if (/\/rollup_door_001\/rollup_door_001_(?:base|mechanism)_/.test(model)) {
      return handled(
        "rollup_mechanism",
        [hullBrush(instance, materials.metalTrim)],
        false
      );
    }
    if (/\/nuke_floor_hatch\//.test(model)) {
      return handled(
        "floor_hatch",
        [hullBrush(instance, materials.safetyYellow)],
        false
      );
    }
    if (/\/window_00[12]\//.test(model)) {
      return handled(
        "window",
        [hullBrush(instance, materials.glass)],
        false
      );
    }

    if (
      /\/nuke_roof_ac\//.test(model) ||
      /\/nuke_ventilation_exhaust\//.test(model) ||
      /\/nuke_ac_inset\//.test(model) ||
      /\/nuke_office_props\/nuke_office_vent_/.test(model) ||
      /\/nuke_vent_slats\//.test(model)
    ) {
      return handled(
        "ventilation",
        [hullBrush(instance, materials.corrugatedGray)],
        false
      );
    }
    if (/\/nuke_roof_caps\//.test(model)) {
      const min = instance.header.hullMin;
      const max = instance.header.hullMax;
      const radius =
        Math.min(max[0] - min[0], max[1] - min[1]) * 0.48;
      return handled(
        "roof_cap",
        [
          frustumBrush(
            instance.origin,
            instance.origin[2] + min[2],
            instance.origin[2] + max[2],
            radius,
            radius * 0.55,
            materials.corrugatedGray,
            8,
            nonBlockingDetail
          ),
        ],
        false
      );
    }

    if (/\/nuke_light_fixture\/nuke_bell_light\.mdl$/.test(model)) {
      const min = instance.header.hullMin;
      const max = instance.header.hullMax;
      const radius =
        Math.min(max[0] - min[0], max[1] - min[1]) * 0.45;
      return handled(
        "bell_light",
        [
          frustumBrush(
            instance.origin,
            instance.origin[2] + min[2],
            instance.origin[2] + max[2],
            radius,
            Math.max(3, radius * 0.18),
            materials.cleanWhiteMetal,
            8,
            nonBlockingDetail
          ),
        ],
        false
      );
    }

    if (
      /\/(?:nuke_electric_panel|transformer_yard_powerbox)\//.test(model) ||
      /\/nuke_industrial_props\/nuke_industrial_electrical_panel_/.test(model)
    ) {
      return handled(
        "electrical_equipment",
        [hullBrush(instance, materials.controlPanel)],
        false
      );
    }
    if (/\/nuke_industrial_props\/nuke_industrial_rail_/.test(model)) {
      return handled(
        "industrial_rail",
        [hullBrush(instance, materials.safetyYellow)],
        false
      );
    }

    if (/\/metal_pipe_001\/metal_pipe_001(?:[a-d])?_straight_/.test(model)) {
      if (Math.abs(pitch) > 0.1 || Math.abs(roll) > 0.1) return null;
      return handled("pipe", [hullBrush(instance, materials.pipe)], false);
    }

    return null;
  }

  return { build };
}

module.exports = { createNukeFidelityBuilder };
