"""
Utilities package for Task Resource Manager.

This package contains utility functions and constants.
"""

from .colors import COLOR_NAMES, DEFAULT_TASK_COLOR, WEB_COLORS
from .version import get_version, get_version_info

__all__ = [
    'COLOR_NAMES',
    'DEFAULT_TASK_COLOR',
    'WEB_COLORS',
    'get_version',
    'get_version_info',
]
