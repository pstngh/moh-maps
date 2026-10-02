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
# "No free spots open in skel cache": more than 1,024 SKDs, props past it never load
# (staticmerge keeps prop SKDs at 600); it matched none of the other words.
PROBLEM_RE = re.compile(r"warning|error|couldn't|could not|can't|cannot|missing|not found|\^~\^~\^|failed"
                        r"|no free spots|server crashed|backtrace", re.I)
# The harness player's join line: absent when the map never loaded (an ERR_DROP back to the
# menu exits 0 after ~16 s with every shot of the menu or one spot: 2026-09-30, cs_dust2's
# "Server crashed: LoadTGA: Only type 2 ...").
JOINED_RE = re.compile(r"has entered the battle")
# Kill messages only: falls ("bot4 cratered") and other self-inflicted deaths are not counted,
# so maps with drops read low (de_rats: 13 counted, ~19 deaths).
KILL_RE = re.compile(r" was (?:killed|shot|blown|sniped|bashed|gunned)| killed | died|was .* by ", re.I)


@dataclass
class Shot:
    """A camera: origin is the *eye* position, angles are pitch, yaw, roll in degrees.

    ``fov`` is the game's fov value (default 80): the horizontal field of view of a
    4:3 view. Wider screens keep the same vertical angle and see more at the sides
    (``cgame/cg_view.c`` CG_CalcFov), so fov 80 is 64.4° vertical at any aspect.
    Use ``fov_from_vertical`` to match a photo. The engine draws 65..120 only (OpenMoHAA
    clamps ``cg_fov``); a narrower ``fov`` is rendered at 65 and centre-cropped (a digital
    zoom, so it is softer), and a wider one is drawn at 120.
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
    perf: dict[str, dict] = field(default_factory=dict)   # camera -> parse_perf() (run(perf_ms=...))
    loaded: bool = True       # the harness player entered the game (JOINED_RE)

    def summary(self) -> str:
        crashed = self.exit_code is not None and self.exit_code < 0
        lines = [f"run {self.home.name}: {self.seconds:.0f}s exit={self.exit_code}"
                 f"{' TIMEOUT' if self.timed_out else ''}{' CRASHED' if crashed else ''}"
                 f"{'' if self.loaded else ' NOT-LOADED'} shots={len(self.screenshots)} kills={self.kills}"]
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
    ``face`` sets the view angles. The eye is ~82 units above the origin standing,
    so subtract that to place the eye where requested.

    The field of view is the client cvar ``cg_fov``: unless the player is zoomed or in a
    script camera, cgame uses it and ignores the server's ``fov`` command
    (``cgame/cg_predict.c``), and clamps it to 65..120 (``cgame/cg_view.c``).
    """
    x, y, z = shot.origin
    p, yw, r = shot.angles
    return [f"tele {x:.0f} {y:.0f} {z - EYE_HEIGHT:.0f}", f"face {p:.1f} {yw:.1f} {r:.1f}",
            f"cg_fov {drawn_fov(shot.fov):g}"]


FOV_MIN, FOV_MAX = 65.0, 120.0  # OpenMoHAA clamps cg_fov to this range every frame


def drawn_fov(fov: Optional[float]) -> float:
    """The fov the engine actually draws for a requested ``fov``."""
    return min(FOV_MAX, max(FOV_MIN, 80.0 if fov is None else fov))


def zoom_crop(fov: float, drawn: float) -> float:
    """Fraction of the frame (each axis) that shows ``fov`` when the engine drew ``drawn``."""
    return math.tan(math.radians(fov) / 2) / math.tan(math.radians(drawn) / 2)


EYE_HEIGHT = 82.0
FPS = 60
MAX_PLUS_COMMANDS = 32   # MAX_CONSOLE_LINES, qcommon/common.c

# Retail's "high" detail preset (Pak0.pk3:high.cfg) with full-size textures and blob shadows
# (its stencil shadows, cg_shadows 2, darken the whole frame about 3x in OpenMoHAA). A fresh
# OpenMoHAA home gets low/safe-mode values instead (r_picmip 2: quarter-size textures;
# r_fastentlight 1: models lit from the light grid, not by the sun and lights, so props near
# the floor sample grid points in solid and render black; r_subdivisions 20: coarse curves).
# They go in the home's autoexec.cfg, which Com_Init execs before the renderer starts (retail's
# own autoexec.cfg is never found there: "couldn't exec autoexec.cfg"). Not as +set: the command
# line holds at most 32 "+" commands (MAX_CONSOLE_LINES, qcommon/common.c) and silently drops
# the rest, +devmap included.
#
# r_primitives 2 draws each batch with one glDrawElements. The default 0 picks it only with
# GL_EXT_compiled_vertex_array, which Apple's GL (2.1 on Metal) lacks, and otherwise sends
# every triangle strip as its own glBegin/glEnd (R_DrawElements, renderergl1/tr_shade.c):
# one Metal draw per strip, ~150 ns per prop vertex, so de_inferno ran at 6 fps instead of
# 84 (same image). Players' configs usually have it (the owner's omconfig.cfg does).
QUALITY_CVARS = {
    "r_primitives": "2", "r_picmip": "0", "r_fastentlight": "0", "r_fastdlights": "0", "r_subdivisions": "4",
    "r_lodscale": "0.55", "r_lodcap": "0.55", "r_lodviewmodelcap": "0.65", "cg_effectdetail": "0.8",
    "ter_error": "9", "ter_maxlod": "4", "cg_shadows": "1", "cg_marks_add": "1",
    "r_drawstaticdecals": "1", "r_colorbits": "32", "r_texturebits": "32",
}


def frames(ms: int) -> list[str]:
    """Harness lines that wait ~``ms`` of frames. A bare ``wait`` holds the buffer for one
    ``Cbuf_Execute`` pass, and there are two passes per frame (``qcommon/common.c``)."""
    return ["wait"] * max(2, 2 * round(ms * FPS / 1000))


PERF_FRAME_RE = re.compile(r"frame:\s*\d+ all:\s*(\d+) sv:\s*-?\d+ ev:\s*-?\d+ cl:\s*-?\d+ gm:\s*(-?\d+) "
                           r"rf:\s*(-?\d+) bk:\s*(-?\d+)")
PERF_SPEEDS_RE = re.compile(r"(\d+)/(\d+) shaders/surfs (\d+) leafs (\d+) verts (\d+)/(\d+) tris")
PERF_MARK = "mohkit-perf"


def perf_commands(name: str, ms: int, toggles: Sequence[tuple[str, str]] = ()) -> list[str]:
    """Harness lines that time ``ms`` of uncapped frames at the current view: ``com_speeds 1``
    prints each frame's milliseconds (``all``: server + events + client, the renderer
    front end ``rf`` and back end ``bk``; ``qcommon/common.c`` Com_Frame), ``r_speeds 1``
    its shaders, surfaces, leafs, vertices and triangles (``renderergl1/tr_cmds.c``).
    ``com_maxfps 0`` still waits 1 ms between frames (``minMsec``), so the ceiling is
    ~1000 fps. Each ``(cvar, value)`` in ``toggles`` repeats the timing with that cvar
    set (e.g. ``r_drawstaticmodels 0``: what the props cost) and restored to 1."""
    out = ["com_maxfps 0", "wait 500"]
    for tag, (cvar, value) in [("base", ("", ""))] + [(f"{c}={v}", (c, v)) for c, v in toggles]:
        if cvar:
            out += [f"{cvar} {value}", "wait 300"]
        out += ["r_speeds 1", "com_speeds 1", f"echo {PERF_MARK} begin {name} {tag} {ms}", f"wait {ms}",
                f"echo {PERF_MARK} end", "com_speeds 0", "r_speeds 0"]
        if cvar:
            out += [f"{cvar} 1"]
    return out + [f"com_maxfps {FPS}", "wait 200"]


def parse_perf(log: str) -> dict[str, dict]:
    """``{camera: {tag: stats}}`` from the frames ``perf_commands`` timed. Stats: frame count,
    ``fps`` (frames per second of measured frame time; Sys_Milliseconds is whole ms, so a
    mean over many frames), ``wall_fps`` (frames in the window: includes the 1 ms floor
    between frames, so it tops out near 1000), ``ms`` mean, ``p90_ms``, ``rf``/``bk`` renderer
    front/back end ms (``bk`` is only the last flush, the swap: docs/testing.md), and the mean
    ``surfs``, ``leafs``, ``verts``, ``tris`` drawn. The first and last two frames of each
    window are dropped (the toggling frames)."""
    out: dict[str, dict] = {}
    cur, frames, speeds = None, [], []
    for line in log.splitlines():
        if PERF_MARK in line and " begin " in line:
            parts = line.split(PERF_MARK + " begin ", 1)[1].split()
            cur, frames, speeds = (parts[0], parts[1] if len(parts) > 1 else "base",
                                   int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0), [], []
            continue
        if cur is None:
            continue
        if PERF_MARK in line and line.rstrip().endswith(" end"):
            fr, sp = frames[2:-2] or frames, speeds[2:-2] or speeds
            if fr:
                alls = sorted(f[0] for f in fr)
                n = len(fr)
                mean = sum(alls) / n
                st = {"frames": n, "ms": round(mean, 2), "fps": round(1000.0 / max(mean, 1e-3), 1),
                      "wall_fps": round(len(frames) * 1000.0 / cur[2], 1) if cur[2] else None,
                      "p90_ms": alls[min(n - 1, int(n * 0.9))],
                      "rf": round(sum(f[2] for f in fr) / n, 2), "bk": round(sum(f[3] for f in fr) / n, 2),
                      "gm": round(sum(f[1] for f in fr) / n, 2)}
                if sp:
                    m = len(sp)
                    for k, i in (("shaders", 0), ("surfs", 1), ("leafs", 2), ("verts", 3), ("tris", 4)):
                        st[k] = round(sum(s[i] for s in sp) / m)
                out.setdefault(cur[0], {})[cur[1]] = st
            cur = None
            continue
        m = PERF_FRAME_RE.search(line)
        if m:
            frames.append(tuple(int(g) for g in m.groups()))
            continue
        m = PERF_SPEEDS_RE.search(line)
        if m:
            g = [int(v) for v in m.groups()]
            speeds.append((g[0], g[1], g[2], g[3], g[5]))
    return out


def perf_table(perf: dict[str, dict]) -> str:
    """One line per camera and toggle: fps, frame ms, renderer ms, what was drawn."""
    rows = [f"{'camera':28} {'tag':22} {'fps':>6} {'wall':>5} {'ms':>6} {'p90':>4} {'rf':>5} {'bk':>5} "
            f"{'surfs':>6} {'leafs':>6} {'verts':>8} {'tris':>8}"]
    for cam, tags in perf.items():
        for tag, s in tags.items():
            rows.append(f"{cam[:28]:28} {tag[:22]:22} {s['fps']:6.0f} {s.get('wall_fps') or 0:5.0f} {s['ms']:6.2f} "
                        f"{s['p90_ms']:4d} {s['rf']:5.1f} "
                        f"{s['bk']:5.1f} {s.get('surfs', 0):6d} {s.get('leafs', 0):6d} {s.get('verts', 0):8d} "
                        f"{s.get('tris', 0):8d}")
    base = [t["base"]["ms"] for t in perf.values() if "base" in t]
    if base:
        ms = sorted(base)
        rows.append(f"== {len(base)} cameras: mean {1000 * len(ms) / sum(ms):.0f} fps (frame-time mean), "
                    f"worst {1000 / ms[-1]:.0f} fps, median {1000 / ms[len(ms) // 2]:.0f} fps")
    return "\n".join(rows)


def run(pk3s: Sequence[Path], map_name: str, shots: Sequence[Shot] = (), *, gametype: int = 1,
        bots: int = 0, match_seconds: float = 0, width: int = 1280, height: int = 720,
        settle_ms: int = 2000, shot_ms: int = 700, cvars: Optional[dict[str, str]] = None,
        extra_commands: Iterable[str] = (), run_name: Optional[str] = None, timeout: float = 300,
        perf_ms: int = 0, perf_toggles: Sequence[tuple[str, str]] = (), screenshots: bool = True,
        cfg: Optional[_config.Config] = None) -> RunResult:
    """Launch OpenMoHAA on ``map_name`` (e.g. ``dm/mymap``) with only retail data + ``pk3s``.

    Takes one screenshot per ``shot`` (or one from the spawn point if none), optionally
    lets ``bots`` fight for ``match_seconds``, then quits. With ``perf_ms``, each camera is
    also timed for that long (``perf_commands``, ``perf_toggles``); ``RunResult.perf``
    holds the numbers. ``screenshots=False`` skips the saveshots (timing only).
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
    (main / "autoexec.cfg").write_text("".join(f'seta {k} "{v}"\n' for k, v in QUALITY_CVARS.items()))

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
        if perf_ms:
            lines += perf_commands("spawn", perf_ms, perf_toggles)
    for i, s in enumerate(shots):
        nm = f"{i:02d}_" + re.sub(r"[^A-Za-z0-9_-]", "_", s.name)
        # tele/face round-trip through the 20 Hz server: set, wait, set again, then capture.
        lines += camera_commands(s) + [f"wait {shot_ms}"] + camera_commands(s) + ["wait 300"]
        if screenshots:
            lines += [f"saveshot {nm}", "wait 300"]
            shot_names.append(nm)
        if perf_ms:
            lines += perf_commands(nm, perf_ms, perf_toggles)
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
        # The engine also searches the binary's own folder (fs_apppath, Sys_DefaultAppPath:
        # the player's game dir with every installed pk3) and Steam/GOG installs, after the
        # base path (qcommon/files.cpp FS_InitPathVars). A file the candidate lacks then comes
        # from an installed map, and since x.jpg is tried before x.tga, an installed build's
        # opaque layer-2 JPG hid the candidate's alpha-tested TGA (de_dust2 drew sand
        # everywhere). Pointing them at the base path drops them (duplicates are skipped).
        "fs_apppath": str(base), "fs_steampath": str(base), "fs_gogpath": str(base),
        "fs_microsoftstorepath": str(base),
    }
    sets, moved = fit_command_line(sets, cvars or {})
    if moved:
        with open(main / "autoexec.cfg", "a") as f:
            f.write("".join(f'set {k} "{v}"\n' for k, v in moved.items()))
    argv = [cfg.openmohaa]
    for k, v in sets.items():
        argv += ["+set", k, v]
    argv += ["+devmap", map_name, "+exec", "harness.cfg"]

    if perf_ms:
        timeout += max(1, len(shots)) * (perf_ms + 900) * (1 + len(perf_toggles)) / 1000
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
    by_name = {nm: s for nm, s in zip(shot_names, shots)}
    for nm in shot_names:
        f = next((shots_dir / (nm + ext) for ext in (".tga", ".jpg") if (shots_dir / (nm + ext)).exists()), None)
        if f is not None:
            s = by_name.get(nm)
            crop = zoom_crop(s.fov, FOV_MIN) if s is not None and s.fov is not None and s.fov < FOV_MIN else 1.0
            res.screenshots[nm] = _to_png(f, nm, crop)
    res.problems = triage(res.log)
    res.loaded = bool(JOINED_RE.search(res.log))
    if not res.loaded:
        res.problems.insert(0, "the map never loaded (no 'has entered the battle' in the log)")
    if rc is not None and rc < 0:
        res.problems.insert(0, f"the game crashed (signal {-rc}); see the Backtrace in {home / 'stdout.txt'}")
    res.kills = sum(1 for line in res.log.splitlines() if KILL_RE.search(line))
    if perf_ms:
        res.perf = parse_perf(res.log)
    return res


def fit_command_line(sets: dict[str, str], cvars: dict[str, str], extra: int = 2) -> tuple[dict, dict]:
    """(``+set`` cvars, cvars for autoexec.cfg): ``sets`` updated with ``cvars``, minus the
    caller cvars that don't fit. At most 32 "+" commands fit the command line
    (MAX_CONSOLE_LINES, qcommon/common.c, counting ``extra`` for +devmap and +exec); the rest
    are dropped silently, +devmap included, and the game idles at the console until the
    timeout. autoexec.cfg runs before the renderer starts, so render cvars still apply there;
    ``fs_*`` paths must stay on the command line."""
    sets = {**sets, **cvars}
    overflow = len(sets) + extra - MAX_PLUS_COMMANDS
    if overflow <= 0:
        return sets, {}
    movable = [k for k in cvars if not k.startswith("fs_")][-overflow:]
    if len(movable) < overflow:
        raise ValueError(f"{len(sets) + extra} '+' commands; the engine keeps {MAX_PLUS_COMMANDS}")
    return {k: v for k, v in sets.items() if k not in movable}, {k: sets[k] for k in movable}


def _to_png(tga: Path, name: str, crop: float = 1.0) -> Path:
    """Convert a screenshot to PNG; ``crop`` < 1 keeps that centre fraction, resized back up."""
    try:
        from PIL import Image
    except ImportError:
        return tga
    out = tga.with_suffix(".png")
    im = Image.open(tga).convert("RGB")
    if crop < 0.999:
        w, h = im.size
        cw, ch = w * crop, h * crop
        im = im.resize((w, h), Image.LANCZOS, box=((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2))
    im.save(out)
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


def contact_sheets(images: dict[str, Path], out: Path, per_page: int = 9, cols: int = 3,
                   thumb_w: int = 640) -> list[Path]:
    """``contact_sheet`` in pages of ``per_page`` shots: ``out`` holds the first page,
    later pages are ``<stem>_2.png``, ``<stem>_3.png`` ... (readable at full size)."""
    items = list(images.items())
    pages = []
    for i in range(0, len(items), per_page):
        k = i // per_page
        dest = out if k == 0 else out.with_name(f"{out.stem}_{k + 1}{out.suffix}")
        sheet = contact_sheet(dict(items[i:i + per_page]), dest, cols, thumb_w)
        if sheet:
            pages.append(sheet)
    return pages


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


def shots_ab(a: Sequence[Path], b: Sequence[Path], map_name: str, shots: Sequence[Shot], out: Path,
             labels: tuple[str, str] = ("A", "B"), threshold: int = 40, cvars: Optional[dict[str, str]] = None,
             log=print) -> dict[str, dict]:
    """Shoot ``map_name`` with two pk3 sets from the same cameras and measure what changed:
    per camera the mean of the largest channel difference (0-255) and the share of pixels
    that differ by more than ``threshold``. Writes ``<out>/<camera>_ab.png`` (A | B), a
    contact sheet of the most changed cameras (``ab_sheet.png``) and ``ab.json``. Use it
    for regression checks (an install against the installed build) and for cross-map
    effects (a pk3 alone against all installed ones: 2026-10-02's prop path clash showed
    as 3% changed pixels on cs_cache's truck camera; after the fix 18 of 19 cameras were
    identical). Judge a change against an A-vs-A run of the same set: a conversion's
    overview camera differs between two runs of one pk3 (mean 1.0: the top ~15 rows still
    hold the previous frame, a sky face flickers); the other cameras repeat exactly."""
    import json

    import numpy as np
    from PIL import Image
    _check_set(a), _check_set(b)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tag = map_name.replace("/", "_")
    runs = [run([Path(x) for x in pk3s], map_name, shots, run_name=f"ab_{tag}_{i}", timeout=300 + 3 * len(shots),
                cvars=cvars) for i, pk3s in enumerate((a, b))]
    for r in runs:
        log(r.summary())
    res: dict[str, dict] = {}
    pairs: dict[str, Path] = {}
    for k in runs[0].screenshots:
        if k not in runs[1].screenshots:
            continue
        ia = np.asarray(Image.open(runs[0].screenshots[k]).convert("RGB"), np.float32)
        ib = np.asarray(Image.open(runs[1].screenshots[k]).convert("RGB"), np.float32)
        if ia.shape != ib.shape:
            continue
        d = np.abs(ia - ib).max(2)
        res[k] = {"mean": round(float(d.mean()), 2), "changed_pct": round(float((d > threshold).mean() * 100), 2)}
        pairs[k] = out / f"{k}_ab.png"
        Image.fromarray(np.concatenate([ia, ib], 1).astype(np.uint8)).save(pairs[k])
    res = dict(sorted(res.items(), key=lambda kv: -kv[1]["mean"]))
    (out / "ab.json").write_text(json.dumps({"labels": list(labels), "threshold": threshold,
                                             "a": [str(x) for x in a], "b": [str(x) for x in b],
                                             "cameras": res}, indent=1))
    worst = {f"{k} ({labels[0]} | {labels[1]})": pairs[k] for k in list(res)[:9]}
    if worst:
        contact_sheet(worst, out / "ab_sheet.png", cols=1, thumb_w=1280)
    for k, v in res.items():
        log(f"{k:32s} mean|d| {v['mean']:6.2f}   px>{threshold} {v['changed_pct']:6.2f}%")
    return res


def _check_set(pk3s: Sequence[Path]) -> None:
    names = [Path(x).name.lower() for x in pk3s]
    if len(set(names)) != len(names):
        raise ValueError(f"two pk3s with the same name in one set (one would replace the other): {names}")


def perf_ab(a: Sequence[Path], b: Sequence[Path], map_name: str, shots: Sequence[Shot], out: Path,
            labels: tuple[str, str] = ("A", "B"), rounds: int = 2, ms: int = 2000,
            cvars: Optional[dict[str, str]] = None, log=print) -> dict:
    """Frame rate of two pk3 sets at the same cameras, interleaved A B A B ... for ``rounds``
    (fps only compare within one interleaved run: docs/testing.md "Frame rate"). Per set:
    the frame-time mean over all cameras and rounds as fps, the worst and the median camera;
    per camera both sets' fps. Writes ``<out>/perf_ab.json``."""
    import json
    _check_set(a), _check_set(b)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tag = map_name.replace("/", "_")
    ms_by: list[dict[str, list[float]]] = [{}, {}]
    for r in range(rounds):
        for i, pk3s in enumerate((a, b)):
            res = run([Path(x) for x in pk3s], map_name, shots, run_name=f"perfab_{tag}_{i}", perf_ms=ms,
                      screenshots=False, cvars=cvars, timeout=300 + (3 + ms / 1000) * len(shots))
            log(f"{labels[i]} round {r + 1}: " + res.summary().splitlines()[0])
            for cam, tags in res.perf.items():
                if "base" in tags:
                    ms_by[i].setdefault(cam, []).append(tags["base"]["ms"])
    cams = [c for c in ms_by[0] if c in ms_by[1]]
    summary = {}
    for i in (0, 1):
        per = sorted(sum(ms_by[i][c]) / len(ms_by[i][c]) for c in cams)
        summary[labels[i]] = {"fps": round(1000 * len(per) / sum(per), 1) if per else None,
                              "worst": round(1000 / per[-1], 1) if per else None,
                              "median": round(1000 / per[len(per) // 2], 1) if per else None}
    table = {c: [round(1000 * len(ms_by[i][c]) / sum(ms_by[i][c]), 1) for i in (0, 1)] for c in cams}
    (out / "perf_ab.json").write_text(json.dumps({"labels": list(labels), "rounds": rounds, "ms": ms,
                                                  "cvars": cvars or {}, "summary": summary, "cameras": table},
                                                 indent=1))
    for c, (fa, fb) in table.items():
        log(f"{c:32s} {labels[0]} {fa:7.1f}   {labels[1]} {fb:7.1f}   {fb / fa:5.2f}x")
    for lab, st in summary.items():
        log(f"== {lab}: {st['fps']} fps (frame-time mean over {len(cams)} cameras), worst {st['worst']},"
            f" median {st['median']}")
    return {"summary": summary, "cameras": table}


def measure(reference: Path, shot: Path, regions: dict[str, tuple[int, int, int, int]]) -> dict[str, dict]:
    """Mean colour of named pixel boxes (x0, y0, x1, y1) in both images, and the brightness
    ratio reference/shot: > 1 means the shot is too dark there. Use it to tune lights and
    ambient against a reference. Boxes are in the reference's pixels; the shot is resized
    to the reference's size first."""
    from PIL import Image
    ref = Image.open(reference).convert("RGB")
    got = Image.open(shot).convert("RGB").resize(ref.size)
    out = {}
    for name, box in regions.items():
        a = [sum(c) / len(c) for c in zip(*ref.crop(box).getdata())]
        b = [sum(c) / len(c) for c in zip(*got.crop(box).getdata())]
        out[name] = {"reference": [round(v) for v in a], "shot": [round(v) for v in b],
                     "ratio": round(sum(a) / max(sum(b), 1e-6), 2)}
    return out


# ---------------------------------------------------------------------------- ladder probe

VIEWPOS_RE = re.compile(r"\((-?\d+) (-?\d+) (-?\d+)\) : (-?\d+)\s*$", re.M)  # cgame viewpos output


def ladders_in_bsp(bsp_path: Path) -> list[dict]:
    """Every ``func_ladder`` of a compiled map: origin (on the climb face), facing yaw
    (``angle``, toward the wall) and the world z range of its brushes."""
    from .bsp import BSP
    b = BSP(Path(bsp_path))
    models = b.models()
    out = []
    for e in b.entities():
        if e.get("classname") != "func_ladder" or not e.get("model", "").startswith("*"):
            continue
        o = [float(v) for v in e.get("origin", "0 0 0").split()]
        m = models[int(e["model"][1:])]
        out.append({"origin": o, "angle": float(e.get("angle", "0") or 0),
                    "zmin": o[2] + m["mins"][2], "zmax": o[2] + m["maxs"][2]})
    return out


def ladders_for_probe(bsp_path: Path) -> list[dict]:
    """Ladders to probe in a compiled map: its ``func_ladder``s, plus the CS-style step
    ladders (clip brushes, no entity) listed in the ``report.json`` beside the BSP (a CS:GO
    conversion's ``convert.ladders``)."""
    import json
    out = ladders_in_bsp(bsp_path)
    rep = Path(bsp_path).with_name("report.json")
    if rep.is_file():
        conv = json.loads(rep.read_text()).get("convert", {})
        out += [l for l in conv.get("ladders", []) if l.get("style") == "steps"]
    return out


def ladder_probe(pk3s: Sequence[Path], map_name: str, ladders: Sequence[dict], climb_ms: int = 4000,
                 run_name: Optional[str] = None) -> list[dict]:
    """Climb every ladder as a player and report how far up each one got.

    One game per ladder (a player still on a ladder ignores ``tele``): the local player
    joins a team, is teleported to the foot of the ladder (feet 1 unit above its bottom,
    28 units back from the climb face, or a step ladder's ``probe_start``), looks 50 degrees up toward the wall, taps +use
    (mounts any ladder the view hits, including one hanging over a gap, which walking
    into it never does) and holds +forward to climb; ``viewpos`` before and every 500 ms
    while climbing gives the climb: the highest point reached, since a player who gets off
    at the top walks on and may leave the ledge (mirage's leaning ladder: on the upper floor
    after 2.2 s, back at floor level 4 s in). ``global/mike_torso.st`` USE_LADDER,
    ``docs/reference/engine.md`` §1.3. Verified on stock mohdm2: 325 units in 4 s.
    A step ladder that hangs over the floor (``hang`` > 40 in its report entry: climbed
    down, or caught from a jump) starts in the air at the column with +forward already held."""
    out = []
    for i, l in enumerate(ladders):
        yaw = math.radians(l["angle"])
        x = l["origin"][0] - math.cos(yaw) * 28
        y = l["origin"][1] - math.sin(yaw) * 28
        z = l["zmin"] + 1
        if l.get("probe_start"):   # a converted step ladder's clear spot in front of it
            x, y, z = l["probe_start"]
        cmds = ["auto_join_team", "primarydmweapon rifle", "wait 3000",
                f"tele {x:.0f} {y:.0f} {z:.0f}", f"face -50 {l['angle']:.0f} 0", "wait 600"]
        if (l.get("hang") or 0) > 40:
            # a step ladder hanging over the floor (report ``hang``): the start is in the air
            # at the column, so push into it from the teleport on (a falling player steps up)
            cmds += ["+forward", f"tele {x:.0f} {y:.0f} {z:.0f}", f"face -50 {l['angle']:.0f} 0", "wait 150", "viewpos"]
        else:
            cmds += [f"tele {x:.0f} {y:.0f} {z:.0f}", f"face -50 {l['angle']:.0f} 0", "wait 400", "viewpos",
                     "+use", "wait 300", "-use", "+forward"]
        for _ in range(max(1, round(climb_ms / 500))):
            cmds += ["wait 500", "viewpos"]
        cmds += ["-forward", f"saveshot ladder{i:02d}", "wait 300"]
        res = run(pk3s, map_name, (), extra_commands=cmds, run_name=f"{run_name or 'ladders'}{i:02d}",
                  timeout=120 + climb_ms / 1000)
        pos = [tuple(int(v) for v in m.groups()[:3]) for m in VIEWPOS_RE.finditer(res.log)]
        before, after = (pos[0], max(pos[1:], key=lambda q: q[2])) if len(pos) >= 2 else (None, None)
        climbed = (after[2] - before[2]) if before and after else None
        shot = next(iter(res.screenshots.values()), None)
        out.append({**l, "before": before, "after": after, "climbed": climbed, "shot": str(shot) if shot else None,
                    "ok": climbed is not None and climbed >= min(64.0, (l["zmax"] - l["zmin"]) * 0.5)})
    return out
