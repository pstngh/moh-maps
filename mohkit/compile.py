"""Drive the original EA compilers: Q3map (BSP), Q3map -vis (VIS), MOHlight (light).

The EA tools are 32-bit Windows programs. On macOS/Linux they run under Wine
(CrossOver on macOS). Each compile gets its own game root::

    <build_dir>/roots/<name>/main/Pak0.pk3 ...   links to the retail paks (shader scripts!)
    <build_dir>/roots/<name>/main/textures/...   the map's own assets, if any
    <build_dir>/roots/<name>/main/maps/dm/<name>.map

Compiling against the retail paks is not optional: without ``scripts/common.shader``
the compiler treats ``common/caulk``, sky and clip shaders as ordinary textures and
the map renders with black holes. Q3map holds only ~1,600 shaders beyond the retail
scripts (``MAX_SURFACE_INFO``, measured), so mods in ``main`` could exhaust it: hence
the isolated root.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Union

from . import config as _config

PROGRESS_RE = re.compile(r"\s*\d+% complete\.\s+\d+ hours\s+\d+ minutes\s+\d+ seconds remaining\.")
TIMING_RE = re.compile(r"^\s*\(\d+\.\d+\) seconds\.$")
NOISE = ("msync:", "fixme:", "err:ntdll", "wine:")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROBLEM_RE = re.compile(r"warning|error|leak|degenerate|couldn't|could not|MAX_|exceed|too large|clamped|mismatch|huge winding|bad ",
                        re.IGNORECASE)

QUALITY = {
    # bsp flags, vis flags, light flags. Draft skips face merging (-nomerge): on mk_village the
    # BSP stage took 23 s instead of 84 s, for 30% more draw surfaces (docs/toolchain.md).
    # MOHlight -fast alone still runs radiosity (its lightmaps match -bounce 2); -bounce 0 skips it.
    "draft": (["-nomerge"], ["-fast"], ["-fast", "-bounce", "0"]),
    "preview": ([], [], ["-bounce", "2"]),
    "normal": ([], [], []),
    "final": ([], [], ["-final"]),
}


@dataclass
class Stage:
    name: str
    cmd: list[str]
    seconds: float
    returncode: Optional[int]
    log: str
    timed_out: bool = False
    timeline: list[tuple[float, str]] = field(default_factory=list)  # (seconds, line), POSIX only

    def slowest(self, n: int = 3, min_seconds: float = 5.0) -> list[tuple[float, str, str]]:
        """The ``n`` longest silences in the log: (seconds, line before, line after)."""
        gaps = []
        prev_t, prev = 0.0, "(start)"
        for t, line in self.timeline + [(self.seconds, "(end)")]:
            if t - prev_t >= min_seconds:
                gaps.append((round(t - prev_t, 1), prev, line))
            prev_t, prev = t, line
        return sorted(gaps, reverse=True)[:n]


@dataclass
class CompileResult:
    name: str
    root: Path
    bsp: Path
    stages: list[Stage] = field(default_factory=list)
    leaked: bool = False
    problems: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (not self.leaked and self.bsp.is_file() and not any("ERROR" in p for p in self.problems if p.startswith("[bsp-check]"))
                and all(s.returncode == 0 and not s.timed_out for s in self.stages
                        if s.name not in ("info", "light_mt")))  # light_mt: a crashed run that was retried

    def summary(self) -> str:
        lines = [f"{self.name}: {'OK' if self.ok else 'FAILED'}  ({self.bsp})"]
        for s in self.stages:
            lines.append(f"  {s.name:6s} {s.seconds:8.1f}s  rc={s.returncode}{'  TIMEOUT' if s.timed_out else ''}")
            if s.seconds >= 60:
                for dt, before, after in s.slowest():
                    lines.append(f"      {dt:7.1f}s after {before[:60]!r}")
        if self.leaked:
            lines.append(f"  LEAK: see {self.bsp.with_suffix('.lin')}")
        if self.stats:
            lines.append("  " + "  ".join(f"{k}={v:g}" for k, v in self.stats.items()))
        for p in self.problems[:40]:
            lines.append(f"  ! {p}")
        if len(self.problems) > 40:
            lines.append(f"  ! ... {len(self.problems) - 40} more")
        return "\n".join(lines)


def to_tool_path(p: Union[str, Path]) -> str:
    """Path as the Windows tools see it (Wine maps / to Z:)."""
    p = Path(p).resolve()
    if platform.system() == "Windows":
        return str(p)
    return "Z:" + str(p).replace("/", "\\")


def clean_log(text: str) -> str:
    text = PROGRESS_RE.sub("", text)
    out = []
    for line in text.splitlines():
        s = line.rstrip()
        if not s or s.startswith(NOISE) or TIMING_RE.match(s):
            continue
        out.append(s)
    return "\n".join(out)


class Toolchain:
    def __init__(self, cfg: Optional[_config.Config] = None):
        self.cfg = cfg or _config.load()
        if not self.cfg.tools_dir:
            raise RuntimeError("EA tools not found; run `python -m mohkit setup` (downloads MOHTools)")
        self.tools = Path(self.cfg.tools_dir)

    def _argv(self, exe: str, args: Iterable[str]) -> list[str]:
        exe_path = str(self.tools / exe)
        if self.cfg.wine:
            argv = [self.cfg.wine]
            if self.cfg.wine_bottle and "CrossOver" in self.cfg.wine:
                argv += ["--bottle", self.cfg.wine_bottle, "--wait-children"]
            return argv + [exe_path, *args]
        return [exe_path, *args]

    def run(self, name: str, exe: str, args: Iterable[str], cwd: Path, timeout: float) -> Stage:
        """Run one tool; its output streams to ``<cwd>/<name>.log`` while it runs.

        On POSIX the tool writes to a pseudo-terminal: Wine's C runtime buffers output to
        a file or pipe until the process exits, but flushes every line to a terminal. So
        the log is live and :attr:`Stage.timeline` has the time of each line (this found
        that Q3map's "Merging faces" step takes most of a BSP compile).
        """
        argv = self._argv(exe, list(args))
        env = dict(os.environ)
        env.setdefault("WINEDEBUG", "-all")
        # A crashing tool would otherwise start Wine's debugger (winedbg --auto), which parks
        # the process: the build hangs instead of failing and retrying (seen with MOHlight).
        env.setdefault("WINEDLLOVERRIDES", "winedbg.exe=d")
        t0 = time.time()
        log_path = Path(cwd) / f"{name}.log"
        if os.name == "posix":
            rc, to, timeline = self._run_pty(argv, cwd, env, log_path, timeout, t0)
        else:
            timeline = []
            rc, to = None, False
            with open(log_path, "wb") as fh:
                # stdin=DEVNULL: the EA tools wait for a key on some usage/error paths.
                p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT)
                try:
                    rc = p.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    to = True
                    p.kill()
                    p.wait()
        if to:
            self.kill_stragglers(exe)
        log = log_path.read_bytes().decode("latin-1", "replace")
        return Stage(name, argv, time.time() - t0, rc, clean_log(log), to, timeline)

    @staticmethod
    def _run_pty(argv, cwd, env, log_path: Path, timeout: float, t0: float):
        import pty
        import select
        import fcntl
        import struct
        import termios
        master, slave = pty.openpty()
        # Wine's console wraps output at the terminal width (80 by default): make it wide.
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 4000, 0, 0))
        timeline: list[tuple[float, str]] = []
        to = False
        with open(log_path, "w", encoding="latin-1", errors="replace") as fh:
            p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=slave, stderr=slave,
                                 start_new_session=True)
            os.close(slave)
            buf = b""

            def emit(chunk: bytes) -> None:
                for raw in re.split(rb"[\r\n]+", chunk):
                    line = ANSI_RE.sub("", raw.decode("latin-1", "replace")).rstrip()
                    if line:
                        fh.write(line + "\n")
                        timeline.append((round(time.time() - t0, 2), line))
                fh.flush()

            while True:
                if time.time() - t0 > timeout:
                    to = True
                    p.kill()
                    break
                ready, _, _ = select.select([master], [], [], 0.5)
                if ready:
                    try:
                        data = os.read(master, 65536)
                    except OSError:  # EIO: every writer closed the terminal
                        data = b""
                    if not data:
                        break
                    buf += data
                    cut = max(buf.rfind(b"\n"), buf.rfind(b"\r"))
                    if cut >= 0:
                        emit(buf[:cut])
                        buf = buf[cut + 1:]
                elif p.poll() is not None:
                    break
            if buf:
                emit(buf)
            rc = p.wait()
        os.close(master)
        return (None if to else rc), to, timeline

    def kill_stragglers(self, exe: str) -> None:
        if platform.system() != "Windows":
            subprocess.run(["pkill", "-f", exe], check=False)


def prepare_root(name: str, assets: Optional[Mapping[str, Union[bytes, str, Path]]] = None,
                 cfg: Optional[_config.Config] = None) -> Path:
    """Fresh compile root linked to the retail paks, with the map's own assets as loose files."""
    cfg = cfg or _config.load()
    root = Path(cfg.build_dir) / "roots" / name.replace("/", "_")
    if root.exists():
        shutil.rmtree(root)
    main = root / "main"
    main.mkdir(parents=True)
    paks = cfg.retail_paks()
    if not paks:
        raise RuntimeError(f"no retail Pak*.pk3 in {cfg.main_dir}")
    for pak in paks:
        dst = main / pak.name
        try:
            os.symlink(pak, dst)
        except OSError:
            try:
                os.link(pak, dst)
            except OSError:
                shutil.copy2(pak, dst)
    for rel, data in (assets or {}).items():
        dst = main / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            dst.write_bytes(data)
        else:
            shutil.copy2(data, dst)
    return root


def _grab(pattern: str, text: str, cast=float) -> Optional[float]:
    m = re.search(pattern, text)
    return cast(m.group(1)) if m else None


def compile_map(map_text_or_path: Union[str, Path], name: str,
                assets: Optional[Mapping[str, Union[bytes, str, Path]]] = None,
                quality: str = "normal", vis: bool = True, light: bool = True,
                bsp_args: Iterable[str] = (), vis_args: Iterable[str] = (), light_args: Iterable[str] = (),
                threads: Optional[int] = None, timeout: float = 4 * 3600,
                stop_on_bad_faces: bool = True, cfg: Optional[_config.Config] = None) -> CompileResult:
    """Compile a map. ``name`` is the game path without extension, e.g. ``dm/mymap``.

    ``quality``: ``draft`` (no face merging, fast VIS, fast light without radiosity), ``preview`` (2 radiosity
    bounces), ``normal`` (8),
    ``final`` (MOHlight -final).

    Faces the renderer cannot draw (> 64 vertices) are checked right after the BSP stage;
    with ``stop_on_bad_faces`` the compile stops there instead of spending VIS and light time.
    """
    cfg = cfg or _config.load()
    tc = Toolchain(cfg)
    root = prepare_root(name, assets, cfg)
    map_path = root / "main" / "maps" / f"{name}.map"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    src = Path(map_text_or_path) if not isinstance(map_text_or_path, str) or "\n" not in map_text_or_path else None
    if src is not None:
        shutil.copy2(src, map_path)
    else:
        map_path.write_text(str(map_text_or_path), encoding="latin-1", newline="\n")
    res = CompileResult(name, root, map_path.with_suffix(".bsp"))
    game = ["-gamedir", to_tool_path(root), "-moddir", "main"]
    tmap = to_tool_path(map_path)
    threads = threads or os.cpu_count() or 4
    thr = ["-threads", str(threads)]
    bsp_q, vis_q, light_q = QUALITY[quality]

    st = tc.run("bsp", "Q3map.exe", [*thr, *bsp_q, *bsp_args, *game, tmap], root, timeout)
    res.stages.append(st)
    # "Entity N of type 'light' leaked" only means that entity sits in the void (stock maps do it);
    # a real hull leak prints the banner below and writes a .lin trace instead of a .prt.
    res.leaked = map_path.with_suffix(".lin").exists() or "******* leaked *******" in st.log
    if st.returncode != 0 or res.leaked or not res.bsp.is_file():
        _collect(res)
        return res
    # Q3map has fixed T-junctions by now, so face vertex counts are final.
    res.problems += face_checks(res.bsp)
    if stop_on_bad_faces and any("ERROR" in p for p in res.problems):
        res.problems.append("[bsp-check] stopped before VIS and light: fix the faces above "
                            "(compile_map(..., stop_on_bad_faces=False) compiles anyway)")
        _collect(res)
        return res
    if vis:
        res.stages.append(tc.run("vis", "Q3map.exe", ["-vis", *thr, *vis_q, *vis_args, *game, tmap], root, timeout))
    if light:
        st = tc.run("light", "MOHlight.exe", [*thr, *light_q, *light_args, *game, tmap], root, timeout)
        if st.returncode not in (0, None) and threads != 1 and "ERROR" not in st.log:
            # A crash without a reported ERROR (those, like MAX_MAP_LIGHTING, are deterministic):
            # retry with one thread, keeping the failed run's log as light_mt.log (evidence for
            # docs/toolchain.md: multi-threaded MOHlight was seen to access-violate).
            failed = Path(root) / "light.log"
            if failed.is_file():
                failed.replace(Path(root) / "light_mt.log")
            st.name = "light_mt"
            res.stages.append(st)
            res.problems.append(f"[light] multi-threaded MOHlight exited with {st.returncode:#x}; "
                                f"retried with -threads 1 (log: light_mt.log)")
            st = tc.run("light", "MOHlight.exe", ["-threads", "1", *light_q, *light_args, *game, tmap], root, timeout)
        res.stages.append(st)
    info = tc.run("info", "Q3map.exe", ["-info", to_tool_path(res.bsp)], root, 300)
    res.stages.append(info)
    _collect(res)
    return res


def _collect(res: CompileResult) -> None:
    logs = {s.name: s.log for s in res.stages}
    bsp, vis, light, info = (logs.get(k, "") for k in ("bsp", "vis", "light", "info"))
    m = re.search(r"(\d+) faces from (\d+)", bsp)
    if m:
        res.stats["faces_out"], res.stats["faces_in"] = float(m.group(1)), float(m.group(2))
    for key, pat, text in (
        ("clusters", r"(\d+) portalclusters", vis),
        ("portals", r"(\d+) numportals", vis),
        ("visbytes", r"visdatasize:(\d+)", vis),
        ("avg_visible", r"Average clusters visible: (\d+)", vis),
        ("static_models_lit", r"Total Models Lit: (\d+)", light),
        ("weight_mb", r"BSP weighs in at ([\d.]+) MB", info),
    ):
        v = _grab(pat, text)
        if v is not None:
            res.stats[key] = v
    for m in re.finditer(r"^\s*(\d+)\s+(models|shaders|brushes|brushsides|planes|entdata|drawverts|drawindexes|"
                         r"drawsurfaces|lightmaps|entitylights|terrain|static models defs)\s+\d+\s*$", info, re.M):
        res.stats[m.group(2).replace(" ", "_")] = float(m.group(1))
    seen = set()
    for s in res.stages:
        if s.name == "info":
            continue
        for line in s.log.splitlines():
            if PROBLEM_RE.search(line) and line not in seen:
                seen.add(line)
                res.problems.append(f"[{s.name}] {line.strip()}")
    if res.bsp.with_suffix(".lin").exists():
        res.leaked = True
    if res.bsp.is_file() and "light" in logs:
        res.problems += bsp_checks(res.bsp)


MAX_FACE_POINTS = 64  # renderergl1/tr_local.h: faces with more vertices draw as the default checker


def face_checks(path: Path, show: int = 12) -> list[str]:
    """Planar faces with more than 64 vertices (they render as the default checker), with
    their shader, vertex count, centre and bounds. Valid right after the BSP stage."""
    from . import bsp as _bsp
    try:
        b = _bsp.BSP(path)
    except Exception as e:  # noqa: BLE001
        return [f"[bsp-check] cannot read BSP: {e}"]
    shaders = b.shaders()
    big = sorted((s for s in b.surfaces() if s.type == 1 and s.num_verts > MAX_FACE_POINTS),
                 key=lambda s: -s.num_verts)
    if not big:
        return []
    out = [f"[bsp-check] ERROR {len(big)} planar faces have > {MAX_FACE_POINTS} vertices and will render as the "
           f"default checker. Usually a long or narrow face collecting T-junction vertices from the detail that "
           f"meets it: split the brush, or stop the detail short of it (docs/map-format.md, 64-vertex faces)"]
    for s in big[:show]:
        pts = b.vertex_positions(s.first_vert, s.num_verts)
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        c = " ".join(f"{(lo[i] + hi[i]) / 2:.0f}" for i in range(3))
        span = " ".join(f"{lo[i]:.0f}..{hi[i]:.0f}" for i in range(3))
        out.append(f"[bsp-check]   {s.num_verts} verts  {shaders[s.shader].name}  centre ({c})  x y z {span}")
    if len(big) > show:
        out.append(f"[bsp-check]   ... {len(big) - show} more")
    return out


def bsp_checks(path: Path) -> list[str]:
    """Defects that only show up in the lit BSP (face vertex counts: see face_checks)."""
    from . import bsp as _bsp
    out = []
    try:
        b = _bsp.BSP(path)
    except Exception as e:  # noqa: BLE001
        return [f"[bsp-check] cannot read BSP: {e}"]
    shaders = b.shaders()
    summ = b.summary()
    for k, v in summ["over_limit"].items():
        out.append(f"[bsp-check] ERROR {k} over engine limit: {v}")
    bad = sorted({sh.fence_mask for sh in shaders if sh.fence_mask and sh.fence_mask not in ("nomask", "ignore")
                  and not sh.fence_mask.lower().endswith(".tga")})
    if bad:
        out.append(f"[bsp-check] ERROR {len(bad)} shaders have a non-.tga qer_editorimage; the engine reads it as a TGA "
                   f"fence mask and the map fails to load (use shaders.editor_image): {', '.join(bad[:5])}")
    if summ["lightmap_pages"] > 170:
        out.append(f"[bsp-check] ERROR {summ['lightmap_pages']} lightmap pages (MOHlight limit is 170)")
    return out


def read_leak(res: CompileResult) -> list[tuple[float, float, float]]:
    """Points of the leak trace (.lin): from the entity out to the void."""
    lin = res.bsp.with_suffix(".lin")
    pts = []
    if lin.is_file():
        for line in lin.read_text().splitlines():
            v = line.split()
            if len(v) >= 3:
                pts.append((float(v[0]), float(v[1]), float(v[2])))
    return pts
