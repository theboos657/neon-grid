"""Build NEON GRID for Windows.

    python build.py                 # PyInstaller folder build + Inno Setup installer
    python build.py --onefile       # single self-extracting .exe instead of a folder
    python build.py --no-installer  # skip Inno Setup
    python build.py --clean         # wipe build/ and dist/ first

Outputs
    dist/NeonGrid/NeonGrid.exe               (folder build, recommended: fast start)
    dist/NeonGrid.exe                        (--onefile)
    installer/NeonGrid-Setup-<version>.exe   (Inno Setup 6, if ISCC.exe is found)
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from neon_shared import GAME_VERSION  # noqa: E402

APP = "NeonGrid"


def run(cmd, **kw):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT, **kw)


def ensure_assets():
    if not os.path.exists(os.path.join(ROOT, "assets", "icon.ico")):
        run([sys.executable, os.path.join("tools", "make_icon.py")])
    voice = os.path.join(ROOT, "assets", "voice")
    if not os.path.isdir(voice) or not os.listdir(voice):
        print("Generating announcer voice lines (Windows speech synthesizer)...")
        try:
            run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 os.path.join("tools", "gen_voice.ps1")])
        except (OSError, subprocess.CalledProcessError):
            print("  (voice generation failed - the game will run without announcer audio)")


def pyinstaller(onefile):
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "main.py", "--name", APP, "--noconfirm",
           "--windowed", "--icon", os.path.join("assets", "icon.ico"),
           "--add-data", "assets%sassets" % sep,
           # Panda3D loads its renderer/audio plugins and Config.prc dynamically
           "--collect-all", "panda3d",
           "--collect-submodules", "direct.gui",
           "--collect-submodules", "direct.filter",
           "--collect-submodules", "direct.showbase",
           "--collect-submodules", "direct.task",
           "--collect-submodules", "direct.interval",
           "--hidden-import", "neon_shared.server_core",
           "--exclude-module", "tkinter",
           "--exclude-module", "direct.tkpanels",
           "--exclude-module", "direct.tkwidgets",
           "--exclude-module", "matplotlib",
           "--exclude-module", "tests"]
    cmd.append("--onefile" if onefile else "--onedir")
    run(cmd)


def find_iscc():
    cands = [shutil.which("ISCC"), shutil.which("iscc")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if base:
            cands.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def installer():
    iscc = find_iscc()
    if iscc is None:
        print("\nInno Setup 6 not found - skipping installer.\n"
              "Install it from https://jrsoftware.org/isdl.php and re-run, or compile setup.iss "
              "manually.")
        return False
    os.makedirs(os.path.join(ROOT, "installer"), exist_ok=True)
    run([iscc, "/DAppVersion=%s" % GAME_VERSION, "setup.iss"])
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onefile", action="store_true")
    ap.add_argument("--no-installer", action="store_true")
    ap.add_argument("--clean", action="store_true")
    a = ap.parse_args()
    if a.clean:
        for d in ("build", "dist"):
            shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    ensure_assets()
    pyinstaller(a.onefile)
    exe = os.path.join(ROOT, "dist", APP + ".exe") if a.onefile else \
        os.path.join(ROOT, "dist", APP, APP + ".exe")
    print("\nBuilt:", exe)
    if not a.no_installer:
        if a.onefile:
            print("Installer packaging expects the folder build; skipping for --onefile.")
        else:
            installer()


if __name__ == "__main__":
    main()
