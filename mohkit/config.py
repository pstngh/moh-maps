"""Locate the game, the EA compilers, Wine and OpenMoHAA.

Resolution order for every setting: environment variable, then
``mohkit.local.json`` at the repository root (gitignored), then auto-detection.

======================  ===========================  =======================================
setting                 env var                      meaning
======================  ===========================  =======================================
game_dir                MOHKIT_GAME_DIR              dir containing ``main/Pak0.pk3``
openmohaa               MOHKIT_OPENMOHAA             OpenMoHAA client executable
tools_dir               MOHKIT_TOOLS_DIR             dir with ``Q3map.exe`` and ``MOHlight.exe``
wine                    MOHKIT_WINE                  wine executable ("" on Windows)
wine_bottle             MOHKIT_WINE_BOTTLE           CrossOver bottle name (macOS)
csgo_dir                MOHKIT_CSGO_DIR              CS:GO install (contains ``csgo/pak01_dir.vpk``)
build_dir               MOHKIT_BUILD_DIR             scratch dir for compiles and test homes (default: user cache)
======================  ===========================  =======================================
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
LOCAL_CONFIG = REPO / "mohkit.local.json"
TOOLCHAIN = REPO / ".toolchain"

RETAIL_PAKS = ("Pak0.pk3", "Pak1.pk3", "Pak2.pk3", "Pak3.pk3", "Pak4.pk3", "Pak5.pk3", "Pak6EnUk.pk3", "pak7.pk3")

CROSSOVER_WINE = "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine"


@dataclass
class Config:
    game_dir: Optional[str] = None
    openmohaa: Optional[str] = None
    tools_dir: Optional[str] = None
    wine: Optional[str] = None
    wine_bottle: Optional[str] = None
    csgo_dir: Optional[str] = None
    build_dir: str = ""  # default: see default_build_dir()

    @property
    def main_dir(self) -> Path:
        if not self.game_dir:
            raise RuntimeError("game_dir not configured; run `python -m mohkit doctor`")
        return Path(self.game_dir) / "main"

    def retail_paks(self) -> list[Path]:
        """Retail AA paks present in the game dir (case-insensitive match)."""
        present = {p.name.lower(): p for p in self.main_dir.glob("*.pk3")}
        return [present[n.lower()] for n in RETAIL_PAKS if n.lower() in present]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def default_build_dir() -> str:
    """Scratch space for compile roots and test homes: outside the repo and outside any
    cloud-synced folder. (iCloud's file provider deleted symlinks and files from a build
    dir under ~/Documents mid-compile.)"""
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library/Caches/mohkit"
    elif system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "mohkit"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mohkit"
    return str(base / "build")


def _is_game_dir(p: Path) -> bool:
    return (p / "main").is_dir() and any(q.name.lower() == "pak0.pk3" for q in (p / "main").glob("*.pk3"))


def _candidates_game() -> list[Path]:
    home = Path.home()
    return [
        home / "Documents/Games/moh",
        home / "Games/moh",
        Path("/Applications/OpenMoHAA"),
        Path("C:/Program Files (x86)/EA GAMES/MOHAA"),
        Path("C:/Program Files/EA GAMES/MOHAA"),
        Path("C:/Games/MOHAA"),
        home / ".local/share/openmohaa",
    ]


def _detect_openmohaa(game_dir: Optional[str]) -> Optional[str]:
    names = ["openmohaa", "openmohaa.exe", "launch_openmohaa_base", "launch_openmohaa_base.exe"]
    if game_dir:
        for n in names:
            p = Path(game_dir) / n
            if p.is_file():
                return str(p)
    for n in names:
        w = shutil.which(n)
        if w:
            return w
    return None


def _detect_tools() -> Optional[str]:
    for p in (TOOLCHAIN / "MOHTools", Path.home() / "Documents/moh-toolchain/MOHTools"):
        if (p / "Q3map.exe").is_file() and (p / "MOHlight.exe").is_file():
            return str(p)
    return None


def _detect_wine() -> tuple[Optional[str], Optional[str]]:
    if platform.system() == "Windows":
        return "", None
    if Path(CROSSOVER_WINE).is_file():
        bottles = Path.home() / "Library/Application Support/CrossOver/Bottles"
        names = sorted(p.name for p in bottles.iterdir() if (p / "cxbottle.conf").is_file()) if bottles.is_dir() else []
        bottle = "mohkit" if "mohkit" in names else (names[0] if names else None)
        return CROSSOVER_WINE, bottle
    w = shutil.which("wine") or shutil.which("wine64")
    return w, None


def _detect_csgo() -> Optional[str]:
    for p in (Path.home() / "Documents/Games/csgo",
              Path.home() / "Library/Application Support/Steam/steamapps/common/Counter-Strike Global Offensive",
              Path("C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive")):
        if (p / "csgo" / "pak01_dir.vpk").is_file():
            return str(p)
    return None


_cached: Optional[Config] = None


def load(refresh: bool = False) -> Config:
    global _cached
    if _cached is not None and not refresh:
        return _cached
    cfg = Config()
    local = json.loads(LOCAL_CONFIG.read_text()) if LOCAL_CONFIG.is_file() else {}
    for key in asdict(cfg):
        env = os.environ.get("MOHKIT_" + key.upper())
        if env is not None:
            setattr(cfg, key, env)
        elif key in local:
            setattr(cfg, key, local[key])
    if not cfg.build_dir:
        cfg.build_dir = default_build_dir()
    if not cfg.game_dir:
        cfg.game_dir = next((str(p) for p in _candidates_game() if _is_game_dir(p)), None)
    if not cfg.openmohaa:
        cfg.openmohaa = _detect_openmohaa(cfg.game_dir)
    if not cfg.tools_dir:
        cfg.tools_dir = _detect_tools()
    if cfg.wine is None:
        cfg.wine, bottle = _detect_wine()
        if cfg.wine_bottle is None:
            cfg.wine_bottle = bottle
    if not cfg.csgo_dir:
        cfg.csgo_dir = _detect_csgo()
    _cached = cfg
    return cfg


def save_local(cfg: Config) -> None:
    LOCAL_CONFIG.write_text(cfg.to_json() + "\n")
