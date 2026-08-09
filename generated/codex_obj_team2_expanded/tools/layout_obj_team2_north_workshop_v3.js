"use strict";

module.exports = function addNorthWorkshop({ concreteBox, metalBox }) {
  const prefix = "north_workshop";
  const xMin = 3584;
  const xMax = 4256;
  const yMin = 2080;
  const yMax = 2464;
  const facadeMin = yMin;
  const facadeMax = yMin + 32;
  const backMin = yMax - 32;
  const backMax = yMax;
  concreteBox(`${prefix}_west_wall`, [xMin, yMin, -384], [xMin + 32, yMax, 144]);
  concreteBox(`${prefix}_east_wall`, [xMax - 32, yMin, -384], [xMax, yMax, 144]);
  concreteBox(`${prefix}_back_wall`, [xMin + 32, backMin, -384], [xMax - 32, backMax, 144]);
  for (const [pillarMin, pillarMax] of [[3616, 3648], [3808, 3840], [4000, 4032], [4192, 4224]]) {
    concreteBox(`${prefix}_facade_pillar`, [pillarMin, facadeMin, -384], [pillarMax, facadeMax, 144]);
  }
  for (const [bayMin, bayMax] of [[3648, 3808], [3840, 4000], [4032, 4192]]) {
    concreteBox(`${prefix}_facade_lintel`, [bayMin, facadeMin, -64], [bayMax, facadeMax, 144]);
    metalBox(`${prefix}_bay_frame`, [bayMin, facadeMin - 8, -80], [bayMin + 16, facadeMax + 8, -64]);
    metalBox(`${prefix}_bay_frame`, [bayMax - 16, facadeMin - 8, -80], [bayMax, facadeMax + 8, -64]);
  }
  for (const dividerX of [3824, 4016]) {
    concreteBox(`${prefix}_divider`, [dividerX, facadeMax, -384], [dividerX + 24, backMin, -64], true);
  }
  metalBox(`${prefix}_roof`, [xMin, yMin, 144], [xMax, yMax, 176]);
  concreteBox(`${prefix}_parapet_west`, [xMin, yMin, 176], [xMin + 16, yMax, 224], true);
  concreteBox(`${prefix}_parapet_east`, [xMax - 16, yMin, 176], [xMax, yMax, 224], true);
  concreteBox(`${prefix}_parapet_south`, [xMin + 16, yMin, 176], [xMax - 16, yMin + 16, 224], true);
  concreteBox(`${prefix}_parapet_north`, [xMin + 16, yMax - 16, 176], [xMax - 16, yMax, 224], true);
};
