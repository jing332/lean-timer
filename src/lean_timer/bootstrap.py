from __future__ import annotations

import importlib.util
import os
import sys


REQUIRED_APT_PACKAGES = (
    "python3-gi",
    "gir1.2-gtk-4.0",
    "gir1.2-notify-0.7",
)

TRAY_SUPPORT_NOTE = (
    "Tray background mode uses StatusNotifierItem. On Ubuntu GNOME, install "
    "gnome-shell-extension-appindicator if the tray icon does not appear."
)


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _has_display_session() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def runtime_check(*, require_display: bool) -> tuple[bool, str]:
    if not _has_module("gi"):
        packages = " ".join(REQUIRED_APT_PACKAGES)
        return (
            False,
            "Missing PyGObject runtime. Install Ubuntu packages:\n"
            f"  sudo apt install -y {packages}",
        )
    if require_display and not _has_display_session():
        return (
            False,
            "No graphical display session detected. Launch this app from the Ubuntu desktop session.",
        )
    return True, f"Runtime dependencies look available.\n{TRAY_SUPPORT_NOTE}"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--self-check" in args
    ok, message = runtime_check(require_display=not check_only)

    if check_only:
        print(message)
        return 0 if ok else 1

    if not ok:
        print(message, file=sys.stderr)
        return 1

    from lean_timer.app import main as app_main

    try:
        app_main()
    except RuntimeError as exc:
        print(f"Unable to start GTK application: {exc}", file=sys.stderr)
        if not _has_display_session():
            print(
                "Hint: make sure you run this inside a logged-in Ubuntu desktop session.",
                file=sys.stderr,
            )
        return 1
    return 0
