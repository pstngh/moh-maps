"""Stock prop knowledge from data/static_models.json (built by mohkit.catalog).

Every AA model referenced by a stock map is listed with its QUAKED classname,
bounds (model space, entity scale 1; the origin is the model's pivot - for most
props the floor contact point, for hanging lamps the *bottom* of the lamp), and
whether a collision ``.map`` ships next to the ``.tik``. Q3map bakes that file
into world collision ("static collision masks"); props without one are
non-solid for players, bullets and bot navigation and need clip brushes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .config import REPO

DATA = REPO / "data" / "static_models.json"


@dataclass(frozen=True)
class Prop:
    path: str                   # models/static/indycrate.tik
    classname: str              # static_item_indycrate
    mins: tuple[float, float, float]
    maxs: tuple[float, float, float]
    collision: bool
    count: int                  # uses in stock maps
    game: str                   # aa | sh | bt

    @property
    def model_key(self) -> str:
        """Value for the entity ``model`` key (path without ``models/``)."""
        return self.path[len("models/"):] if self.path.startswith("models/") else self.path

    @property
    def size(self) -> tuple[float, float, float]:
        return tuple(self.maxs[i] - self.mins[i] for i in range(3))  # type: ignore[return-value]


@lru_cache(maxsize=1)
def _table() -> dict[str, dict]:
    if not DATA.is_file():
        return {}
    return json.loads(DATA.read_text())["models"]


def _norm(name: str) -> str:
    n = name.replace("\\", "/").replace("//", "/").lower()
    if not n.endswith(".tik"):
        n += ".tik"
    if not n.startswith("models/"):
        n = "models/" + n
    return n


def get(name: str) -> Optional[Prop]:
    """Look up ``static/indycrate``, ``static/indycrate.tik`` or ``models/static/indycrate.tik``."""
    m = _table().get(_norm(name))
    if not m:
        return None
    b = m.get("bounds") or m.get("editor_bounds") or [[-8, -8, 0], [8, 8, 16]]
    cls = m.get("quaked") or (m["classnames"][0][0] if m.get("classnames") else None)
    if not cls:
        cls = "static_" + _norm(name).rsplit("/", 1)[-1][:-4]
    return Prop(_norm(name), cls, tuple(b[0]), tuple(b[1]), bool(m.get("collision_map")), m.get("count", 0),
                m.get("avail", "?"))


def collision_bounds(name: str) -> Optional[tuple[tuple, tuple]]:
    """Bounds of the whole collision ``.map`` (every brush, including bullet-only foliage), or None."""
    c = (_table().get(_norm(name)) or {}).get("collision") or {}
    b = c.get("bounds")
    return (tuple(b[0]), tuple(b[1])) if b else None


def search(*words: str, game: str = "aa", collision: Optional[bool] = None, limit: int = 40) -> list[Prop]:
    """Props whose path contains all ``words``, most used first."""
    out = []
    for path, m in _table().items():
        if game and m.get("avail") != game:
            continue
        if all(w.lower() in path for w in words):
            p = get(path)
            if p and (collision is None or p.collision == collision):
                out.append(p)
    out.sort(key=lambda p: -p.count)
    return out[:limit]
