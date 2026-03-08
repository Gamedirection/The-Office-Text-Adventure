"""Main launcher for the Office Text Adventure template."""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import site
import subprocess
import sys

from engine.game_engine import GameEngine
from ui.tui.main import run_tui


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Office Text Adventure Launcher")
    parser.add_argument(
        "--mode",
        choices=["tui", "gui"],
        default="tui",
        help="Select interface mode. Defaults to terminal UI.",
    )
    return parser.parse_args()


def ensure_pyside6_installed() -> bool:
    """Ensure PySide6 exists before launching GUI mode."""
    if importlib.util.find_spec("PySide6") is not None:
        return True

    vendor_dir = Path(os.environ.get("LOCALAPPDATA", ".")) / "ovj_pydeps" / "pyside6"
    if _try_enable_vendor_pyside6(vendor_dir):
        return True

    print("PySide6 is not installed, so GUI mode cannot start yet.")
    try:
        answer = input("Install PySide6 now? [y/N]: ").strip().lower()
    except EOFError:
        return False

    if answer not in {"y", "yes"}:
        print("Skipping install. Use '--mode tui' or install PySide6 manually.")
        return False

    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6==6.8.2.1"])
    except subprocess.CalledProcessError:
        print("Default install failed. Retrying with a short local path...")
        try:
            vendor_dir.mkdir(parents=True, exist_ok=True)
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--target",
                    str(vendor_dir),
                    "PySide6==6.8.2.1",
                ]
            )
        except subprocess.CalledProcessError:
            print("PySide6 installation failed.")
            print(
                "Try manually: "
                f'"{sys.executable}" -m pip install --target "{vendor_dir}" PySide6==6.8.2.1'
            )
            print("Then re-run launcher with --mode gui.")
            return False

    if importlib.util.find_spec("PySide6") is None and not _try_enable_vendor_pyside6(vendor_dir):
        print("PySide6 still was not detected after installation.")
        return False

    print("PySide6 installed successfully.")
    return True


def _try_enable_vendor_pyside6(vendor_dir: Path) -> bool:
    if not vendor_dir.exists():
        return False
    site.addsitedir(str(vendor_dir))
    return importlib.util.find_spec("PySide6") is not None


def main() -> None:
    args = parse_args()
    engine = GameEngine()

    if args.mode == "gui":
        if not ensure_pyside6_installed():
            return
        from ui.gui.main import run_gui

        run_gui(engine)
        return

    run_tui(engine)


if __name__ == "__main__":
    main()
