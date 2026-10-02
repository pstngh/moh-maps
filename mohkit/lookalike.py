"""Find stock materials that look like part of a picture, and show them as swatches.

Recreating a scene from a screenshot or photo starts with "which stock texture is
this wall?". Two helpers:

* :func:`swatches` tiles stock materials into a labelled sheet (name, image size,
  the scale stock maps use most), so candidates can be compared by eye.
* :func:`rank` scores every retail Allied Assault material from ``data/materials.json``
  against a crop of the reference. The features tolerate baked lighting, because a
  lightmap multiplies a texture by a smooth, often tinted light: hue and
  saturation, contrast and roughness relative to the mean, gradient orientation
  (planks, brick courses) and local binary patterns.
  Absolute brightness counts only a little.

Ranking narrows ~1,400 materials to a couple of dozen; the final choice is made by
looking at the swatch sheet next to the reference.

CLI::

    python -m mohkit swatches stone brick -o sheet.png      # materials whose name contains a word
    python -m mohkit looks-like ref.png --box 170,230,390,520 --where wall -o cands.png
"""

from __future__ import annotations

import colorsys
import io
import json
import math
from pathlib import Path
from typing import Iterable, Optional, Sequence

from . import config as _config

DATA = Path(__file__).resolve().parent.parent / "data" / "materials.json"


def materials(avail: Sequence[str] = ("aa",), fs=None) -> dict[str, dict]:
    """Stock materials with an image: those in ``data/materials.json`` (usage, scale,
    orientation; tools excluded) plus, when ``fs`` is given, every other retail image
    under ``textures/`` (no usage data; many were never used in a stock map)."""
    mats = json.loads(DATA.read_text())["materials"]
    out = {k: v for k, v in mats.items() if v.get("avail") in avail and not v.get("tool") and v.get("image")}
    if fs is not None:
        from .pak import split_image_ext
        for path in fs.list("textures/", ext=(".jpg", ".tga")):
            name = split_image_ext(path[len("textures/"):])[0]
            if name not in mats and name.lower() not in out:
                out[name] = {"image": path}
    return out


def features(im) -> list[float]:
    """Lighting-tolerant descriptor of an RGB image (see the module doc): hue/saturation
    vector, log mean luminance, contrast and gradient energy relative to the mean, a
    4-bin gradient orientation histogram and a 10-bin local-binary-pattern histogram."""
    import numpy as np
    a = np.asarray(im.convert("RGB").resize((64, 64)), dtype=np.float32) / 255.0
    mean = a.reshape(-1, 3).mean(0)
    h, _, s = colorsys.rgb_to_hls(*[float(x) for x in mean])
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    m = float(lum.mean()) + 1e-3
    n = lum / m
    gx = np.zeros_like(n)
    gy = np.zeros_like(n)
    gx[:, 1:-1] = n[:, 2:] - n[:, :-2]
    gy[1:-1, :] = n[2:, :] - n[:-2, :]
    mag = np.hypot(gx, gy)
    ang = (np.degrees(np.arctan2(gy, gx)) + 180.0) % 180.0
    bins = ((ang + 22.5) // 45).astype(int) % 4
    ohist = np.array([mag[bins == i].sum() for i in range(4)])
    ohist = ohist / (ohist.sum() + 1e-6)
    c = n[1:-1, 1:-1]
    nb = [n[:-2, :-2], n[:-2, 1:-1], n[:-2, 2:], n[1:-1, 2:], n[2:, 2:], n[2:, 1:-1], n[2:, :-2], n[1:-1, :-2]]
    bits = np.stack([(x >= c) for x in nb]).astype(int)
    trans = (bits != np.roll(bits, 1, axis=0)).sum(0)
    code = np.where(trans <= 2, bits.sum(0), 9)
    lbp = np.bincount(code.ravel(), minlength=10)[:10].astype(float)
    lbp /= lbp.sum()
    return ([math.cos(2 * math.pi * h) * s, math.sin(2 * math.pi * h) * s, math.log(m), float(n.std()),
             float(mag.mean())] + list(ohist) + list(lbp))


# colour (2), brightness, contrast, roughness, orientation (4), LBP (10). Tuned on crops
# of mk_village screenshots with known materials; a radial power spectrum and heavier
# LBP weights made the ranking worse (blur and perspective change fine structure).
# Those screenshots were shot at r_picmip 2 (quarter-size textures, before 2026-10-01):
# re-tune on full-detail crops before trusting the fine-structure terms.
WEIGHTS = [4.0, 4.0, 0.3, 1.5, 1.5] + [2.0] * 4 + [1.0] * 10


def distance(f: Sequence[float], g: Sequence[float]) -> float:
    return math.sqrt(sum(w * (a - b) ** 2 for w, a, b in zip(WEIGHTS, f, g)))


_IMAGES: dict = {}


def _image(fs, path: str):
    from PIL import Image
    if path not in _IMAGES:
        _IMAGES[path] = Image.open(io.BytesIO(fs.read(path))).convert("RGB")
    return _IMAGES[path]


def rank(crop, where: Optional[str] = None, words: Iterable[str] = (), n: int = 24, all_images: bool = False,
         cfg: Optional[_config.Config] = None) -> list[tuple[str, float]]:
    """Materials most like ``crop`` (a PIL image), best first.

    ``all_images`` also ranks retail images no stock map uses (~4,000 instead of ~1,400). ``where``
    (``floor``/``wall``/``ceiling``) drops catalogued materials that stock maps use on
    less than 15% of their area in that orientation (uncatalogued images stay);
    ``words`` keeps names containing any word.

    Measured on crops of mk_village screenshots with known materials, the right one
    ranked 1, 23, 31, 40 and 62 among ~990 catalogued wall or ~470 floor materials:
    a sheet of the top 48 usually contains it, but always choose by eye. Tiling the
    texture to the crop's estimated world size made every case worse.
    """
    from .pak import GameFS
    cfg = cfg or _config.load()
    fs = GameFS(cfg.game_dir, ("main",), loose=False)
    f = features(crop)
    words = [w.lower() for w in words]
    out = []
    for name, m in materials(fs=fs if all_images else None).items():
        if m.get("transparent"):
            continue
        if where and "orient_area" in m and m["orient_area"].get(where, 0) < 0.15:
            continue
        if words and not any(w in name.lower() for w in words):
            continue
        try:
            im = _image(fs, m["image"])
        except Exception:  # noqa: BLE001 (unreadable image: skip it)
            continue
        out.append((name, distance(f, features(im))))
    out.sort(key=lambda t: t[1])
    return out[:n]


def swatches(names: Sequence[str], out: Path, first=None, first_label: str = "reference", cols: int = 6,
             cell: int = 192, cfg: Optional[_config.Config] = None) -> Path:
    """Labelled sheet of material images (``first``: an optional PIL image shown in the first cell)."""
    from PIL import Image, ImageDraw

    from .pak import GameFS
    cfg = cfg or _config.load()
    mats = json.loads(DATA.read_text())["materials"]
    fs = GameFS(cfg.game_dir, ("main",), loose=False)
    cells = []
    if first is not None:
        cells.append((first_label, first.convert("RGB")))
    for name in names:
        m = mats.get(name, {})
        image = m.get("image") or fs.find_image("textures/" + name)
        try:
            im = Image.open(io.BytesIO(fs.read(image))).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        size = m.get("size") or list(im.size)
        sc = m.get("scale") or [1, 1]
        cells.append((f"{name}\n{size[0]}x{size[1]} scale {sc[0]:g}", im))
    rows = max(1, (len(cells) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 28)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(cells):
        x, y = (i % cols) * cell, (i // cols) * (cell + 28)
        im = im.copy()
        im.thumbnail((cell, cell))
        sheet.paste(im, (x, y + 28))
        d.text((x + 4, y + 2), label, fill=(255, 220, 120))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def search_names(words: Iterable[str], avail: Sequence[str] = ("aa",), cfg: Optional[_config.Config] = None) -> list[str]:
    """Material names (catalogued and other retail images) containing any of ``words``, most used first."""
    from .pak import GameFS
    cfg = cfg or _config.load()
    words = [w.lower() for w in words]
    mats = materials(avail, fs=GameFS(cfg.game_dir, ("main",), loose=False))
    hits = [k for k in mats if any(w in k.lower() for w in words)]
    return sorted(hits, key=lambda k: -mats[k].get("uses", 0))
