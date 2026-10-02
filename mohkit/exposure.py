"""Exposure check for screenshots: how bright a shot is, and how much of it is blown out
or crushed.

Lighting problems in converted maps are rarely one bug: a room is white because a
texlight sits under its ceiling, a wall is black because no light reaches it, a prop
glows because its material is drawn fullbright. Judging that from contact sheets by eye
misses the pattern. This module measures every shot the same way so a map's shots can be
ranked, compared with stock maps (``stock_shots``), and re-measured after a fix::

    python -m mohkit exposure local/csgo/cs_nuke/shots          # one map, worst shots first
    python -m mohkit exposure local/csgo/*/shots --by-map       # one line per map
    python -m mohkit exposure a.png --mask out.png              # red = blown, blue = crushed

Luminance is Rec. 709 luma of the 8-bit sRGB values (what the eye reads as brightness on
screen). Thresholds:

* **white**: luma >= 240 (near-white; a lit white wall in a stock map stays below it);
* **black**: luma <= 16 (near-black; stock maps keep shadows above it);
* **blown** / **crushed** regions: share of 32 x 32 pixel blocks (at 1280 x 720) whose mean
  luma is >= 225 / <= 20, i.e. whole areas rather than specks.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

WHITE = 240
BLACK = 16
BLOCK = 32
BLOWN_BLOCK = 225
CRUSHED_BLOCK = 20

# Target band, from stock MOHAA maps shot the same way (``stock_shots``; docs/lighting.md):
# shots outside it are flagged. Set from the mohdm1-3/5-7 measurements (2026-10-01).
MEAN_LOW, MEAN_HIGH = 55.0, 150.0
WHITE_MAX = 0.03     # share of near-white pixels
BLACK_MAX = 0.08     # share of near-black pixels
BLOWN_MAX = 0.02     # share of blown-out blocks
CRUSHED_MAX = 0.05   # share of crushed blocks


@dataclass
class Exposure:
    name: str
    mean: float          # mean luma 0-255
    p05: float
    p50: float
    p95: float
    white: float         # share of pixels with luma >= WHITE
    black: float         # share of pixels with luma <= BLACK
    blown: float         # share of BLOCK-pixel blocks with mean luma >= BLOWN_BLOCK
    crushed: float       # share of blocks with mean luma <= CRUSHED_BLOCK
    warmth: float        # mean R / mean B (stock daylight ~1.0-1.2; > 1 is warm)
    path: str = ""

    @property
    def flags(self) -> list[str]:
        f = []
        if self.white > WHITE_MAX or self.blown > BLOWN_MAX:
            f.append("BLOWN")
        if self.black > BLACK_MAX or self.crushed > CRUSHED_MAX:
            f.append("CRUSHED")
        if self.mean < MEAN_LOW:
            f.append("DIM")
        if self.mean > MEAN_HIGH:
            f.append("BRIGHT")
        return f

    @property
    def score(self) -> float:
        """Badness: 0 for a shot inside every limit, growing with how far outside it is."""
        s = 0.0
        s += max(0.0, self.white - WHITE_MAX) * 400 + max(0.0, self.blown - BLOWN_MAX) * 300
        s += max(0.0, self.black - BLACK_MAX) * 300 + max(0.0, self.crushed - CRUSHED_MAX) * 200
        s += max(0.0, MEAN_LOW - self.mean) * 0.8 + max(0.0, self.mean - MEAN_HIGH) * 0.8
        return round(s, 1)


def _luma(rgb):
    import numpy as np
    a = rgb.astype(np.float32)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def measure(image, name: str = "") -> Exposure:
    """Exposure of one image (a path or a PIL image), measured at 1280 x 720."""
    import numpy as np
    from PIL import Image
    im = Image.open(image) if isinstance(image, (str, Path)) else image
    im = im.convert("RGB")
    if im.size != (1280, 720):
        im = im.resize((1280, 720), Image.BILINEAR)
    rgb = np.asarray(im)
    y = _luma(rgb)
    h, w = y.shape
    blocks = y[: h - h % BLOCK, : w - w % BLOCK].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).mean(axis=(1, 3))
    p05, p50, p95 = np.percentile(y, [5, 50, 95])
    mr, mb = float(rgb[..., 0].mean()), float(rgb[..., 2].mean())
    return Exposure(
        name=name or (Path(image).stem if isinstance(image, (str, Path)) else ""),
        mean=round(float(y.mean()), 1), p05=round(float(p05), 1), p50=round(float(p50), 1),
        p95=round(float(p95), 1), white=round(float((y >= WHITE).mean()), 4),
        black=round(float((y <= BLACK).mean()), 4), blown=round(float((blocks >= BLOWN_BLOCK).mean()), 4),
        crushed=round(float((blocks <= CRUSHED_BLOCK).mean()), 4), warmth=round(mr / max(mb, 1.0), 3),
        path=str(image) if isinstance(image, (str, Path)) else "")


def mask(image, out: Path) -> Path:
    """The image dimmed, with near-white pixels painted red and near-black ones blue."""
    import numpy as np
    from PIL import Image
    im = Image.open(image).convert("RGB")
    rgb = np.asarray(im).astype(np.float32)
    y = _luma(rgb)
    vis = rgb * 0.5
    vis[y >= WHITE] = (255, 30, 30)
    vis[y <= BLACK] = (40, 80, 255)
    Image.fromarray(vis.astype(np.uint8)).save(out)
    return Path(out)


def groups_in(paths: Iterable) -> dict[str, dict[str, Path]]:
    """Shot images under ``paths`` (folders of .png/.jpg/.tga, or single images), grouped by
    map: ``local/csgo/cs_nuke/shots`` is group ``cs_nuke``, ``dist/stock_shots/mohdm1`` is
    ``mohdm1``, loose files are group ``""``. Returns group -> shot name -> path."""
    out: dict[str, dict[str, Path]] = {}
    for p in map(Path, paths):
        if p.is_dir():
            group = p.parent.name if p.name == "shots" else p.name
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in (".png", ".jpg", ".tga"))
        else:
            group, files = "", [p]
        for f in files:
            out.setdefault(group, {})[f.stem] = f
    return out


def measure_all(images: dict[str, Path]) -> list[Exposure]:
    return [measure(p, name) for name, p in images.items()]


def summary(rows: Sequence[Exposure], name: str = "") -> dict:
    """One map (or one group of shots): averages, worst shot and flag counts."""
    if not rows:
        return {"name": name, "shots": 0}
    n = len(rows)
    flagged = [r for r in rows if r.flags]
    worst = max(rows, key=lambda r: r.score)
    return {
        "name": name, "shots": n, "mean": round(sum(r.mean for r in rows) / n, 1),
        "mean_sd": round(math.sqrt(sum((r.mean - sum(x.mean for x in rows) / n) ** 2 for r in rows) / n), 1),
        "white": round(sum(r.white for r in rows) / n, 4), "black": round(sum(r.black for r in rows) / n, 4),
        "blown": round(sum(r.blown for r in rows) / n, 4), "crushed": round(sum(r.crushed for r in rows) / n, 4),
        "warmth": round(sum(r.warmth for r in rows) / n, 3), "flagged": len(flagged),
        "score": round(sum(r.score for r in rows), 1), "worst": f"{worst.name} ({worst.score})",
    }


HEADER = f"{'shot':34s} {'mean':>5s} {'p05':>5s} {'p50':>5s} {'p95':>5s} {'white%':>6s} {'black%':>6s} " \
         f"{'blown%':>6s} {'crush%':>6s} {'R/B':>5s} {'score':>6s}  flags"


def line(r: Exposure) -> str:
    return (f"{r.name[:34]:34s} {r.mean:5.0f} {r.p05:5.0f} {r.p50:5.0f} {r.p95:5.0f} {r.white * 100:6.1f} "
            f"{r.black * 100:6.1f} {r.blown * 100:6.1f} {r.crushed * 100:6.1f} {r.warmth:5.2f} {r.score:6.1f}  "
            f"{' '.join(r.flags)}")


def table(rows: Sequence[Exposure], worst_first: bool = True) -> str:
    rows = sorted(rows, key=lambda r: -r.score) if worst_first else list(rows)
    return "\n".join([HEADER] + [line(r) for r in rows])


def map_table(groups: dict[str, Sequence[Exposure]]) -> str:
    out = [f"{'map':16s} {'shots':>5s} {'mean':>5s} {'sd':>5s} {'white%':>6s} {'black%':>6s} {'blown%':>6s} "
           f"{'crush%':>6s} {'R/B':>5s} {'flag':>4s} {'score':>6s}  worst"]
    for name, rows in groups.items():
        s = summary(rows, name)
        if not s["shots"]:
            continue
        out.append(f"{name[:16]:16s} {s['shots']:5d} {s['mean']:5.0f} {s['mean_sd']:5.0f} {s['white'] * 100:6.1f} "
                   f"{s['black'] * 100:6.1f} {s['blown'] * 100:6.1f} {s['crushed'] * 100:6.1f} {s['warmth']:5.2f} "
                   f"{s['flagged']:4d} {s['score']:6.1f}  {s['worst']}")
    return "\n".join(out)


def save(rows: Sequence[Exposure], out: Path, name: str = "") -> Path:
    data = {"summary": summary(rows, name), "shots": [dict(asdict(r), flags=r.flags, score=r.score) for r in rows]}
    Path(out).write_text(json.dumps(data, indent=1))
    return Path(out)


def load(path: Path) -> list[Exposure]:
    data = json.loads(Path(path).read_text())
    keys = Exposure.__dataclass_fields__.keys()
    return [Exposure(**{k: v for k, v in s.items() if k in keys}) for s in data["shots"]]


def compare(before: Sequence[Exposure], after: Sequence[Exposure]) -> str:
    """Per shot: mean and white/black shares before -> after (shots matched by name)."""
    b = {r.name: r for r in before}
    out = [f"{'shot':34s} {'mean':>11s} {'white%':>13s} {'black%':>13s} {'score':>13s}"]
    for r in after:
        o = b.get(r.name)
        if o is None:
            continue
        out.append(f"{r.name[:34]:34s} {o.mean:4.0f} ->{r.mean:4.0f} {o.white * 100:5.1f} ->{r.white * 100:5.1f} "
                   f"{o.black * 100:5.1f} ->{r.black * 100:5.1f} {o.score:5.1f} ->{r.score:5.1f}")
    return "\n".join(out)


STOCK_MAPS = ("dm/mohdm1", "dm/mohdm2", "dm/mohdm3", "dm/mohdm5", "dm/mohdm6", "dm/mohdm7",
              "obj/obj_team1", "obj/obj_team2", "obj/obj_team3", "obj/obj_team4")


def stock_shots(maps: Sequence[str] = STOCK_MAPS, per_map: int = 9, out_dir: Optional[Path] = None,
                skip_done: bool = True) -> dict[str, dict[str, Path]]:
    """Screenshots of stock maps from cameras chosen like a conversion's (``auto_cameras``
    on the EA ``.map`` source in ``reference/aa``), saved under ``out_dir/<map>/``: the
    reference for what a finished MOHAA map's exposure looks like."""
    import shutil

    from . import config, game
    from .mapfile import MapFile
    from .source.convert import auto_cameras
    out_dir = Path(out_dir or config.REPO / "dist" / "stock_shots")
    res: dict[str, dict[str, Path]] = {}
    for path in maps:
        m = path.rsplit("/", 1)[-1]
        src = config.REPO / "reference" / "aa" / f"{m}.map"   # (mohdm4 has no source: not shot)
        d = out_dir / m
        if not src.is_file() or (skip_done and d.is_dir() and any(d.iterdir())):
            continue
        cams = auto_cameras(MapFile.load(str(src)), per_map)
        run = game.run([], path, cams, run_name=f"stock_{m}", gametype=1 if path.startswith("dm/") else 4,
                       timeout=300 + 3 * len(cams))
        d.mkdir(parents=True, exist_ok=True)
        res[m] = {}
        for k, p in run.screenshots.items():
            dst = d / f"{k}.png"
            shutil.copy2(p, dst)
            res[m][k] = dst
    return res


def against(ref: Path, runs: Sequence[Path]) -> tuple[list[dict], str]:
    """Shots of each run (folders) against reference shots of the same cameras (``ref``,
    e.g. ``local/csgo/<name>/csgo_ref`` from ``mohkit csgo-ref``; matched by file stem).
    Returns per-run summaries (mean brightness, mean absolute error and correlation of
    per-camera means with the reference) and a printable table."""
    import numpy as np
    refs = {p.stem: measure(p) for p in sorted(Path(ref).iterdir()) if p.suffix.lower() in (".png", ".jpg", ".tga")}
    rows = [{p.stem: measure(p) for p in sorted(Path(r).iterdir()) if p.suffix.lower() in (".png", ".jpg", ".tga")}
            for r in runs]
    names = [k for k in refs if all(k in r for r in rows)]
    lines = [f"{'camera':22s} {'ref':>5s} " + " ".join(f"{Path(r).parent.name[:10]:>10s}" for r in runs)]
    for k in names:
        lines.append(f"{k[:22]:22s} {refs[k].mean:5.0f} " + " ".join(f"{r[k].mean:10.0f}" for r in rows))
    out = []
    R = np.array([refs[k].mean for k in names])
    for r, path in zip(rows, runs):
        M = np.array([r[k].mean for k in names])
        out.append({"run": str(path), "cameras": len(names), "ref_mean": round(float(R.mean()), 1) if len(R) else 0,
                    "mean": round(float(M.mean()), 1) if len(M) else 0,
                    "mae": round(float(np.abs(M - R).mean()), 1) if len(R) else 0,
                    "corr": round(float(np.corrcoef(R, M)[0, 1]), 2) if len(R) > 2 else 0.0})
    lines += [f"== {o['run']}: mean {o['mean']} (ref {o['ref_mean']}), mean |error| {o['mae']}, "
              f"corr {o['corr']} over {o['cameras']} cameras" for o in out]
    return out, "\n".join(lines)


def triple_sheet(folders: Sequence[tuple[str, Path]], cameras: Sequence[str], out: Path,
                 width: int = 560) -> Path:
    """Side-by-side rows, one per camera (stem prefix such as ``05_``), one column per
    labelled folder (e.g. CS:GO / before / after)."""
    from PIL import Image, ImageDraw
    h = round(width * 9 / 16)
    sheet = Image.new("RGB", (len(folders) * width, len(cameras) * (h + 18)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for r, cam in enumerate(cameras):
        for c, (label, folder) in enumerate(folders):
            p = next((q for q in sorted(Path(folder).glob(f"{cam}*")) if q.suffix.lower() in (".png", ".jpg")), None)
            x, y = c * width, r * (h + 18)
            if p is not None:
                sheet.paste(Image.open(p).convert("RGB").resize((width, h)), (x, y + 18))
            d.text((x + 4, y + 3), f"{label} {p.stem if p else cam}", fill=(255, 220, 120))
    sheet.save(out)
    return Path(out)
