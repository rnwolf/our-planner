"""
Task Resource Manager

A Tkinter application for managing tasks and resources with timeline visualization.
"""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("our-planner")
except PackageNotFoundError:
    __version__ = "unknown"

__author__ = 'R.N. Wolf'
