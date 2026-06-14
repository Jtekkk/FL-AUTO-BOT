#!/usr/bin/env python3
"""Build a standalone FL Auto Bot GUI executable with PyInstaller.

    pip install pyinstaller          # plus: pip install -r requirements.txt
    python packaging/build_exe.py

Produces ``dist/FLAutoBot`` (``dist/FLAutoBot.exe`` on Windows). A single,
double-clickable file with Python and all dependencies bundled in.

Note: PyInstaller does **not** cross-compile -- run this on the OS you want to
target (Windows for a .exe, macOS for a .app-style binary, Linux for an ELF).
Use the GitHub Actions workflow (.github/workflows/build-exe.yml) to build all
three in the cloud.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = Path(__file__).resolve().parent / "launch_gui.py"
APP_NAME = "FLAutoBot"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed.\n  pip install pyinstaller",
              file=sys.stderr)
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",          # one self-contained file
        "--windowed",         # GUI app: no console window
        "--name", APP_NAME,
        "--collect-submodules", "flautobot",   # include lazily-imported submodules
        # External deps imported lazily inside the package (PyInstaller can't see
        # them statically). Missing ones are warnings, not errors.
        "--hidden-import", "anthropic",
        "--hidden-import", "mido.backends.rtmidi",
        "--hidden-import", "rtmidi",
        str(ENTRY),
    ]
    print("Building:", " ".join(cmd), "\n")
    result = subprocess.call(cmd, cwd=str(ROOT))
    if result == 0:
        ext = ".exe" if sys.platform.startswith("win") else ""
        out = ROOT / "dist" / f"{APP_NAME}{ext}"
        print(f"\nDone -> {out}")
    return result


if __name__ == "__main__":
    sys.exit(main())
