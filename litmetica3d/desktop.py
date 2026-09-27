"""Desktop entry point: native WinUI on Windows, existing Qt elsewhere."""
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
        print("WinUI 前端尚未构建。请在源码仓库运行 setup_winui.ps1，再启动 run_winui.ps1。\n"
              "需要旧 Qt 界面时运行 python -m litmetica3d.gui_app。", file=sys.stderr)
        return 1
    return subprocess.call([str(exe)], cwd=root)
