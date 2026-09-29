"""Crash + diagnostic logging to %APPDATA%\\NeonGrid\\logs."""

import datetime
import logging
import os
import platform
import sys
import traceback

from . import paths

_log_path = None


def log_dir():
    d = os.path.join(paths.data_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def setup():
    """Configure file logging and install a global exception hook."""
    global _log_path
    _log_path = os.path.join(log_dir(), "neongrid.log")
    # keep the previous session's log for comparison
    if os.path.exists(_log_path):
        try:
            os.replace(_log_path, _log_path + ".prev")
        except OSError:
            pass
    logging.basicConfig(
        filename=_log_path, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler(sys.stdout) if sys.stdout else None
    if console:
        console.setLevel(logging.INFO)
        logging.getLogger().addHandler(console)
    logging.info("NEON GRID starting - Python %s on %s", sys.version.split()[0],
                 platform.platform())
    sys.excepthook = _excepthook


def _excepthook(exc_type, exc, tb):
    write_crash(exc_type, exc, tb)
    sys.__excepthook__(exc_type, exc, tb)


def write_crash(exc_type=None, exc=None, tb=None, context=""):
    """Write a crash report and return its path."""
    if exc_type is None:
        exc_type, exc, tb = sys.exc_info()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(log_dir(), "crash_%s.log" % stamp)
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("NEON GRID crash report %s\n" % stamp)
            f.write("Python %s | %s\n" % (sys.version, platform.platform()))
            if context:
                f.write("Context: %s\n" % context)
            f.write("\n" + text)
        # also keep a rolling crash.log for quick access
        with open(os.path.join(paths.data_dir(), "crash.log"), "a", encoding="utf-8") as f:
            f.write("\n==== %s ====\n%s" % (stamp, text))
    except OSError:
        pass
    logging.error("CRASH: %s", text)
    return path
