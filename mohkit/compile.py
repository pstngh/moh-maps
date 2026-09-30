"""Drive the original EA compilers: Q3map (BSP), Q3map -vis (VIS), MOHlight (light).

The EA tools are 32-bit Windows programs. On macOS/Linux they run under Wine
(CrossOver on macOS). Each compile gets its own game root::

    <build_dir>/roots/<name>/main/Pak0.pk3 ...   links to the retail paks (shader scripts!)
    <build_dir>/roots/<name>/main/textures/...   the map's own assets, if any
    <build_dir>/roots/<name>/main/maps/dm/<name>.map

Compiling against the retail paks is not optional: without ``scripts/common.shader``
the compiler treats ``common/caulk``, sky and clip shaders as ordinary textures and
the map renders with black holes. Compiling against a heavily modded ``main`` can
exhaust ``MAX_SURFACE_INFO``, hence the isolated root.
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
PROBLEM_RE = re.compile(r"warning|error|leak|degenerate|couldn't|could not|MAX_|exceed|too large|clamped|mismatch|huge winding|bad ",
                        re.IGNORECASE)

QUALITY = {
    # vis flags, light flags
    "draft": (["-fast"], ["-fast"]),
    "preview": ([], ["-bounce", "2"]),
    "normal": ([], []),
    "final": ([], ["-final"]),
}


@dataclass
class Stage:
    name: str
    cmd: list[str]
    seconds: float
    returncode: Optional[int]
    log: str
    timed_out: bool = False


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
                and all(s.returncode == 0 and not s.timed_out for s in self.stages if s.name != "info"))

    def summary(self) -> str:
        lines = [f"{self.name}: {'OK' if self.ok else 'FAILED'}  ({self.bsp})"]
        for s in self.stages:
            lines.append(f"  {s.name:6s} {s.seconds:8.1f}s  rc={s.returncode}{'  TIMEOUT' if s.timed_out else ''}")
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
        """Run one tool; its raw output streams to ``<cwd>/<name>.log`` while it runs."""
        argv = self._argv(exe, list(args))
        env = dict(os.environ)
        env.setdefault("WINEDEBUG", "-all")
        t0 = time.time()
        log_path = Path(cwd) / f"{name}.log"
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
                self.kill_stragglers(exe)
        log = log_path.read_bytes().decode("latin-1", "replace")
        return Stage(name, argv, time.time() - t0, rc, clean_log(log), to)

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
                cfg: Optional[_config.Config] = None) -> CompileResult:
    """Compile a map. ``name`` is the game path without extension, e.g. ``dm/mymap``.

    ``quality``: ``draft`` (fast VIS + fast light), ``preview`` (2 radiosity bounces), ``normal`` (8),
    ``final`` (MOHlight -final).
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
    vis_q, light_q = QUALITY[quality]

    st = tc.run("bsp", "Q3map.exe", [*thr, *bsp_args, *game, tmap], root, timeout)
    res.stages.append(st)
    # "Entity N of type 'light' leaked" only means that entity sits in the void (stock maps do it);
    # a real hull leak prints the banner below and writes a .lin trace instead of a .prt.
    res.leaked = map_path.with_suffix(".lin").exists() or "******* leaked *******" in st.log
    if st.returncode != 0 or res.leaked or not res.bsp.is_file():
        _collect(res)
        return res
    if vis:
        res.stages.append(tc.run("vis", "Q3map.exe", ["-vis", *thr, *vis_q, *vis_args, *game, tmap], root, timeout))
    if light:
        st = tc.run("light", "MOHlight.exe", [*thr, *light_q, *light_args, *game, tmap], root, timeout)
        if st.returncode not in (0, None) and threads != 1:
            # Multi-threaded MOHlight occasionally access-violates on big maps; one thread is reliable.
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


def bsp_checks(path: Path) -> list[str]:
    """Defects that only show up in the compiled BSP."""
    from . import bsp as _bsp
    out = []
    try:
        b = _bsp.BSP(path)
    except Exception as e:  # noqa: BLE001
        return [f"[bsp-check] cannot read BSP: {e}"]
    shaders = b.shaders()
    big = [s for s in b.surfaces() if s.type == 1 and s.num_verts > MAX_FACE_POINTS]
    if big:
        names = sorted({shaders[s.shader].name for s in big})
        out.append(f"[bsp-check] ERROR {len(big)} planar faces have > {MAX_FACE_POINTS} vertices and will render as "
                   f"the default checker (split long brushes): {', '.join(names[:8])}")
    summ = b.summary()
    for k, v in summ["over_limit"].items():
        out.append(f"[bsp-check] ERROR {k} over engine limit: {v}")
    bad = sorted({sh.fence_mask for sh in shaders if sh.fence_mask and sh.fence_mask not in ("nomask", "ignore")
                  and not sh.fence_mask.lower().endswith(".tga")})
    if bad:
        out.append(f"[bsp-check] ERROR {len(bad)} shaders have a non-.tga qer_editorimage; the engine reads it as a TGA "
                   f"fence mask and the map fails to load (use shaders.editor_image): {', '.join(bad[:5])}")
    if summ["lightmap_pages"] > 180:
        out.append(f"[bsp-check] ERROR {summ['lightmap_pages']} lightmap pages (MOHlight limit is 180)")
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
