"""CS:GO reference screenshots from a map's named spectator cameras.

Runs the CS:GO client found in ``config.csgo_dir`` (a native macOS build of the 2017+
engine works; ``csgo_osx64``) windowed at 1280 x 720, drives it over the remote console
(``-netconport``), and for every entry of ``maps/<map>_cameras.txt`` flies the spectator
camera there (``spec_goto x y z pitch yaw``) and saves ``jpeg``. The shots land in
``local/csgo/<name>/csgo_ref/NN_<camera>.jpg``, named like the converted map's shots
(``mohkit.source.convert.shoot``), so the two can be compared camera by camera::

    python -m mohkit csgo-ref de_inferno            # -> local/csgo/cs_inferno/csgo_ref/

The game's ``cfg/config.cfg`` and ``cfg/video.txt`` are restored afterwards (a windowed
run would otherwise leave them changed). Bots are kicked and the HUD hidden; CS:GO's
default fov (90 on a 4:3 basis) is kept, a little wider than MOHAA's 80.
"""

from __future__ import annotations

import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

PORT = 2121
_CAMERA_RE = re.compile(r'"([^"]+)"\s+"\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*"')


def _send(cmds, port: int = PORT, pause: float = 0.3) -> str:
    out = b""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        for c in cmds:
            if isinstance(c, (int, float)):
                time.sleep(c)
                continue
            s.sendall((c + "\n").encode())
            time.sleep(pause)
            s.settimeout(0.2)
            try:
                while True:
                    d = s.recv(65536)
                    if not d:
                        break
                    out += d
            except OSError:
                pass
    return out.decode("latin-1", "replace")


def _wait_for_map(map_name: str, timeout: float = 240.0, port: int = PORT) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st = _send(["status"], port)
            if re.search(rf"^map\s*:\s*{re.escape(map_name)}\b", st, re.M):
                return True
        except OSError:
            pass
        time.sleep(3)
    return False


def cameras(cam_file: Path) -> list[tuple[str, tuple[float, ...]]]:
    text = re.sub(r"//[^\n]*", "", Path(cam_file).read_text(encoding="latin-1", errors="replace"))
    return [(m.group(1).strip(), tuple(float(v) for v in m.groups()[1:])) for m in _CAMERA_RE.finditer(text)]


def shoot(map_name: str, name: Optional[str] = None, csgo_dir: Optional[str] = None, log=print,
          settle: float = 2.5) -> list[Path]:
    """Reference shots of ``map_name`` (e.g. ``de_nuke``); returns the saved files."""
    from .. import config
    cfg = config.load()
    root = Path(csgo_dir or cfg.csgo_dir)
    game = root / "csgo"
    exe = root / "csgo_osx64"
    if not exe.is_file():
        raise SystemExit(f"no CS:GO client at {exe}")
    cams = cameras(game / "maps" / f"{map_name}_cameras.txt")
    name = name or ("cs_" + map_name.split("_", 1)[-1] if map_name.startswith("de_") else map_name)
    out = config.REPO / "local" / "csgo" / name / "csgo_ref"
    out.mkdir(parents=True, exist_ok=True)
    keep = {p: p.read_bytes() for p in (game / "cfg" / "config.cfg", game / "cfg" / "video.txt") if p.is_file()}
    log_file = open(out.parent / "csgo_ref.log", "wb")
    proc = subprocess.Popen([str(exe), "-game", "csgo", "-novid", "-windowed", "-noborder", "-w", "1280", "-h", "720",
                             "-insecure", "-condebug", "-netconport", str(PORT), "+map", map_name], cwd=str(root),
                            stdout=log_file, stderr=subprocess.STDOUT)
    saved: list[Path] = []
    try:
        if not _wait_for_map(map_name):
            raise SystemExit(f"CS:GO did not load {map_name}")
        _send(["sv_cheats 1", "bot_quota 0", "bot_kick", "mp_warmup_end", "cl_drawhud 0", "r_drawviewmodel 0",
               "r_cleardecals", "jointeam 1", 2.0, "spec_mode 6", 1.0])
        for i, (cam, (x, y, z, pitch, yaw)) in enumerate(cams):
            tag = f"{i:02d}_" + re.sub(r"[^A-Za-z0-9_-]", "_", cam)
            _send([f"spec_goto {x} {y} {z} {pitch} {yaw}", settle, f"jpeg mohkit_{tag} 95", 0.8])
            f = game / "screenshots" / f"mohkit_{tag}.jpg"
            if f.is_file():
                shutil.move(str(f), out / f"{tag}.jpg")
                saved.append(out / f"{tag}.jpg")
            else:
                log(f"  no screenshot for {cam}")
        log(f"== {len(saved)} CS:GO reference shots in {out}")
    finally:
        try:
            _send(["cl_drawhud 1", "quit"])
        except OSError:
            pass
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
        for p, data in keep.items():
            p.write_bytes(data)
        log_file.close()
    return saved
