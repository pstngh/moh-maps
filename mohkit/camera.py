"""Pinhole maths for measuring a scene from one picture (docs/from-reference.md).

The game camera is a pinhole with square pixels. With fov 80 (the game's value: the
horizontal angle of a 4:3 view, see ``game.Shot``) the vertical angle is 64.4° at any
aspect, so a 1280x720 screenshot has a focal length of 572 px. For a photo, pass its
own vertical field of view.

Camera frame: the eye looks along +x with +y to the left of the image and +z up, so a
build.py that puts the eye at (0, 0, eye) with yaw 0 can use the numbers directly::

    cam = Camera(1280, 720)                  # eye 82 above the floor, level view
    d = cam.floor_depth(530)                 # floor line of a wall at y = 530 px -> 276 units away
    cam.lateral(170, d)                      # that wall's left corner -> 227 units to the left (+y)
    cam.height(263, d)                       # the door top -> 129 units above the floor
    cam.project((276, 81, 128))              # back to pixels, to check a guess
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Camera:
    width: int = 1280
    height_px: int = 720
    fov: float = 80.0            # game fov (horizontal at 4:3)
    eye: float = 82.0            # eye height above the floor (standing player)
    vfov: float = 0.0            # vertical field of view in degrees; overrides ``fov`` when set

    @property
    def vertical_fov(self) -> float:
        if self.vfov:
            return self.vfov
        return math.degrees(2 * math.atan(math.tan(math.radians(self.fov) / 2) * 3 / 4))

    @property
    def focal(self) -> float:
        """Focal length in pixels."""
        return (self.height_px / 2) / math.tan(math.radians(self.vertical_fov) / 2)

    @property
    def cx(self) -> float:
        return self.width / 2

    @property
    def cy(self) -> float:
        return self.height_px / 2

    def floor_depth(self, y: float) -> float:
        """Distance along the view axis of a floor point seen at image row ``y`` (below the horizon)."""
        if y <= self.cy:
            raise ValueError("a floor point must be below the horizon (y > height/2)")
        return self.focal * self.eye / (y - self.cy)

    def ceiling_depth(self, y: float, z: float) -> float:
        """Distance of a point at height ``z`` (above the eye) seen at image row ``y``."""
        return self.focal * (z - self.eye) / (self.cy - y)

    def lateral(self, x: float, depth: float) -> float:
        """Sideways offset (+ = image left) of a point at image column ``x`` and ``depth``."""
        return (self.cx - x) * depth / self.focal

    def height(self, y: float, depth: float) -> float:
        """Height above the floor of a point at image row ``y`` and ``depth``."""
        return self.eye + (self.cy - y) * depth / self.focal

    def depth_from_lateral(self, x: float, lateral: float) -> float:
        """Depth of a point on a wall parallel to the view axis at offset ``lateral`` seen at column ``x``."""
        return lateral * self.focal / (self.cx - x)

    def project(self, p: tuple[float, float, float]) -> tuple[float, float]:
        """Image position of the point ``p`` = (depth, lateral, height above the floor)."""
        d, lat, z = p
        return self.cx - self.focal * lat / d, self.cy - self.focal * (z - self.eye) / d
