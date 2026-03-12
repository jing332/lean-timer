from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace


class FakeVariant:
    def __init__(self, _signature: str, value: tuple[str, str]) -> None:
        self.value = value


class FakeUnpackValue:
    def __init__(self, value: object) -> None:
        self.value = value

    def unpack(self) -> object:
        return self.value


class FakeResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def unpack(self) -> object:
        return self.value


class FakeProxy:
    def __init__(
        self,
        *,
        name: str,
        interface_name: str,
        names: tuple[str, ...],
        playback_statuses: dict[str, str],
        calls: list[tuple[str, str]],
    ) -> None:
        self.name = name
        self.interface_name = interface_name
        self.names = names
        self.playback_statuses = playback_statuses
        self.calls = calls

    def call_sync(
        self,
        method: str,
        parameters,
        _flags: object,
        _timeout: int,
        _cancellable: object,
    ) -> FakeResult:
        if self.interface_name == "org.freedesktop.DBus" and method == "ListNames":
            return FakeResult((self.names,))
        if self.interface_name == "org.freedesktop.DBus.Properties" and method == "Get":
            _interface_name, property_name = parameters.value
            assert property_name == "PlaybackStatus"
            return FakeResult((FakeUnpackValue(self.playback_statuses[self.name]),))
        self.calls.append((self.name, method))
        return FakeResult(())


def _load_audio_focus_module() -> ModuleType:
    sys.modules.pop("lean_timer.audio_focus", None)
    fake_glib = SimpleNamespace(Error=RuntimeError, Variant=FakeVariant)
    fake_gio = SimpleNamespace(
        DBusProxy=SimpleNamespace(new_sync=lambda *_args, **_kwargs: None),
        DBusProxyFlags=SimpleNamespace(NONE=0),
        DBusCallFlags=SimpleNamespace(NONE=0),
        BusType=SimpleNamespace(SESSION=0),
        DBusConnection=object,
        bus_get_sync=lambda *_args, **_kwargs: None,
    )
    sys.modules["gi"] = SimpleNamespace()
    sys.modules["gi.repository"] = SimpleNamespace(Gio=fake_gio, GLib=fake_glib)
    return importlib.import_module("lean_timer.audio_focus")


def test_pause_active_players_only_pauses_playing() -> None:
    audio_focus = _load_audio_focus_module()
    names = (
        "org.mpris.MediaPlayer2.alpha",
        "org.mpris.MediaPlayer2.beta",
    )
    playback_statuses = {
        "org.mpris.MediaPlayer2.alpha": "Playing",
        "org.mpris.MediaPlayer2.beta": "Paused",
    }
    calls: list[tuple[str, str]] = []

    def proxy_factory(
        _bus: object,
        _flags: object,
        _info: object,
        name: str,
        _object_path: str,
        interface_name: str,
        _cancellable: object,
    ) -> FakeProxy:
        return FakeProxy(
            name=name,
            interface_name=interface_name,
            names=names,
            playback_statuses=playback_statuses,
            calls=calls,
        )

    controller = audio_focus.AudioFocusController(bus=object(), proxy_factory=proxy_factory)
    controller.pause_active_players()

    assert calls == [("org.mpris.MediaPlayer2.alpha", "Pause")]


def test_resume_paused_players_only_resumes_players_paused_by_controller() -> None:
    audio_focus = _load_audio_focus_module()
    names = ("org.mpris.MediaPlayer2.alpha",)
    playback_statuses = {"org.mpris.MediaPlayer2.alpha": "Playing"}
    calls: list[tuple[str, str]] = []

    def proxy_factory(
        _bus: object,
        _flags: object,
        _info: object,
        name: str,
        _object_path: str,
        interface_name: str,
        _cancellable: object,
    ) -> FakeProxy:
        return FakeProxy(
            name=name,
            interface_name=interface_name,
            names=names,
            playback_statuses=playback_statuses,
            calls=calls,
        )

    controller = audio_focus.AudioFocusController(bus=object(), proxy_factory=proxy_factory)
    controller.pause_active_players()
    controller.resume_paused_players()
    controller.resume_paused_players()

    assert calls == [
        ("org.mpris.MediaPlayer2.alpha", "Pause"),
        ("org.mpris.MediaPlayer2.alpha", "Play"),
    ]
