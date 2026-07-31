"use strict";
// Clean-room VMF audit for the fable_nuke rebuild (line-based, O(n)).
const fs = require("fs");
const path = require("path");
const lines = fs.readFileSync(path.resolve(process.argv[2]), "utf8").split("\n");
const a = { reference: path.basename(process.argv[2]), worldSolids: 0, sides: 0,
  displacementSides: 0, funcDetailSolids: 0, entities: 0, classnames: {}, materials: {},
  models: new Set(), spawns: { terrorist: 0, counter: 0 }, lights: 0,
  bounds: [[1e9,1e9,1e9],[-1e9,-1e9,-1e9]] };
const stack = []; let pendingName = null, entCls = null, entModel = null, entHasSolid = false;
for (let i = 0; i < lines.length; i++) {
  const t = lines[i].trim();
  if (!t) continue;
  if (t === "{") { stack.push(pendingName || "?"); pendingName = null; continue; }
  if (t === "}") {
    const closed = stack.pop();
    if (closed === "entity" && stack.length === 0) {
      a.entities++;
      a.classnames[entCls] = (a.classnames[entCls] || 0) + 1;
      if (entModel && !entModel.startsWith("*")) a.models.add(entModel.toLowerCase());
      if (entCls === "info_player_terrorist") a.spawns.terrorist++;
      if (entCls === "info_player_counterterrorist") a.spawns.counter++;
      if (entCls && entCls.startsWith("light")) a.lights++;
      if (entCls === "func_detail" && entHasSolid) a.funcDetailSolids++;
      entCls = entModel = null; entHasSolid = false;
    }
    continue;
  }
  if (t[0] === '"') {
    const m = t.match(/^"([^"]*)"\s+"([^"]*)"$/);
    if (!m) continue;
    const [, k, v] = m;
    const ctx = stack[stack.length - 1];
    if (ctx === "side") {
      if (k === "material") { const mm = v.toLowerCase(); a.materials[mm] = (a.materials[mm] || 0) + 1; }
      else if (k === "plane") {
        for (const pt of v.match(/\(([^)]+)\)/g) || []) {
          const [x, y, z] = pt.slice(1, -1).trim().split(/\s+/).map(Number);
          const b = a.bounds;
          if (x < b[0][0]) b[0][0] = x; if (y < b[0][1]) b[0][1] = y; if (z < b[0][2]) b[0][2] = z;
          if (x > b[1][0]) b[1][0] = x; if (y > b[1][1]) b[1][1] = y; if (z > b[1][2]) b[1][2] = z;
        }
      }
    } else if (stack.length === 1 && stack[0] === "entity") {
      if (k === "classname") entCls = v;
      if (k === "model") entModel = v;
    }
    continue;
  }
  pendingName = t;
  if (t === "solid") {
    if (stack[0] === "world" || stack[0] === "entity") {
      if (stack[0] === "world" && stack.length === 1) a.worldSolids++;
      if (stack[0] === "entity") entHasSolid = true;
    }
  } else if (t === "side") a.sides++;
  else if (t === "dispinfo") a.displacementSides++;
}
a.models = a.models.size;
const top = o => Object.fromEntries(Object.entries(o).sort((x, y) => y[1] - x[1]).slice(0, 25));
a.materialCount = Object.keys(a.materials).length;
const full = { ...a, classnames: top(a.classnames), materials: top(a.materials) };
fs.writeFileSync(path.join(__dirname, "..", "reference-audit.json"), JSON.stringify(full, null, 2));
console.log(JSON.stringify({ worldSolids: a.worldSolids, sides: a.sides,
  displacementSides: a.displacementSides, entities: a.entities, spawns: a.spawns,
  lights: a.lights, uniqueModels: a.models, materialCount: a.materialCount,
  bounds: a.bounds }));
