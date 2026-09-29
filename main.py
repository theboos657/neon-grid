"""NEON GRID - entry point.

    python main.py                 normal launch
    python main.py --mode endless  jump straight into a mode (ffa/duel/team/coop/endless)
    python main.py --autotest ffa --autoplay --offscreen --duration 30 --shots DIR
                                   automated smoke test (used during development)
"""

import argparse
import logging
import os
import sys

# make ``neon_shared`` and ``game`` importable when run from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import crashlog  # noqa: E402


def parse_args(argv):
    ap = argparse.ArgumentParser(description="NEON GRID")
    ap.add_argument("--mode", help="start a match immediately in this mode")
    ap.add_argument("--autotest", help="run an automated match in this mode")
    ap.add_argument("--autoplay", action="store_true", help="bot controls the player")
    ap.add_argument("--offscreen", action="store_true", help="render without a window")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--shots", help="directory for autotest screenshots")
    ap.add_argument("--shot-interval", type=float, default=4.0)
    ap.add_argument("--menutest", action="store_true", help="screenshot every menu")
    ap.add_argument("--nettest", action="store_true", help="LAN end-to-end test with a net bot")
    ap.add_argument("--weapon", help="test hook: force the primary weapon id")
    ap.add_argument("--mods", help="test hook: slot=id,... fitted on the primary")
    ap.add_argument("--endat", type=float, help="test hook: force a win at this time")
    ap.add_argument("--fxtest", action="store_true", help="test hook: explosion showcase")
    ap.add_argument("--difficulty", default="normal",
                    choices=["easy", "normal", "hard", "nightmare"])
    ap.add_argument("--ads", action="store_true", help="test hook: hold aim-down-sights")
    ap.add_argument("--chaos", action="store_true")
    ap.add_argument("--lives", action="store_true")
    ap.add_argument("--lang", choices=["en", "he"])
    ap.add_argument("--quality", choices=["high", "low"])
    return ap.parse_args(argv)


def main(argv=None):
    crashlog.setup()
    args = parse_args(sys.argv[1:] if argv is None else argv)
    opts = {"offscreen": args.offscreen, "autoplay": args.autoplay,
            "duration": args.duration, "shots_dir": args.shots,
            "shot_interval": args.shot_interval, "menutest": args.menutest,
            "nettest": args.nettest, "weapon": args.weapon,
            "endat": args.endat, "mods": args.mods, "fxtest": args.fxtest, "quality": args.quality,
            "lang": args.lang, "ads": args.ads}
    mode = args.autotest or args.mode
    if mode:
        cfg = {"mode": mode, "bots": 5, "difficulty": args.difficulty, "lives": args.lives,
               "lives_count": 3, "chaos": args.chaos, "time_limit": 8, "score_limit": 25}
        opts["autotest" if args.autotest else "start"] = cfg
        if args.mode and not args.autotest:
            opts["autotest"] = None
    try:
        from game.app import NeonGridApp

        app = NeonGridApp(opts)
        if args.mode and not args.autotest:
            app.start_match(opts["start"])
        app.run()
    except SystemExit:
        raise
    except Exception:
        path = crashlog.write_crash(context="startup/run")
        logging.error("Fatal error, crash report: %s", path)
        _show_fatal(path)
        return 1
    return 0


def _show_fatal(path):
    """Best-effort native message box so frozen builds don't fail silently."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, "NEON GRID crashed.\n\nA crash report was saved to:\n%s" % path,
            "NEON GRID", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
