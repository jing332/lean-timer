from __future__ import annotations

import shutil
import subprocess

from gi.repository import Gdk, Notify


class AlertService:
    def __init__(self, app_name: str = "Lean Timer") -> None:
        self._notify_ready = Notify.init(app_name)

    def notify(self, title: str, body: str) -> None:
        if self._notify_ready:
            n = Notify.Notification.new(title, body, None)
            n.show()
            return
        notify_send = shutil.which("notify-send")
        if notify_send:
            subprocess.run([notify_send, title, body], check=False)

    def beep(self) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            display.beep()
            return
        paplay = shutil.which("paplay")
        if paplay:
            subprocess.run(
                [paplay, "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                check=False,
            )
