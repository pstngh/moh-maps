"use strict";

module.exports = function buildRevision4ForestLayout({ addBox, addUtility, M }) {
  const base = require("./layout_obj_team2_expanded_v3")({
    addBox,
    addUtility,
    M,
    includeAlliedBoundary: false,
  });
  const addedEntities = [...base.addedEntities];
  const allFaces = (spec) => ({ xMin: spec, xMax: spec, yMin: spec, yMax: spec, zMin: spec, zMax: spec });
  const concreteBox = (role, min, max, detail = false) => addBox(role, min, max, {
    xMin: M.concreteB,
    xMax: M.concreteB,
    yMin: M.bunker,
    yMax: M.bunker,
    zMin: M.concrete,
    zMax: M.concrete,
  }, { detail });
  const metalBox = (role, min, max) => addBox(role, min, max, allFaces(M.iron), { detail: true });
  const rockBox = (role, min, max, detail = false) => addBox(role, min, max, allFaces(M.rock), { detail });
  const pathBox = (role, minX, minY, maxX, maxY, topZ, depth = 64) => addBox(role,
    [minX, minY, topZ - depth], [maxX, maxY, topZ], {
      xMin: M.rock, xMax: M.rock, yMin: M.rock, yMax: M.rock, zMin: M.rock, zMax: M.grass,
    });

  // Remove the entire stock fence vocabulary and replace it with one broad,
  // walkable forest circuit. The route starts in the Allied spawn court,
  // descends through the western trees, traverses the southern ridge, bridges
  // the stock terrain gap, and returns through the former east fence line.
  pathBox("forest_allied_court", -2400, -320, -960, 320, -464, 96);
  for (let index = 0; index < 3; index += 1) {
    const yMax = -320 - index * 32;
    pathBox("forest_west_transition_steps", -2048, yMax - 32, -1536, yMax, -448 + index * 16, 64);
  }
  pathBox("forest_west_lower_lane", -2048, -1024, -1536, -416, -416, 80);
  for (let index = 0; index < 11; index += 1) {
    const yMax = -1024 - index * 32;
    pathBox("forest_west_climb_steps", -2048, yMax - 32, -1536, yMax, -400 + index * 16, 64);
  }
  pathBox("forest_west_ridge", -2048, -1536, -960, -1376, -240, 64);
  for (let index = 0; index < 4; index += 1) {
    const minX = -192 + index * 64;
    pathBox("forest_bridge_west_steps", minX, -1536, minX + 64, -1216, -224 + index * 16, 64);
  }
  pathBox("forest_central_bridge", 64, -1536, 1088, -1216, -176, 48);
  for (let index = 0; index < 4; index += 1) {
    const minX = 1088 + index * 64;
    pathBox("forest_bridge_east_steps", minX, -1536, minX + 64, -1216, -192 - index * 16, 64);
  }
  pathBox("forest_east_ridge", 1632, -1536, 2944, -1216, -240, 64);
  for (let index = 0; index < 14; index += 1) {
    const minY = -1216 + index * 32;
    pathBox("forest_east_descent_steps", 2560, minY, 3072, minY + 32, -256 - index * 16, 64);
  }
  pathBox("forest_east_lower_lane", 2560, -768, 3072, 256, -464, 80);
  pathBox("forest_east_entry", 1536, 256, 3072, 448, -464, 96);

  // The stock east and west terrains leave a central opening down to the
  // outside void. A finished rock foundation ties both terrain sections into
  // the southern sky hull, seals that seam, and supports the raised causeway.
  rockBox("forest_central_foundation", [-960, -1792, -960], [1632, -1040, -240]);
  addBox("forest_south_sky_hull", [-368, -1824, -960], [1632, -1792, 960], allFaces(M.sky));
  addBox("forest_north_sky_hull", [-368, -1040, -960], [960, -1008, 960], allFaces(M.sky));
  addBox("forest_central_sky_ceiling", [-960, -1792, 832], [1632, -1008, 992], allFaces(M.sky));
  rockBox("forest_south_retaining_wall", [-896, -1744, -240], [1568, -1696, 32]);
  for (const x of [-832, -384, 64, 512, 960, 1408]) {
    rockBox("forest_south_retaining_pier", [x, -1760, -240], [x + 64, -1680, 112], true);
  }
  for (const x of [-800, -352, 96, 544, 992]) {
    pathBox("forest_south_tree_planter", x, -1696, x + 240, -1584, -176, 64);
  }

  // Finished retaining faces hide the unmodelled central backside and turn the
  // bridge into intentional stock-style architecture instead of a view into
  // empty terrain. The doorway-sized bays are open to the forest side only.
  concreteBox("forest_central_facade_base", [-160, -1216, -560], [1280, -1184, -384]);
  concreteBox("forest_central_facade_backwall", [-160, -1184, -240], [1280, -1152, 176]);
  for (const x of [-128, 320, 768, 1216]) {
    concreteBox("forest_central_facade_pilaster", [x, -1248, -240], [x + 48, -1216, 176], true);
  }
  for (const [xMin, xMax] of [[64, 256], [512, 704], [960, 1152]]) {
    metalBox("forest_central_service_door", [xMin, -1232, -240], [xMax, -1216, -32]);
    concreteBox("forest_central_service_door_lintel", [xMin - 16, -1240, -32], [xMax + 16, -1216, 16], true);
  }
  concreteBox("forest_central_facade_band", [-160, -1232, 64], [1280, -1216, 112], true);
  for (const [xMin, xMax] of [[-160, 32], [288, 480], [736, 928], [1184, 1280]]) {
    concreteBox("forest_central_facade_pier", [xMin, -1216, -384], [xMax, -1184, 128]);
  }
  for (const [xMin, xMax] of [[32, 288], [480, 736], [928, 1184]]) {
    concreteBox("forest_central_facade_lintel", [xMin, -1216, -32], [xMax, -1184, 128]);
    metalBox("forest_central_facade_awning", [xMin + 16, -1248, -48], [xMax - 16, -1184, -16]);
  }
  concreteBox("forest_central_facade_cornice", [-192, -1224, 128], [1312, -1176, 176], true);


  // Two open shelters, utility banks and low stone clusters fill the route
  // without narrowing its bot lanes. There are no fence, wire, rail, grate,
  // caulk or nodraw construction materials in this revision.
  pathBox("forest_allied_layby", -2400, -928, -2080, -448, -416, 80);
  for (const [x, y] of [[-2384, -896], [-2160, -896], [-2384, -512], [-2160, -512]]) {
    metalBox("forest_allied_shelter_column", [x, y, -416], [x + 24, y + 24, -64]);
  }
  metalBox("forest_allied_shelter_roof", [-2400, -928, -64], [-2112, -464, -32]);
  concreteBox("forest_allied_shelter_back", [-2400, -928, -416], [-2368, -464, -64]);
  addUtility("forest_allied_utility", [-2320, -848, -416], [-2208, -752, -272], "xMax");
  addUtility("forest_allied_utility", [-2320, -688, -416], [-2208, -592, -304], "xMax");

  for (const [x, y] of [[1424, -1504], [2112, -1504], [1424, -1272], [2112, -1272]]) {
    metalBox("forest_ridge_shelter_column", [x, y, -240], [x + 24, y + 24, 96]);
  }
  metalBox("forest_ridge_shelter_roof", [1400, -1528, 96], [2160, -1248, 128]);
  for (const x of [1536, 1760, 1984]) {
    addUtility("forest_ridge_utility", [x, -1504, -240], [x + 128, -1408, -96], "yMax");
  }

  for (const box of [
    [[-1456, -224, -464], [-1296, -128, -336]],
    [[-1904, -896, -416], [-1808, -736, -288]],
    [[-1984, -1504, -240], [-1792, -1432, -112]],
    [[-1184, -1504, -240], [-1024, -1432, -128]],
    [[160, -1504, -176], [320, -1424, -64]],
    [[736, -1328, -176], [896, -1248, -48]],
    [[2272, -1504, -240], [2432, -1424, -112]],
    [[2656, -1152, -256], [2736, -992, -128]],
    [[2896, -704, -464], [3040, -608, -336]],
    [[2624, -224, -464], [2768, -128, -320]],
    [[2112, 304, -464], [2272, 400, -336]],
  ]) rockBox("forest_route_stone_cover", box[0], box[1], true);

  // Short buttresses and drainage heads finish the long retaining edges while
  // leaving the route visually open to the surviving forest.
  for (const x of [-1984, -1536, -1088, -640]) {
    rockBox("forest_west_ridge_buttress", [x, -1568, -304], [x + 96, -1536, -128], true);
  }
  for (const x of [1440, 1888, 2336, 2784]) {
    rockBox("forest_east_ridge_buttress", [x, -1568, -304], [x + 96, -1536, -128], true);
  }
  for (const y of [-704, -256, 160]) {
    concreteBox("forest_east_drain_head", [3040, y, -496], [3072, y + 96, -368], true);
  }

  function pointEntity(classname, properties) {
    const lines = ["{", `"classname" "${classname}"`];
    for (const [key, value] of Object.entries(properties)) lines.push(`"${key}" "${value}"`);
    lines.push("}");
    return lines.join("\r\n");
  }
  function addEntity(role, classname, properties) {
    addedEntities.push({ role, classname, properties, text: pointEntity(classname, properties) });
  }
  function addLamp(role, x, y, surfaceZ, angle = 0) {
    metalBox(`${role}_pole`, [x - 8, y - 8, surfaceZ], [x + 8, y + 8, surfaceZ + 288]);
    metalBox(`${role}_arm`, [x - 8, y - 8, surfaceZ + 272], [x + 64, y + 8, surfaceZ + 288]);
    addEntity(role, "static_lamp_lightbulb-caged", {
      model: "static//lightbulb_caged.tik", origin: `${x + 56} ${y} ${surfaceZ + 264}`,
      angle: String(angle), scale: "1.40", testanim: "idle",
    });
    addEntity(role, "static_corona_orange", {
      model: "static//corona_orange.tik", origin: `${x + 56} ${y} ${surfaceZ + 258}`,
      scale: "1.0", testanim: "idle",
    });
    addEntity(role, "light", {
      origin: `${x + 56} ${y} ${surfaceZ + 216}`, light: "80", _color: "1.0 0.9 0.8", overbright_range: "0.15",
    });
  }

  for (const spawn of [
    [-1600, 0, -416, 180],
    [-1792, -768, -368, 270],
    [-1760, -1456, -192, 0],
    [320, -1360, -128, 0],
    [896, -1360, -128, 180],
    [2368, -1360, -192, 180],
    [2800, -1040, -288, 90],
    [2800, -512, -416, 90],
    [1920, 352, -416, 0],
  ]) addEntity("forest_dm_spawn", "info_player_deathmatch", {
    origin: `${spawn[0]} ${spawn[1]} ${spawn[2]}`, angle: String(spawn[3]),
  });

  addEntity("forest_vehicle", "static_vehicle_german_opeltruck", {
    model: "static//vehicle_opeltruck.tik", origin: "-1248 80 -464", angle: "270", scale: "1.10", testanim: "idle",
  });  for (const [x, angle, scale] of [[-680, 20, 0.65], [-232, 310, 0.70], [216, 80, 0.60], [664, 215, 0.70], [1112, 345, 0.65]]) {
    addEntity("forest_south_tree", "static_natural_tree_oak", {
      model: "static//tree_oak.tik", origin: `${x} -1640 -176`, angle: String(angle), angles: "0 0 0", scale: String(scale), testanim: "idle",
    });
  }
  for (const [x, y, z, angle] of [
    [-2240, -816, -416, 90], [-1872, -928, -416, 0], [-1872, -1456, -240, 90],
    [-1104, -1456, -240, 0], [224, -1456, -176, 90], [800, -1280, -176, 180],
    [2352, -1456, -240, 0], [2960, -656, -464, 90], [2688, -176, -464, 0], [2208, 352, -464, 180],
  ]) addEntity("forest_crate", "static_item_nazicrate", {
    model: "static//nazi_crate.tik", origin: `${x} ${y} ${z}`, angle: String(angle), scale: "1.0", testanim: "idle",
  });

  for (const lamp of [
    [-1504, 224, -464, 180], [-2000, -704, -416, 0], [-1600, -1488, -240, 0],
    [-512, -1488, -240, 0],
    [2240, -1488, -240, 180], [3024, -912, -400, 180], [3024, -384, -464, 180], [2400, 416, -464, 270],
  ]) addLamp("forest_route_light", lamp[0], lamp[1], lamp[2], lamp[3]);
  for (const x of [160, 608, 1056]) {
    addEntity("forest_facade_light", "static_lamp_lightbulb-caged", { model: "static//lightbulb_caged.tik", origin: `${x} -1250 40`, angle: "90", scale: "1.40", testanim: "idle" });
    addEntity("forest_facade_light", "static_corona_orange", { model: "static//corona_orange.tik", origin: `${x} -1256 40`, scale: "1.0", testanim: "idle" });
    addEntity("forest_facade_light", "light", { origin: `${x} -1320 16`, light: "75", _color: "1.0 0.9 0.8", overbright_range: "0.15" });
  }

  return { addedEntities };
};
