"""Story mode hook.

The campaign ships as a separate module.  To plug one in, provide a package
named ``neongrid_story`` (anywhere on sys.path, or drop it in the game folder)
exposing:

    def launch(app) -> None
        Take over from the main menu.  ``app`` is the NeonGridApp: use
        app.start_match(config) to run arena encounters, app.menus for UI and
        app.quit_to_menu() to return.

    TITLE = "..."   (optional, shown on the menu button)

Until such a module exists the menu shows a "coming soon" panel.
"""

import importlib
import logging

log = logging.getLogger("story")


def find_module():
    try:
        return importlib.import_module("neongrid_story")
    except ImportError:
        return None
    except Exception:
        log.exception("Story module failed to import")
        return None


def available():
    return find_module() is not None


def launch(app):
    mod = find_module()
    if mod is None or not hasattr(mod, "launch"):
        return False
    mod.launch(app)
    return True
