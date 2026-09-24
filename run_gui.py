import multiprocessing

from litmetica3d.desktop import launch_gui

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(launch_gui())
