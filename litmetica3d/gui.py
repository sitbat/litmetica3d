"""Compatibility entry point for the PySide6 desktop interface."""

from .gui_app import MainWindow, launch_gui

LitmeticaGUI = MainWindow

__all__ = ["MainWindow", "LitmeticaGUI", "launch_gui"]

if __name__ == "__main__":
    raise SystemExit(launch_gui())