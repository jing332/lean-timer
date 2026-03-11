from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from gi.repository import Notify


NOTIFICATION_TIMEOUT_MS = 3000


class AlertService:
    def __init__(self, app_name: str = "Lean Timer") -> None:
        self._notify_ready = Notify.init(app_name)
        sounds_dir = Path(__file__).resolve().parent / "sounds"
        self._complete_sound_path = sounds_dir / "complete.oga"
        self._start_sound_path = sounds_dir / "start.oga"

    def notify(self, title: str, body: str) -> None:
        if self._notify_ready:
            n = Notify.Notification.new(title, body, None)
            n.set_timeout(NOTIFICATION_TIMEOUT_MS)
            n.show()
            return
        notify_send = shutil.which("notify-send")
        if notify_send:
            subprocess.run(
                [notify_send, "-t", str(NOTIFICATION_TIMEOUT_MS), title, body],
                check=False,
            )

    def beep(self) -> None:
        self._play_sound(self._complete_sound_path)

    def play_start(self) -> None:
        self._play_sound(self._start_sound_path)

    @staticmethod
    def _play_sound(sound_path: Path) -> None:
        if not sound_path.exists():
            return

        paplay = shutil.which("paplay")
        if paplay:
            AlertService._launch_background([paplay, str(sound_path)])
            return

        canberra_gtk_play = shutil.which("canberra-gtk-play")
        if canberra_gtk_play:
            AlertService._launch_background([canberra_gtk_play, "--file", str(sound_path)])

    @staticmethod
    def _launch_background(args: list[str]) -> None:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
