"""Desktop entry point: use a built Windows frontend when available, else Qt."""
from pathlib import Path
import subprocess
import sys


def launch_gui():
    # Existing PyInstaller/Qt distributions retain their embedded UI.
    if sys.platform != "win32" or getattr(sys, "frozen", False):
        from .gui_app import launch_gui as launch_qt
        return launch_qt()
    root = Path(__file__).resolve().parent.parent
    exe = root / "frontend/Litmetica3D.WinUI/bin/x64/Release/net10.0-windows10.0.26100.0/win-x64/Litmetica3D.WinUI.exe"
    if not exe.is_file():
        # Wheels contain the Python/Qt application, not a compiled WinUI EXE.
        from .gui_app import launch_gui as launch_qt
        return launch_qt()
    return subprocess.call([str(exe)], cwd=root)
