import multiprocessing

from litmetica3d.gui_app import launch_gui

if __name__ == "__main__":
    multiprocessing.freeze_support()
    launch_gui()
