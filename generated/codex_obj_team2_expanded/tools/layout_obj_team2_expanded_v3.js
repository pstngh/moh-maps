"use strict";

module.exports = function buildRevision3Layout({ addBox, addUtility, M }) {
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

  // East annex: revision 3 more than doubles the usable footprint and replaces
  // the former two narrow fence cuts with one continuous 1,824-unit frontage.
  addBox("service_deck", [3232, 320, -560], [5152, 2208, -384], {
    xMin: M.bunker,
    xMax: M.bunker,
    yMin: M.bunker,
    yMax: M.bunker,
    zMin: M.concrete,
    zMax: M.concrete,
  });
  addBox("service_deck", [3584, 2208, -560], [5152, 2496, -384], {
    xMin: M.bunker, xMax: M.bunker, yMin: M.bunker, yMax: M.bunker, zMin: M.concrete, zMax: M.concrete,
  });
  for (let index = 0; index < 6; index += 1) {
    const minX = 3040 + index * 32;
    addBox("grand_apron_steps", [minX, 384, -560], [minX + 32, 2208, -464 + index * 16], allFaces(M.step), { detail: true });
  }

  // Three-bay workshops close the south and north ends without narrowing the
  // courtyard. Their inward facades are permanently open for bots.
  function addWorkshop(prefix, yMin, yMax, openingSide) {
    const xMin = 3360;
    const xMax = 4256;
    const openingYMin = openingSide === "north" ? yMax - 32 : yMin;
    const openingYMax = openingSide === "north" ? yMax : yMin + 32;
    const backYMin = openingSide === "north" ? yMin : yMax - 32;
    const backYMax = openingSide === "north" ? yMin + 32 : yMax;
    concreteBox(`${prefix}_west_wall`, [xMin, yMin, -384], [xMin + 32, yMax, 144]);
    concreteBox(`${prefix}_east_wall`, [xMax - 32, yMin, -384], [xMax, yMax, 144]);
    concreteBox(`${prefix}_back_wall`, [xMin + 32, backYMin, -384], [xMax - 32, backYMax, 144]);
    for (const [pillarMin, pillarMax] of [[3392, 3456], [3712, 3760], [4000, 4048], [4192, 4224]]) {
      concreteBox(`${prefix}_facade_pillar`, [pillarMin, openingYMin, -384], [pillarMax, openingYMax, 144]);
    }
    for (const [bayMin, bayMax] of [[3456, 3712], [3760, 4000], [4048, 4192]]) {
      concreteBox(`${prefix}_facade_lintel`, [bayMin, openingYMin, -64], [bayMax, openingYMax, 144]);
      metalBox(`${prefix}_bay_frame`, [bayMin, openingYMin - 8, -80], [bayMin + 16, openingYMax + 8, -64]);
      metalBox(`${prefix}_bay_frame`, [bayMax - 16, openingYMin - 8, -80], [bayMax, openingYMax + 8, -64]);
    }
    for (const dividerX of [3744, 4032]) {
      concreteBox(`${prefix}_divider`, [dividerX, Math.min(backYMax, openingYMax), -384], [dividerX + 24, Math.max(backYMin, openingYMin), -64], true);
    }
    metalBox(`${prefix}_roof`, [xMin, yMin, 144], [xMax, yMax, 176]);
    concreteBox(`${prefix}_parapet_west`, [xMin, yMin, 176], [xMin + 16, yMax, 224], true);
    concreteBox(`${prefix}_parapet_east`, [xMax - 16, yMin, 176], [xMax, yMax, 224], true);
    concreteBox(`${prefix}_parapet_south`, [xMin + 16, yMin, 176], [xMax - 16, yMin + 16, 224], true);
    concreteBox(`${prefix}_parapet_north`, [xMin + 16, yMax - 16, 176], [xMax - 16, yMax, 224], true);
  }
  addWorkshop("south_workshop", 384, 800, "north");
  require("./layout_obj_team2_north_workshop_v3")({ concreteBox, metalBox });

  // Large four-bay maintenance hall. It is nearly twice the revision-2 floor
  // area and includes two interior choke walls, a catwalk, and four exterior
  // loops through the courtyard rather than one empty rectangular room.
  const hallXMin = 4352;
  const hallXMax = 5120;
  const hallYMin = 544;
  const hallYMax = 2464;
  concreteBox("hall_east_wall", [5088, hallYMin, -384], [hallXMax, hallYMax, 208]);
  concreteBox("hall_south_wall", [hallXMin, hallYMin, -384], [5088, hallYMin + 32, 208]);
  concreteBox("hall_north_wall", [hallXMin, hallYMax - 32, -384], [5088, hallYMax, 208]);
  const hallBays = [[672, 960], [1088, 1376], [1504, 1792], [1920, 2304]];
  const hallSolids = [[544, 672], [960, 1088], [1376, 1504], [1792, 1920], [2304, 2464]];
  for (const [yMin, yMax] of hallSolids) concreteBox("hall_west_pillar", [hallXMin, yMin, -384], [hallXMin + 32, yMax, 208]);
  for (const [yMin, yMax] of hallBays) {
    concreteBox("hall_bay_lintel", [hallXMin, yMin, -64], [hallXMin + 32, yMax, 208]);
    metalBox("hall_bay_frame", [hallXMin - 16, yMin, -384], [hallXMin, yMin + 16, -64]);
    metalBox("hall_bay_frame", [hallXMin - 16, yMax - 16, -384], [hallXMin, yMax, -64]);
    metalBox("hall_bay_frame", [hallXMin - 16, yMin, -80], [hallXMin, yMax, -64]);
    metalBox("hall_bay_awning", [hallXMin - 64, yMin + 24, -64], [hallXMin, yMax - 24, -32]);
  }
  metalBox("hall_roof", [hallXMin, hallYMin, 208], [hallXMax, hallYMax, 240]);
  concreteBox("hall_roof_parapet_west", [hallXMin, hallYMin, 240], [hallXMin + 16, hallYMax, 288], true);
  concreteBox("hall_roof_parapet_east", [hallXMax - 16, hallYMin, 240], [hallXMax, hallYMax, 288], true);
  concreteBox("hall_roof_parapet_south", [hallXMin + 16, hallYMin, 240], [hallXMax - 16, hallYMin + 16, 288], true);
  concreteBox("hall_roof_parapet_north", [hallXMin + 16, hallYMax - 16, 240], [hallXMax - 16, hallYMax, 288], true);
  for (const y of [640, 896, 1152, 1408, 1664, 1920, 2176, 2400]) {
    addBox("hall_ceiling_beam", [4384, y, 160], [5088, y + 16, 192], allFaces(M.ibeam), { detail: true });
  }
  for (const y of [1408, 1920]) {
    concreteBox("hall_partition", [4384, y, -384], [4688, y + 24, 64]);
    concreteBox("hall_partition", [4896, y, -384], [5088, y + 24, 64]);
    concreteBox("hall_partition_lintel", [4688, y, 32], [4896, y + 24, 64]);
  }

  // East-wall catwalk with a wide, regular stair and finished solid rails.
  for (let index = 0; index < 20; index += 1) {
    const minY = 704 + index * 32;
    addBox("hall_catwalk_steps", [4608, minY, -384], [4752, minY + 32, -368 + index * 16], allFaces(M.step), { detail: true });
  }
  metalBox("hall_catwalk_floor", [4752, 704, -80], [5088, 1536, -64]);
  for (const y of [736, 928, 1120, 1440, 1512]) {
    addBox("hall_catwalk_post", [4736, y, -64], [4752, y + 16, 48], allFaces(M.ibeam), { detail: true });
  }
  for (const [yMin, yMax] of [[704, 1280], [1408, 1536]]) {
    for (const [zMin, zMax] of [[-8, 0], [48, 56]]) metalBox("hall_catwalk_rail", [4736, yMin, zMin], [4752, yMax, zMax]);
  }
  for (const y of [768, 1088, 1456]) addBox("hall_catwalk_support", [4736, y, -384], [4776, y + 32, -80], allFaces(M.ibeam), { detail: true });

  // Courtyard canopy, open arcade, and cover form several broad close-range
  // loops while preserving at least 160-unit circulation lanes throughout.
  for (const x of [3616, 3904, 4192]) {
    for (const y of [1088, 1664]) addBox("courtyard_canopy_column", [x, y, -384], [x + 32, y + 32, 80], allFaces(M.ibeam), { detail: true });
  }
  metalBox("courtyard_canopy_roof", [3592, 1064, 80], [4248, 1720, 112]);
  for (const y of [1064, 1704]) addBox("courtyard_canopy_beam", [3592, y, 48], [4248, y + 16, 80], allFaces(M.ibeam), { detail: true });
  for (const y of [944, 1248, 1552, 1856, 2160]) {
    addBox("west_arcade_column", [3360, y, -384], [3392, y + 32, 16], allFaces(M.ibeam), { detail: true });
  }
  metalBox("west_arcade_roof", [3336, 920, 16], [3520, 2208, 48]);
  for (const box of [
    [[3520, 880, -384], [3664, 944, -272]],
    [[3936, 880, -384], [4080, 944, -272]],
    [[3520, 1888, -384], [3664, 1952, -272]],
    [[4048, 1904, -384], [4192, 1968, -272]],
    [[3744, 1264, -384], [3840, 1488, -272]],
    [[4000, 1424, -384], [4096, 1648, -272]],
    [[3296, 1984, -384], [3440, 2048, -272]],
    [[4216, 1040, -384], [4280, 1184, -272]],
  ]) concreteBox("yard_cover", box[0], box[1], true);
  for (const [x, y] of [[3488, 1008], [3488, 2112], [4256, 992], [4256, 2080], [3712, 1824], [4128, 1792]]) {
    metalBox("yard_bollard", [x, y, -384], [x + 16, y + 16, -256]);
  }

  // Roof services and interior utility banks give the larger structure a
  // finished stock-map density without alpha or custom texture dependencies.
  for (const vent of [
    [[4448, 720, 240], [4544, 912, 320]],
    [[4800, 1008, 240], [4896, 1200, 304]],
    [[4464, 1728, 240], [4560, 1920, 320]],
    [[4800, 2240, 240], [4896, 2432, 304]],
  ]) {
    addBox("roof_vent", vent[0], vent[1], allFaces(M.rust), { detail: true });
    metalBox("roof_vent_cap", [vent[0][0] - 8, vent[0][1] - 8, vent[1][2]], [vent[1][0] + 8, vent[1][1] + 8, vent[1][2] + 16]);
  }
  for (const utility of [
    [[3440, 448, -384], [3568, 544, -240], "yMax"],
    [[3712, 448, -384], [3840, 544, -272], "yMax"],
    [[4000, 448, -384], [4128, 544, -240], "yMax"],
    [[3648, 2304, -384], [3760, 2400, -240], "yMin"],
    [[3856, 2304, -384], [3968, 2400, -272], "yMin"],
    [[4064, 2304, -384], [4176, 2400, -240], "yMin"],
    [[4448, 1120, -384], [4544, 1216, -240], "xMin"],
    [[4936, 1120, -384], [5032, 1216, -272], "xMin"],
    [[4448, 2304, -384], [4544, 2400, -240], "xMin"],
    [[4936, 2304, -384], [5032, 2400, -272], "xMin"],
  ]) addUtility("utility_bank", utility[0], utility[1], utility[2]);
  addBox("service_duct", [5008, 624, 48], [5072, 1504, 112], allFaces(M.rust), { detail: true });
  for (const y of [768, 1056, 1344]) addBox("duct_bracket", [4984, y, 32], [5080, y + 16, 128], allFaces(M.ibeam), { detail: true });

  // Allied exterior route: rebuild the source fence curb as two finished
  // segments around a 326-unit gate, then wrap a broad L-shaped lane around
  // the west wall into the already existing rear-bunker yard.
  concreteBox("allied_fence_base_south", [-2026, 0, -560], [-1944, 344, -432]);
  concreteBox("allied_fence_base_north", [-2026, 670, -560], [-1944, 1056, -432]);
  for (const [yMin, yMax] of [[12, 344], [670, 1000]]) {
    metalBox("allied_fence_lower_rail", [-2014, yMin, -432], [-2006, yMax, -428]);
    metalBox("allied_fence_upper_rail", [-2014, yMin, -244], [-2006, yMax, -240]);
  }
  concreteBox("allied_gate_apron", [-2400, 344, -560], [-1944, 670, -464]);
  concreteBox("allied_outer_lane", [-2400, 320, -560], [-2080, 1344, -464]);
  concreteBox("allied_rear_link", [-2400, 1056, -560], [-1280, 1344, -464]);
  concreteBox("allied_outer_guard", [-2432, 320, -464], [-2400, 1344, -288]);
  concreteBox("allied_south_guard", [-2400, 320, -464], [-2026, 352, -288]);
  concreteBox("allied_north_guard", [-2400, 1312, -464], [-1760, 1344, -320]);
  for (const box of [
    [[-2320, 736, -464], [-2240, 896, -352]],
    [[-2176, 928, -464], [-2096, 1088, -352]],
    [[-2000, 1120, -464], [-1840, 1200, -352]],
    [[-1600, 1184, -464], [-1440, 1264, -352]],
  ]) concreteBox("allied_route_cover", box[0], box[1], true);
  for (const [x, y] of [[-2384, 544], [-2384, 1008], [-2208, 1320], [-1792, 1320]]) {
    metalBox("allied_route_light_pole", [x, y, -464], [x + 16, y + 16, -160]);
  }

  function pointEntity(classname, properties) {
    const lines = ["{", `"classname" "${classname}"`];
    for (const [key, value] of Object.entries(properties)) lines.push(`"${key}" "${value}"`);
    lines.push("}");
    return lines.join("\r\n");
  }

  const addedEntities = [];
  function addEntity(role, classname, properties) {
    addedEntities.push({ role, classname, properties, text: pointEntity(classname, properties) });
  }

  for (const spawn of [
    [3280, 512, -336, 0],
    [3808, 864, -336, 90],
    [4160, 864, -336, 180],
    [3408, 1168, -336, 0],
    [4160, 1856, -336, 180],
    [3680, 2256, -336, 0],
    [3784, 2320, -336, 225],
    [4512, 832, -336, 90],
    [4928, 1376, -336, 180],
    [4560, 2336, -336, 270],
    [-2208, 576, -416, 90],
    [-2208, 1168, -416, 45],
  ]) addEntity("dm_spawn", "info_player_deathmatch", { origin: `${spawn[0]} ${spawn[1]} ${spawn[2]}`, angle: String(spawn[3]) });

  addEntity("vehicle", "static_vehicle_german_opeltruck", { model: "static//vehicle_opeltruck.tik", origin: "3920 2080 -384", angle: "90", scale: "1.10", testanim: "idle" });
  for (const [x, y, z, angle] of [
    [3672, 912, -384, 20], [4064, 912, -384, 340], [3504, 2016, -384, 90],
    [4192, 1984, -384, 180], [4480, 1088, -384, 0], [4992, 1040, -384, 270],
    [4480, 2240, -384, 90], [4992, 2464, -384, 180], [4800, 1472, -64, 90],
    [-2288, 400, -464, 0], [-2240, 1248, -464, 90], [-1552, 1120, -464, 180],
  ]) addEntity("crate", "static_item_nazicrate", { model: "static//nazi_crate.tik", origin: `${x} ${y} ${z}`, angle: String(angle), scale: "1.0", testanim: "idle" });

  function addLamp(role, fixtureOrigin, coronaOrigin, lightOrigin, angle, intensity) {
    addEntity(role, "static_lamp_lightbulb-caged", { model: "static//lightbulb_caged.tik", origin: fixtureOrigin.join(" "), angle: String(angle), scale: "1.40", testanim: "idle" });
    addEntity(role, "static_corona_orange", { model: "static//corona_orange.tik", origin: coronaOrigin.join(" "), scale: "1.0", testanim: "idle" });
    addEntity(role, "light", { origin: lightOrigin.join(" "), light: String(intensity), _color: "1.0 0.9 0.8", overbright_range: "0.15" });
  }
  for (const y of [888, 1384, 1880, 2376]) addLamp("bay_light", [4342, y, -112], [4336, y, -115], [4280, y, -112], 0, 85);
  for (const y of [768, 1104, 1456, 1824, 2176, 2512]) addLamp("hall_light", [4800, y, 196], [4800, y, 190], [4800, y, 128], -2, 85);
  for (const x of [3712, 3920, 4128]) addLamp("canopy_light", [x, 1392, 68], [x, 1392, 62], [x, 1392, 0], -2, 65);
  for (const x of [3520, 3840, 4128]) addLamp("south_workshop_light", [x, 768, 132], [x, 768, 126], [x, 768, 64], -2, 65);
  for (const x of [3520, 3840, 4128]) addLamp("north_workshop_light", [x, 2112, 132], [x, 2112, 126], [x, 2112, 64], -2, 65);
  for (const [x, y] of [[-2376, 552], [-2376, 1016], [-2200, 1312], [-1784, 1312]]) {
    addLamp("allied_route_light", [x, y, -176], [x, y, -182], [x + 24, y, -224], 0, 70);
  }

  return { addedEntities };
};
