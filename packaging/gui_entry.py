"""Windowed PyInstaller entry point that selects the desktop CLI mode."""

import sys

from divyaraj.__main__ import main

sys.argv = [sys.argv[0], "--gui", *sys.argv[1:]]
main()
