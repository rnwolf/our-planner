"""
Version utilities for the Task Resource Manager application.

This module provides functions for accessing version information.
"""


def get_version():
    """Return the current application version.

    Returns:
        str: The version string
    """
    try:
        import src

        return src.__version__
    except (ImportError, AttributeError):
        return '0.1.0'  # Default fallback version


def get_version_info():
    """Return detailed version information.

    Returns:
        dict: A dictionary containing version details
    """
    version = get_version()
    version_parts = version.split('.')

    return {
        'version': version,
        'major': int(version_parts[0]) if len(version_parts) > 0 else 0,
        'minor': int(version_parts[1]) if len(version_parts) > 1 else 0,
        'patch': int(version_parts[2]) if len(version_parts) > 2 else 0,
    }
