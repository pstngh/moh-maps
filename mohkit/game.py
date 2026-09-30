"""Run OpenMoHAA against a map package: screenshots, bot matches, log triage.

Every run uses an isolated base and home so neither the user's mods nor their
config affect the result::

    <build_dir>/gamebase/        openmohaa + libs + main/Pak*.pk3 (retail only, symlinks)
    <build_dir>/homes/<run>/main/ the candidate PK3(s), harness cfg, qconsole.log, screenshots

(``build_dir`` defaults to the user cache dir, e.g. ~/Library/Caches/mohkit/build.)

The harness is a plain cfg executed after ``devmap``. ``wait N`` waits N
milliseconds (a bare ``wait`` is one command-buffer pass). Cheat commands
(``tele``, ``face``) need ``cheats 1`` *and* ``thereisnomonkey 1``: without the
latter the game silently resets ``cheats`` to 0. ``saveshot`` renders one frame
without HUD/menus/spectator text and writes ``screenshots/<name>.tga``.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from . import config as _config

Vec3 = tuple[float, float, float]

# Lines that appear in every stock run and say nothing about the candidate map.
BENIGN = (
    "LOCALIZATION ERROR", "NET_JoinMulticast6", "Loaded symbol", "TIKI_InitTiki: Couldn't load models/player/",
    "Tiki:LoadFile Couldn't load models/player/", "callvote.cfg", "radar_allies", "radar_axis",
)
PROBLEM_RE = re.compile(r"warning|error|couldn't|could not|can't|cannot|missing|not found|\^~\^~\^|failed", re.I)
KILL_RE = re.compile(r" was (?:killed|shot|blown|sniped|bashed|gunned)| killed | died|was .* by ", re.I)


@dataclass
class Shot:
    """A camera: origin is the *eye* position, angles are pitch, yaw, roll in degrees.

    ``fov`` is the game's fov value (default 80): the horizontal field of view of a
    4:3 view. Wider screens keep the same vertical angle and see more at the sides
    (``cgame/cg_view.c`` CG_CalcFov), so fov 80 is 64.6° vertical at any aspect.
    Use ``fov_from_vertical`` to match a photo.
    """
    name: str
    origin: Vec3
    angles: tuple[float, float, float] = (0.0, 0.0, 0.0)
    fov: Optional[float] = None

    @classmethod
    def looking_at(cls, name: str, eye: Vec3, target: Vec3, fov: Optional[float] = None) -> "Shot":
        dx, dy, dz = target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]
        yaw = math.degrees(math.atan2(dy, dx))
        pitch = -math.degrees(math.atan2(dz, math.hypot(dx, dy)))
        return cls(name, eye, (pitch, yaw, 0.0), fov)


def fov_from_vertical(vfov_deg: float) -> float:
    """Game fov value that gives a vertical field of view of ``vfov_deg`` degrees."""
    return math.degrees(2 * math.atan(math.tan(math.radians(vfov_deg) / 2) * 4 / 3))


def vertical_fov(fov: float = 80.0) -> float:
    """Vertical field of view (degrees) of the game fov value ``fov``."""
    return math.degrees(2 * math.atan(math.tan(math.radians(fov) / 2) * 3 / 4))


@dataclass
class RunResult:
    home: Path
    log: str
    screenshots: dict[str, Path] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    kills: int = 0
    seconds: float = 0.0
    exit_code: Optional[int] = None
    timed_out: bool = False

    def summary(self) -> str:
        lines = [f"run {self.home.name}: {self.seconds:.0f}s exit={self.exit_code}"
                 f"{' TIMEOUT' if self.timed_out else ''} shots={len(self.screenshots)} kills={self.kills}"]
        for p in self.problems[:30]:
            lines.append(f"  ! {p}")
        return "\n".join(lines)


def gamebase(cfg: Optional[_config.Config] = None) -> Path:
    """Isolated base dir: engine binaries plus retail paks only."""
    cfg = cfg or _config.load()
    if not cfg.openmohaa:
        raise RuntimeError("OpenMoHAA executable not found (set MOHKIT_OPENMOHAA)")
    base = Path(cfg.build_dir) / "gamebase"
    main = base / "main"
    main.mkdir(parents=True, exist_ok=True)
    engine_dir = Path(cfg.openmohaa).parent
    for f in engine_dir.iterdir():
        if f.is_file() and (f.suffix in (".dylib", ".so", ".dll") or f.name == Path(cfg.openmohaa).name):
            _link(f, base / f.name)
    for pak in cfg.retail_paks():
        _link(pak, main / pak.name)
    return base


def _link(src: Path, dst: Path) -> None:
    if dst.is_symlink() or dst.exists():
        if dst.is_symlink() and os.readlink(dst) == str(src):
            return
        dst.unlink()
    try:
        os.symlink(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def camera_commands(shot: Shot) -> list[str]:
    """Console commands that put the local player's view at ``shot``.

    Requires ``cheats 1`` (set by ``run``). ``tele`` moves the player origin (feet);
    ``face`` sets the view angles, ``fov`` the field of view. The eye is ~82 units above the origin standing,
    so subtract that to place the eye where requested.
    """
    x, y, z = shot.origin
    p, yw, r = shot.angles
    return [f"tele {x:.0f} {y:.0f} {z - EYE_HEIGHT:.0f}", f"face {p:.1f} {yw:.1f} {r:.1f}",
            f"fov {shot.fov if shot.fov is not None else 80:g}"]


EYE_HEIGHT = 82.0
FPS = 60


def frames(ms: int) -> list[str]:
    """Harness lines that wait ~``ms`` of frames. A bare ``wait`` holds the buffer for one
    ``Cbuf_Execute`` pass, and there are two passes per frame (``qcommon/common.c``)."""
    return ["wait"] * max(2, 2 * round(ms * FPS / 1000))


def run(pk3s: Sequence[Path], map_name: str, shots: Sequence[Shot] = (), *, gametype: int = 1,
        bots: int = 0, match_seconds: float = 0, width: int = 1280, height: int = 720,
        settle_ms: int = 2000, shot_ms: int = 700, cvars: Optional[dict[str, str]] = None,
        extra_commands: Iterable[str] = (), run_name: Optional[str] = None, timeout: float = 300,
        cfg: Optional[_config.Config] = None) -> RunResult:
    """Launch OpenMoHAA on ``map_name`` (e.g. ``dm/mymap``) with only retail data + ``pk3s``.

    Takes one screenshot per ``shot`` (or one from the spawn point if none), optionally
    lets ``bots`` fight for ``match_seconds``, then quits.
    """
    cfg = cfg or _config.load()
    base = gamebase(cfg)
    name = run_name or map_name.replace("/", "_")
    home = Path(cfg.build_dir) / "homes" / name
    if home.exists():
        shutil.rmtree(home)
    main = home / "main"
    main.mkdir(parents=True)
    for pk3 in pk3s:
        shutil.copy2(pk3, main / Path(pk3).name)

    # ui_hud must be issued after the map loads (CG_Init turns it back on). `wait N` subtracts
    # each frame's duration, so one long loading frame can use up the whole wait; bare
    # `wait`s count frames instead (com_maxfps below), which loading can't consume.
    # A map with its own loading menu (stock mohdm1) waits for its "continue" button with
    # the local server paused when sv_maxclients <= 1 (UI_EndLoad, client/cl_ui.cpp):
    # `finishloadingscreen` dismisses it and is harmless otherwise.
    lines: list[str] = frames(1500) + ["finishloadingscreen", "ui_hud 0", "ui_crosshair 0", "ui_compass 0",
                                       "ui_gmbox 0", "ui_minicon 0", "cg_drawviewmodel 0", "fps 0", "cg_lagometer 0"]
    lines += list(extra_commands)
    lines += frames(settle_ms)
    shot_names = []
    if not shots:
        lines += ["saveshot spawn", "wait 300"]
        shot_names.append("spawn")
    for i, s in enumerate(shots):
        nm = f"{i:02d}_" + re.sub(r"[^A-Za-z0-9_-]", "_", s.name)
        # tele/face round-trip through the 20 Hz server: set, wait, set again, then capture.
        lines += camera_commands(s) + [f"wait {shot_ms}"] + camera_commands(s) + ["wait 300", f"saveshot {nm}", "wait 300"]
        shot_names.append(nm)
    if bots:
        # Bots join only after the cameras: with other players present the local
        # spectator can end up following one, and every shot turns third-person.
        lines += [f"sv_numbots {bots}"]
    if match_seconds:
        lines += [f"wait {int(match_seconds * 1000)}"]
    lines += ["quit"]
    (main / "harness.cfg").write_text("\n".join(lines) + "\n")

    sets = {
        "fs_homepath": str(home), "fs_basepath": str(base), "com_updatecheck_enabled": "0",
        "r_fullscreen": "0", "r_mode": "-1", "r_customwidth": str(width), "r_customheight": str(height),
        "cl_playintro": "0", "logfile": "2", "developer": "1", "cheats": "1", "thereisnomonkey": "1", "g_gametype": str(gametype),
        "sv_maxbots": str(bots), "sv_numbots": "0", "name": "mohkit", "com_maxfps": str(FPS),
        "s_volume": "0", "s_musicvolume": "0",
    }
    sets.update(cvars or {})
    argv = [cfg.openmohaa]
    for k, v in sets.items():
        argv += ["+set", k, v]
    argv += ["+devmap", map_name, "+exec", "harness.cfg"]

    t0 = time.time()
    timed_out, rc = False, None
    with open(home / "stdout.txt", "wb") as out:
        proc = subprocess.Popen(argv, cwd=str(Path(cfg.openmohaa).parent), stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
    res = RunResult(home, "", seconds=time.time() - t0, exit_code=rc, timed_out=timed_out)
    log_path = main / "qconsole.log"
    res.log = log_path.read_text("latin-1", "replace") if log_path.exists() else (home / "stdout.txt").read_text("latin-1", "replace")
    shots_dir = main / "screenshots"
    for nm in shot_names:
        f = next((shots_dir / (nm + ext) for ext in (".tga", ".jpg") if (shots_dir / (nm + ext)).exists()), None)
        if f is not None:
            res.screenshots[nm] = _to_png(f, nm)
    res.problems = triage(res.log)
    res.kills = sum(1 for line in res.log.splitlines() if KILL_RE.search(line))
    return res


def _to_png(tga: Path, name: str) -> Path:
    try:
        from PIL import Image
    except ImportError:
        return tga
    out = tga.with_suffix(".png")
    Image.open(tga).convert("RGB").save(out)
    return out


def triage(log: str) -> list[str]:
    seen, out = set(), []
    for line in log.splitlines():
        s = re.sub(r"^\[[^\]]*\]\s*", "", line).strip()
        if not s or any(b in s for b in BENIGN) or not PROBLEM_RE.search(s):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def contact_sheet(images: dict[str, Path], out: Path, cols: int = 3, thumb_w: int = 640) -> Optional[Path]:
    """Tile screenshots into one labelled PNG (needs Pillow)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    ims = [(k, Image.open(v).convert("RGB")) for k, v in images.items()]
    if not ims:
        return None
    w = thumb_w
    h = int(ims[0][1].height * w / ims[0][1].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 20)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, (k, im) in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * (h + 20)
        sheet.paste(im.resize((w, h)), (x, y + 20))
        d.text((x + 6, y + 4), k, fill=(255, 220, 120))
    sheet.save(out)
    return out


def compare(reference: Path, shot: Path, out: Path, height: int = 540,
            labels: tuple[str, str] = ("reference", "mohaa")) -> Path:
    """Side-by-side check for recreating a scene from a picture.

    Writes ``out`` with three panels at the same height: the reference, the game
    shot, and a 50/50 blend (edges that line up in the blend mean the camera and the
    geometry match). The reference is centre-cropped to the shot's aspect ratio;
    render the shot at the reference's aspect (``run(width=, height=)``) to avoid that.
    """
    from PIL import Image, ImageDraw
    ref = Image.open(reference).convert("RGB")
    got = Image.open(shot).convert("RGB")
    aspect = got.width / got.height
    if abs(ref.width / ref.height - aspect) > 0.01:
        if ref.width / ref.height > aspect:
            w = round(ref.height * aspect)
            ref = ref.crop(((ref.width - w) // 2, 0, (ref.width - w) // 2 + w, ref.height))
        else:
            h = round(ref.width / aspect)
            ref = ref.crop((0, (ref.height - h) // 2, ref.width, (ref.height - h) // 2 + h))
    w = round(height * aspect)
    ref, got = ref.resize((w, height), Image.LANCZOS), got.resize((w, height), Image.LANCZOS)
    blend = Image.blend(ref, got, 0.5)
    sheet = Image.new("RGB", (3 * w, height + 20), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(((ref, labels[0]), (got, labels[1]), (blend, "blend"))):
        sheet.paste(im, (i * w, 20))
        d.text((i * w + 6, 4), label, fill=(255, 220, 120))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out
