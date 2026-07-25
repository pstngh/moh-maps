const fs = require("fs");
const path = require("path");

const mapName = process.argv[2] || "codex_arena01";
const outputRoot = path.resolve(process.argv[3] || "work/generated_game");
const mainDir = path.join(outputRoot, "main");
const mapDir = path.join(mainDir, "maps", "dm");
const textureDir = path.join(mainDir, "textures", "codex");

for (const directory of [mapDir, textureDir]) {
  fs.mkdirSync(directory, { recursive: true });
}

function fmt(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

function face(points, texture, shiftX = 0, shiftY = 0, rotation = 0, scaleX = 1, scaleY = 1) {
  const pointText = points
    .map((point) => `( ${point.map(fmt).join(" ")} )`)
    .join(" ");
  return `${pointText} ${texture} ${shiftX} ${shiftY} ${rotation} ${scaleX} ${scaleY} 0 0 0`;
}

function boxBrush(min, max, texture) {
  const [minX, minY, minZ] = min;
  const [maxX, maxY, maxZ] = max;
  return [
    "{",
    face([[minX, -16, 16], [minX, 0, 0], [minX, 16, 16]], texture),
    face([[maxX, 16, 16], [maxX, 0, 0], [maxX, -16, 16]], texture),
    face([[16, minY, -16], [0, minY, 0], [16, minY, 16]], texture),
    face([[16, maxY, 16], [0, maxY, 0], [16, maxY, -16]], texture),
    face([[-16, 16, minZ], [0, 0, minZ], [16, 16, minZ]], texture),
    face([[16, 16, maxZ], [0, 0, maxZ], [-16, 16, maxZ]], texture),
    "}",
  ].join("\n");
}

function pointEntity(classname, properties) {
  const lines = ["{", `"classname" "${classname}"`];
  for (const [key, value] of Object.entries(properties)) {
    lines.push(`"${key}" "${value}"`);
  }
  lines.push("}");
  return lines.join("\n");
}

function yawTowardCenter(x, y) {
  let degrees = (Math.atan2(-y, -x) * 180) / Math.PI;
  if (degrees < 0) degrees += 360;
  return Math.round(degrees);
}

function makeTga(filePath, colorA, colorB, size = 128, tile = 16) {
  const header = Buffer.alloc(18);
  header[2] = 2;
  header.writeUInt16LE(size, 12);
  header.writeUInt16LE(size, 14);
  header[16] = 24;
  header[17] = 0x20;

  const pixels = Buffer.alloc(size * size * 3);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const color = ((Math.floor(x / tile) + Math.floor(y / tile)) & 1) ? colorA : colorB;
      const offset = (y * size + x) * 3;
      pixels[offset] = color[2];
      pixels[offset + 1] = color[1];
      pixels[offset + 2] = color[0];
    }
  }
  fs.writeFileSync(filePath, Buffer.concat([header, pixels]));
}

const worldBrushes = [];
const addBox = (min, max, texture) => worldBrushes.push(boxBrush(min, max, texture));

// Sealed 2560 x 2560 x 512-unit arena shell.
addBox([-1344, -1344, -64], [1344, 1344, 0], "codex/floor");
addBox([-1344, -1344, 512], [1344, 1344, 576], "codex/ceiling");
addBox([-1344, -1344, 0], [-1280, 1344, 512], "codex/wall");
addBox([1280, -1344, 0], [1344, 1344, 512], "codex/wall");
addBox([-1280, -1344, 0], [1280, -1280, 512], "codex/wall");
addBox([-1280, 1280, 0], [1280, 1344, 512], "codex/wall");

// Central raised fighting platform.
addBox([-176, -176, 0], [176, 176, 96], "codex/trim");

// Four broad stairways. Each rise is 24 units and each tread is 56 units.
const stairHeights = [24, 48, 72, 96];
for (let i = 0; i < stairHeights.length; i++) {
  const h = stairHeights[i];
  addBox([-112, 400 - i * 56, 0], [112, 456 - i * 56, h], "codex/floor");
  addBox([-112, -456 + i * 56, 0], [112, -400 + i * 56, h], "codex/floor");
  addBox([400 - i * 56, -112, 0], [456 - i * 56, 112, h], "codex/floor");
  addBox([-456 + i * 56, -112, 0], [-400 + i * 56, 112, h], "codex/floor");
}

// Low cover creates two circulating lanes without doors or bot traps.
const coverBoxes = [
  [[-880, -720, 0], [-624, -656, 128]],
  [[624, -720, 0], [880, -656, 128]],
  [[-880, 656, 0], [-624, 720, 128]],
  [[624, 656, 0], [880, 720, 128]],
  [[-720, -880, 0], [-656, -624, 128]],
  [[656, -880, 0], [720, -624, 128]],
  [[-720, 624, 0], [-656, 880, 128]],
  [[656, 624, 0], [720, 880, 128]],
  [[-1040, -96, 0], [-912, 96, 112]],
  [[912, -96, 0], [1040, 96, 112]],
  [[-96, -1040, 0], [96, -912, 112]],
  [[-96, 912, 0], [96, 1040, 112]],
];
for (const [min, max] of coverBoxes) addBox(min, max, "codex/trim");

const worldspawn = [
  "{",
  `"classname" "worldspawn"`,
  `"message" "Codex Arena 01"`,
  `"ambientlight" "18 18 20"`,
  `"farplane" "5000"`,
  ...worldBrushes.map((brush, index) => `// brush ${index}\n${brush}`),
  "}",
].join("\n");

const entities = [worldspawn];
entities.push(pointEntity("info_player_start", { origin: "0 -1120 32", angle: "90" }));

const neutralSpawns = [
  [-1080, -880], [-720, -1080], [0, -1120], [720, -1080],
  [1080, -880], [1120, 0], [1080, 880], [720, 1080],
  [0, 1120], [-720, 1080], [-1080, 880], [-1120, 0],
  [-880, -320], [880, -320], [880, 320], [-880, 320],
];
for (const [x, y] of neutralSpawns) {
  entities.push(pointEntity("info_player_deathmatch", {
    origin: `${x} ${y} 32`,
    angle: String(yawTowardCenter(x, y)),
  }));
}

const alliedSpawns = [
  [-1080, -960], [-840, -1080], [-480, -1120], [-160, -1120],
  [160, -1120], [480, -1120], [840, -1080], [1080, -960],
];
const axisSpawns = alliedSpawns.map(([x, y]) => [-x, -y]);
for (const [x, y] of alliedSpawns) {
  entities.push(pointEntity("info_player_allied", {
    origin: `${x} ${y} 32`,
    angle: String(yawTowardCenter(x, y)),
  }));
}
for (const [x, y] of axisSpawns) {
  entities.push(pointEntity("info_player_axis", {
    origin: `${x} ${y} 32`,
    angle: String(yawTowardCenter(x, y)),
  }));
}

for (const x of [-800, 0, 800]) {
  for (const y of [-800, 0, 800]) {
    entities.push(pointEntity("light", {
      origin: `${x} ${y} 400`,
      light: "500",
      _color: "1.0 0.82 0.62",
    }));
  }
}

const mapText = `${entities.map((entity, index) => `// entity ${index}\n${entity}`).join("\n")}\n`;
fs.writeFileSync(path.join(mapDir, `${mapName}.map`), mapText);

const scriptText = `main:

// Scoreboard labels.
setcvar "g_obj_alliedtext1" "Codex Arena 01"
setcvar "g_obj_alliedtext2" "Compact bot-friendly deathmatch"
setcvar "g_obj_alliedtext3" ""
setcvar "g_obj_axistext1" ""
setcvar "g_obj_axistext2" ""
setcvar "g_obj_axistext3" ""

level waittill prespawn
exec global/DMprecache.scr
level.script = maps/dm/${mapName}.scr
level waittill spawn

end
`;
fs.writeFileSync(path.join(mapDir, `${mapName}.scr`), scriptText);
fs.writeFileSync(path.join(mapDir, `${mapName}_precache.scr`), "exec global/DMprecache.scr\n");

makeTga(path.join(textureDir, "floor.tga"), [92, 86, 74], [78, 72, 62]);
makeTga(path.join(textureDir, "wall.tga"), [112, 108, 98], [98, 94, 84]);
makeTga(path.join(textureDir, "trim.tga"), [72, 68, 60], [54, 50, 44]);
makeTga(path.join(textureDir, "ceiling.tga"), [68, 70, 72], [58, 60, 62]);

process.stdout.write(`${path.join(mapDir, `${mapName}.map`)}\n`);
