"use strict";
// Clean-room CS:GO Nuke -> MOHAA DM conversion (fable_nuke).
// Written fresh for the one-shot benchmark; reuses documented knowledge only:
// docs/MAP-SOURCE-FORMAT.md grammar/flags, playbook structural-shell +
// detail policy, three-axis skybox exclusion, clip preservation, prop
// omission-first policy, and light clustering. No code copied from
// generated/codex_nuke.
const fs = require("fs");
const path = require("path");

const vmfPath = path.resolve(process.argv[2] || "de_nuke_d.vmf");
const outRoot = path.resolve(__dirname, "..");
const mapDir = path.join(outRoot, "main", "maps", "dm");
fs.mkdirSync(mapDir, { recursive: true });

const SKYBOX_Y = 5000; // measured gap: playable <= ~4000, scenery >= 6656
const SKY = { tex: "sky/m5l2", contents: 0, flags: 276 };

// ---- material mapping (Source hr_ set -> original fable_nuke palette) ----
const M = {
  concrete: { tex: "fable_nuke/concrete_wall", contents: 0, flags: 0 },
  painted: { tex: "fable_nuke/painted_wall", contents: 0, flags: 0 },
  floor: { tex: "fable_nuke/concrete_floor", contents: 0, flags: 0 },
  trim: { tex: "fable_nuke/concrete_trim", contents: 0, flags: 0 },
  corrugated: { tex: "fable_nuke/corrugated", contents: 0, flags: 32768 },
  metal: { tex: "fable_nuke/metal_trim", contents: 0, flags: 32768 },
  asphalt: { tex: "fable_nuke/asphalt", contents: 0, flags: 0 },
  gravel: { tex: "fable_nuke/gravel", contents: 0, flags: 8388608 },
  grass: { tex: "fable_nuke/grass", contents: 0, flags: 524288 },
  glass: { tex: "fable_nuke/glass", contents: 8192, flags: 4194304, nonsolid: true },
  chainlink: { tex: "fable_nuke/chainlink", contents: 8192, flags: 0, nonsolid: true },
  caulk: { tex: "common/caulk", contents: 0, flags: 160 },
  clip: { tex: "common/clip", contents: 196608, flags: 2193 },
};
function mapMaterial(src) {
  const s = src.toLowerCase();
  if (s.startsWith("tools/")) {
    if (/clip/.test(s)) return M.clip;
    return M.caulk; // hint/skip/nodraw/areaportal/skybox sides inside kept solids
  }
  if (/chainlink|fence/.test(s)) return M.chainlink;
  if (/glass|window/.test(s)) return M.glass;
  if (/corrugated/.test(s)) return M.corrugated;
  if (/metal|rail|pipe|duct|vent/.test(s)) return M.metal;
  if (/asphalt/.test(s)) return M.asphalt;
  if (/gravel/.test(s)) return M.gravel;
  if (/grass|foliage/.test(s)) return M.grass;
  if (/dirt|ground|sand|mud/.test(s)) return M.gravel;
  if (/floor|stair/.test(s)) return M.floor;
  if (/trim/.test(s)) return M.trim;
  if (/paint/.test(s)) return M.painted;
  if (/concrete|plaster|brick|stone|tile/.test(s)) return M.concrete;
  if (/sky/.test(s)) return SKY;
  return null; // unknown -> caulk fallback, counted
}

// ---- VMF parse (structure-retaining stack machine) ----
const lines = fs.readFileSync(vmfPath, "utf8").split("\n");
const worldSolids = [];
const entities = [];
let stack = [], pending = null, ent = null, solid = null, side = null, inDisp = 0;
for (const raw of lines) {
  const t = raw.trim();
  if (!t) continue;
  if (t === "{") {
    stack.push(pending || "?");
    const ctx = stack.join("/");
    if (pending === "entity" && stack.length === 1) ent = { kv: {}, solids: [] };
    if (pending === "solid" && (ctx === "world/solid" || ctx === "entity/solid"))
      solid = { sides: [], ent: stack[0] === "entity" };
    if (pending === "side" && solid) side = { material: "", planes: [], disp: false };
    if (pending === "dispinfo" && side) { side.disp = true; inDisp = stack.length; }
    pending = null;
    continue;
  }
  if (t === "}") {
    const closed = stack.pop();
    if (inDisp && stack.length < inDisp) inDisp = 0;
    if (closed === "side" && solid && side) { solid.sides.push(side); side = null; }
    if (closed === "solid" && solid && stack.length === (solid.ent ? 1 : 1)) {
      if (solid.ent && ent) ent.solids.push(solid);
      else if (stack[0] === "world") worldSolids.push(solid);
      solid = null;
    }
    if (closed === "entity" && stack.length === 0 && ent) { entities.push(ent); ent = null; }
    continue;
  }
  if (t[0] === '"') {
    const m = t.match(/^"([^"]*)"\s+"([^"]*)"$/);
    if (!m) continue;
    if (inDisp) continue;
    const ctx = stack[stack.length - 1];
    if (ctx === "side" && side) {
      if (m[1] === "material") side.material = m[2];
      else if (m[1] === "plane")
        side.planes = (m[2].match(/\(([^)]+)\)/g) || []).map((p) =>
          p.slice(1, -1).trim().split(/\s+/).map(Number)
        );
    } else if (stack.length === 1 && stack[0] === "entity" && ent) ent.kv[m[1]] = m[2];
    continue;
  }
  pending = t;
}

// ---- conversion ----
const stats = {
  worldSolids: worldSolids.length, converted: 0, skyboxSkipped: 0,
  helperSkipped: 0, clipPreserved: 0, invalid: 0, displacementPlanarized: 0,
  unknownMaterialFaces: 0, funcDetailConverted: 0, funcBrushConverted: 0,
  propsSkipped: 0, lightsIn: 0, lightsOut: 0,
};
const fmt = (v) => { const r = Number(v.toFixed(2)); return Object.is(r, -0) ? "0" : String(r); };
const bounds = [[1e9, 1e9, 1e9], [-1e9, -1e9, -1e9]];
function growBounds(p) {
  for (let i = 0; i < 3; i++) {
    if (p[i] < bounds[0][i]) bounds[0][i] = p[i];
    if (p[i] > bounds[1][i]) bounds[1][i] = p[i];
  }
}
function centroidY(s) {
  let sum = 0, n = 0;
  for (const sd of s.sides) for (const p of sd.planes) { sum += p[1]; n++; }
  return n ? sum / n : 0;
}
function convertSolid(s, source) {
  if (s.sides.length < 4 || s.sides.some((sd) => sd.planes.length !== 3)) { stats.invalid++; return null; }
  if (centroidY(s) > SKYBOX_Y) { stats.skyboxSkipped++; return null; }
  const mats = s.sides.map((sd) => sd.material.toLowerCase());
  const allTools = mats.every((m) => m.startsWith("tools/"));
  if (allTools) {
    if (mats.some((m) => /clip/.test(m))) {
      stats.clipPreserved++;
      const out = ["{"];
      for (const sd of s.sides)
        out.push(`${sd.planes.map((p) => `( ${p.map(fmt).join(" ")} )`).join(" ")} common/clip 0 0 0 0.5 0.5 ${M.clip.contents} ${M.clip.flags} 0 +surfaceparm detail`);
      out.push("}");
      return out.join("\n");
    }
    stats.helperSkipped++;
    return null;
  }
  const out = ["{"];
  let nonsolid = true;
  for (const sd of s.sides) {
    let mat = mapMaterial(sd.material);
    if (!mat) { mat = M.caulk; stats.unknownMaterialFaces++; }
    if (!mat.nonsolid && mat !== SKY) nonsolid = false;
    if (sd.disp) stats.displacementPlanarized++;
    for (const p of sd.planes) growBounds(p);
    const extra = mat.nonsolid ? " +surfaceparm detail -surfaceparm solid" : " +surfaceparm detail";
    out.push(`${sd.planes.map((p) => `( ${p.map(fmt).join(" ")} )`).join(" ")} ${mat.tex} 0 0 0 0.5 0.5 ${mat.contents} ${mat.flags} 0${extra}`);
  }
  out.push("}");
  stats.converted++;
  if (source === "func_detail") stats.funcDetailConverted++;
  if (source === "func_brush") stats.funcBrushConverted++;
  return out.join("\n");
}

const brushes = [];
for (const s of worldSolids) { const b = convertSolid(s, "world"); if (b) brushes.push(b); }
for (const e of entities) {
  const cls = e.kv.classname;
  if ((cls === "func_detail" || cls === "func_brush" || cls === "func_breakable") && e.solids.length)
    for (const s of e.solids) { const b = convertSolid(s, cls === "func_detail" ? "func_detail" : "func_brush"); if (b) brushes.push(b); }
  if (cls === "prop_static") stats.propsSkipped++;
}

// ---- structural shell (playbook: sky shell structural, interior detail) ----
const lo = bounds[0].map((v) => Math.floor(v / 16) * 16 - 128);
const hi = bounds[1].map((v) => Math.ceil(v / 16) * 16 + 128);
hi[2] += 512; // headroom under the sky
function shellBrush(a, b, mat) {
  const [x0, y0, z0] = a, [x1, y1, z1] = b;
  const F = (pts) => `${pts.map((p) => `( ${p.map(fmt).join(" ")} )`).join(" ")} ${mat.tex} 0 0 0 0.5 0.5 ${mat.contents} ${mat.flags} 0`;
  return ["{",
    F([[x0, y0, z1], [x0, y1, z1], [x0, y1, z0]]),
    F([[x1, y1, z1], [x1, y0, z1], [x1, y0, z0]]),
    F([[x0, y0, z1], [x1, y0, z1], [x1, y0, z0]]),
    F([[x1, y1, z1], [x0, y1, z1], [x0, y1, z0]]),
    F([[x0, y1, z0], [x1, y1, z0], [x1, y0, z0]]),
    F([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1]]),
  "}"].join("\n");
}
const T = 64;
const shell = [
  shellBrush([lo[0] - T, lo[1] - T, lo[2] - T], [hi[0] + T, hi[1] + T, lo[2]], M.caulk),
  shellBrush([lo[0] - T, lo[1] - T, hi[2]], [hi[0] + T, hi[1] + T, hi[2] + T], SKY),
  shellBrush([lo[0] - T, lo[1] - T, lo[2]], [lo[0], hi[1] + T, hi[2]], SKY),
  shellBrush([hi[0], lo[1] - T, lo[2]], [hi[0] + T, hi[1] + T, hi[2]], SKY),
  shellBrush([lo[0] - T, lo[1] - T, lo[2]], [hi[0], lo[1], hi[2]], SKY),
  shellBrush([lo[0] - T, hi[1], lo[2]], [hi[0] + T, hi[1] + T, hi[2]], SKY),
];

// ---- entities ----
const outEnts = [];
function pointEnt(kv) {
  outEnts.push(`{\n${Object.entries(kv).map(([k, v]) => `"${k}" "${v}"`).join("\n")}\n}`);
}
const yawOf = (e) => {
  const a = (e.kv.angles || "0 0 0").split(/\s+/).map(Number);
  return Math.round(a[1] || 0);
};
const spawnClasses = [];
for (const e of entities) {
  const cls = e.kv.classname;
  if (cls === "info_player_terrorist" || cls === "info_player_counterterrorist") {
    const org = (e.kv.origin || "0 0 0").split(/\s+/).map(Number);
    org[2] += 24; // MOHAA spawns want clearance above the floor
    spawnClasses.push({
      team: cls === "info_player_terrorist" ? "info_player_axis" : "info_player_allied",
      origin: org.map(fmt).join(" "), angle: yawOf(e),
    });
  }
}
for (const s of spawnClasses) {
  pointEnt({ classname: s.team, origin: s.origin, angle: s.angle });
  pointEnt({ classname: "info_player_deathmatch", origin: s.origin, angle: s.angle });
}
pointEnt({ classname: "info_player_intermission", origin: "0 -1000 900", angle: "90" });

// lights: grid-cell clustering (256 units), strongest wins
const cells = new Map();
for (const e of entities) {
  const cls = e.kv.classname;
  if (cls !== "light" && cls !== "light_spot") continue;
  stats.lightsIn++;
  const org = (e.kv.origin || "0 0 0").split(/\s+/).map(Number);
  if (org[1] > SKYBOX_Y) continue;
  const lv = (e.kv._light || "255 255 255 200").split(/\s+/).map(Number);
  const key = org.map((v) => Math.round(v / 256)).join(",");
  const strength = lv[3] || 200;
  if (!cells.has(key) || cells.get(key).strength < strength)
    cells.set(key, { org, color: lv.slice(0, 3), strength });
}
for (const { org, color, strength } of cells.values()) {
  const mx = Math.max(...color, 1);
  pointEnt({
    classname: "light", origin: org.map(fmt).join(" "),
    _color: color.map((c) => (c / mx).toFixed(3)).join(" "),
    light: Math.round(Math.min(Math.max(strength * 0.45, 60), 300)),
  });
  stats.lightsOut++;
}

// doors: prop_door_rotating -> func_rotatingdoor with origin brush hinge
let doors = 0;
for (const e of entities) {
  if (e.kv.classname !== "prop_door_rotating") continue;
  const o = (e.kv.origin || "0 0 0").split(/\s+/).map(Number);
  const yaw = yawOf(e);
  const along = Math.abs(((yaw % 180) + 180) % 180 - 90) < 45 ? "x" : "y";
  const w = 56, th = 4, h = 108;
  const a = along === "x" ? [o[0], o[1] - th / 2, o[2]] : [o[0] - th / 2, o[1], o[2]];
  const b = along === "x" ? [o[0] + w, o[1] + th / 2, o[2] + h] : [o[0] + th / 2, o[1] + w, o[2] + h];
  const door = shellBrush(a, b, M.metal).replace(/ 0$/gm, " 0 +surfaceparm detail");
  const org = shellBrush([o[0] - 4, o[1] - 4, o[2]], [o[0] + 4, o[1] + 4, o[2] + h],
    { tex: "common/origin", contents: 16777216, flags: 2176 });
  outEnts.push(`{\n"classname" "func_rotatingdoor"\n"angle" "${yaw}"\n"time" "0.8"\n"wait" "1.0"\n"alwaysaway" "1"\n${door}\n${org}\n}`);
  doors++;
}

// ---- worldspawn + write ----
const world = [
  "// entity 0", "{",
  '"classname" "worldspawn"',
  '"message" "Fable Nuke"',
  '"ambientlight" "11 12 15"',
  '"suncolor" "128 120 104"',
  '"sundirection" "310 140 0"',
  '"sundiffuse" "1.25"',
  '"sundiffusecolor" "64 72 88"',
  '"_color" "0.97 0.99 1.0"',
  '"farplane" "8200"',
  '"farplane_color" "0.38 0.42 0.48"',
  ...shell.flatMap((b, i) => [`// brush ${i}`, b]),
  ...brushes.flatMap((b, i) => [`// brush ${i + shell.length}`, b]),
  "}",
];
const mapText = [world.join("\n"), ...outEnts.map((e, i) => `// entity ${i + 1}\n${e}`)].join("\n") + "\n";
fs.writeFileSync(path.join(mapDir, "fable_nuke.map"), mapText);

stats.doors = doors;
stats.spawnsPerTeam = spawnClasses.length / 2;
stats.shellBounds = { lo, hi };
fs.writeFileSync(path.join(outRoot, "fable_nuke-conversion-report.json"),
  JSON.stringify({ mapName: "fable_nuke", reference: path.basename(vmfPath), stats }, null, 2));
console.log(JSON.stringify(stats));
