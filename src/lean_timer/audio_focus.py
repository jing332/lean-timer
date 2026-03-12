from __future__ import annotations

from collections.abc import Callable

from gi.repository import Gio, GLib


class AudioFocusController:
    def __init__(
        self,
        bus: Gio.DBusConnection | None = None,
        proxy_factory: Callable[..., Gio.DBusProxy] | None = None,
    ) -> None:
        self._bus = bus
        self._proxy_factory = proxy_factory or Gio.DBusProxy.new_sync
        self._paused_player_names: set[str] = set()

    def pause_active_players(self) -> None:
        for name in self._player_names():
            if self._playback_status(name) != "Playing":
                continue
            if self._call_player_method(name, "Pause"):
                self._paused_player_names.add(name)

    def resume_paused_players(self) -> None:
        paused_names = tuple(self._paused_player_names)
        self._paused_player_names.clear()
        for name in paused_names:
            self._call_player_method(name, "Play")

    def _player_names(self) -> tuple[str, ...]:
        bus_proxy = self._make_proxy(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
        )
        if bus_proxy is None:
            return ()
        try:
            result = bus_proxy.call_sync(
                "ListNames",
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error:
            return ()
        names = result.unpack()[0]
        return tuple(name for name in names if name.startswith("org.mpris.MediaPlayer2."))

    def _playback_status(self, name: str) -> str | None:
        proxy = self._make_proxy(
            name,
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties",
        )
        if proxy is None:
            return None
        try:
            result = proxy.call_sync(
                "Get",
                GLib.Variant(
                    "(ss)",
                    ("org.mpris.MediaPlayer2.Player", "PlaybackStatus"),
                ),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error:
            return None
        status_variant = result.unpack()[0]
        return status_variant.unpack()

    def _call_player_method(self, name: str, method: str) -> bool:
        proxy = self._make_proxy(
            name,
            "/org/mpris/MediaPlayer2",
            "org.mpris.MediaPlayer2.Player",
        )
        if proxy is None:
            return False
        try:
            proxy.call_sync(
                method,
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except GLib.Error:
            return False
        return True

    def _make_proxy(
        self,
        name: str,
        object_path: str,
        interface_name: str,
    ) -> Gio.DBusProxy | None:
        bus = self._ensure_bus()
        if bus is None:
            return None
        try:
            return self._proxy_factory(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                name,
                object_path,
                interface_name,
                None,
            )
        except GLib.Error:
            return None

    def _ensure_bus(self) -> Gio.DBusConnection | None:
        if self._bus is not None:
            return self._bus
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            self._bus = None
        return self._bus
