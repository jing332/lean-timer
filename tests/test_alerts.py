from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace


class FakeNotification:
    def __init__(self, title: str, body: str, icon: str | None) -> None:
        self.title = title
        self.body = body
        self.icon = icon
        self.timeout: int | None = None
        self.shown = False

    def set_timeout(self, timeout: int) -> None:
        self.timeout = timeout

    def show(self) -> None:
        self.shown = True


def _load_alerts_module(notify_module: object) -> ModuleType:
    sys.modules.pop("lean_timer.alerts", None)
    sys.modules["gi"] = SimpleNamespace()
    sys.modules["gi.repository"] = SimpleNamespace(Notify=notify_module)
    return importlib.import_module("lean_timer.alerts")


def test_notify_sets_libnotify_timeout_to_3_seconds() -> None:
    created: list[FakeNotification] = []

    def new_notification(title: str, body: str, icon: str | None) -> FakeNotification:
        notification = FakeNotification(title, body, icon)
        created.append(notification)
        return notification

    notify_module = SimpleNamespace(
        init=lambda _app_name: True,
        Notification=SimpleNamespace(new=new_notification),
    )

    alerts = _load_alerts_module(notify_module)
    service = alerts.AlertService()
    service.notify("title", "body")

    assert len(created) == 1
    assert created[0].timeout == alerts.NOTIFICATION_TIMEOUT_MS == 3000
    assert created[0].shown is True


def test_notify_send_uses_3_second_timeout(monkeypatch) -> None:
    notify_module = SimpleNamespace(
        init=lambda _app_name: False,
        Notification=SimpleNamespace(new=lambda *_args: None),
    )

    alerts = _load_alerts_module(notify_module)
    calls: list[list[str]] = []
    monkeypatch.setattr(alerts.shutil, "which", lambda name: "/usr/bin/notify-send" if name == "notify-send" else None)
    monkeypatch.setattr(alerts.subprocess, "run", lambda args, check: calls.append(args))

    service = alerts.AlertService()
    service.notify("title", "body")

    assert calls == [["/usr/bin/notify-send", "-t", "3000", "title", "body"]]
