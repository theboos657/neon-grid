"""Filesystem locations.

All user data lives in %APPDATA%\\NeonGrid (JSON files, crash log, generated
audio cache).  Read-only game assets live next to the code, or inside the
PyInstaller bundle when frozen.
"""

import os
import sys

APP_NAME = "NeonGrid"


def resource_root():
    """Directory containing the ``assets`` folder (works frozen and unfrozen)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset(*parts):
    return os.path.join(resource_root(), "assets", *parts)


def data_dir():
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def data_file(name):
    return os.path.join(data_dir(), name)


def cache_dir(sub=""):
    path = os.path.join(data_dir(), "cache", sub) if sub else os.path.join(data_dir(), "cache")
    os.makedirs(path, exist_ok=True)
    return path
