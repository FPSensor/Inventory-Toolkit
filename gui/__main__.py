from core.build import BUILD
BUILD.require("gui")

from gui.app import launch_gui

if __name__ == "__main__":
    launch_gui()
