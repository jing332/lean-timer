from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Callable


class _MissingModule:
    def __getattr__(self, _name: str) -> object:
        raise RuntimeError("D-Bus tray runtime is unavailable")


_GI_AVAILABLE = False

try:
    gi_module_name = "".join(("g", "i"))
    gi = importlib.import_module(gi_module_name)
    gi.require_version("Gtk", "4.0")
    repository = importlib.import_module(f"{gi_module_name}.repository")
    Gio = repository.Gio
    GLib = repository.GLib
    _GI_AVAILABLE = True
except (ImportError, AttributeError, ValueError):
    Gio = _MissingModule()
    GLib = _MissingModule()


STATUS_NOTIFIER_WATCHER = "org.kde.StatusNotifierWatcher"
STATUS_NOTIFIER_WATCHER_PATH = "/StatusNotifierWatcher"
STATUS_NOTIFIER_WATCHER_INTERFACE = "org.kde.StatusNotifierWatcher"


def _interface_from_xml(xml: str):
    if not _GI_AVAILABLE:
        return None
    return Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]


SNI_NODE_INFO = _interface_from_xml(
    """
<?xml version="1.0" encoding="UTF-8"?>
<node>
    <interface name="org.kde.StatusNotifierItem">
        <property name="Category" type="s" access="read"/>
        <property name="Id" type="s" access="read"/>
        <property name="Title" type="s" access="read"/>
        <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
        <property name="Menu" type="o" access="read"/>
        <property name="ItemIsMenu" type="b" access="read"/>
        <property name="IconName" type="s" access="read"/>
        <property name="IconThemePath" type="s" access="read"/>
        <property name="Status" type="s" access="read"/>
        <property name="XAyatanaLabel" type="s" access="read"/>
        <method name="Activate">
            <arg type="i" direction="in"/>
            <arg type="i" direction="in"/>
        </method>
        <method name="SecondaryActivate">
            <arg type="i" direction="in"/>
            <arg type="i" direction="in"/>
        </method>
        <method name="ContextMenu">
            <arg type="i" direction="in"/>
            <arg type="i" direction="in"/>
        </method>
        <signal name="NewIcon"/>
        <signal name="NewTooltip"/>
        <signal name="NewStatus">
            <arg type="s" direction="out"/>
        </signal>
        <signal name="XAyatanaNewLabel">
            <arg type="s" direction="out"/>
            <arg type="s" direction="out"/>
        </signal>
    </interface>
</node>
"""
)

MENU_NODE_INFO = _interface_from_xml(
    """
<?xml version="1.0" encoding="UTF-8"?>
<node>
    <interface name="com.canonical.dbusmenu">
        <method name="GetLayout">
            <arg type="i" direction="in"/>
            <arg type="i" direction="in"/>
            <arg type="as" direction="in"/>
            <arg type="u" direction="out"/>
            <arg type="(ia{sv}av)" direction="out"/>
        </method>
        <method name="GetGroupProperties">
            <arg type="ai" name="ids" direction="in"/>
            <arg type="as" name="propertyNames" direction="in"/>
            <arg type="a(ia{sv})" name="properties" direction="out"/>
        </method>
        <method name="GetProperty">
            <arg type="i" name="id" direction="in"/>
            <arg type="s" name="name" direction="in"/>
            <arg type="v" name="value" direction="out"/>
        </method>
        <method name="Event">
            <arg type="i" direction="in"/>
            <arg type="s" direction="in"/>
            <arg type="v" direction="in"/>
            <arg type="u" direction="in"/>
        </method>
        <method name="EventGroup">
            <arg type="a(isvu)" name="events" direction="in"/>
            <arg type="ai" name="idErrors" direction="out"/>
        </method>
        <method name="AboutToShow">
            <arg type="i" direction="in"/>
            <arg type="b" direction="out"/>
        </method>
        <method name="AboutToShowGroup">
            <arg type="ai" name="ids" direction="in"/>
            <arg type="ai" name="updatesNeeded" direction="out"/>
            <arg type="ai" name="idErrors" direction="out"/>
        </method>
        <signal name="LayoutUpdated">
            <arg type="u"/>
            <arg type="i"/>
        </signal>
    </interface>
</node>
"""
)


def tray_runtime_available() -> bool:
    return _GI_AVAILABLE


def tray_support_hint() -> str:
    return (
        "Tray background mode uses StatusNotifierItem. On Ubuntu GNOME, install "
        "`gnome-shell-extension-appindicator` if the tray icon does not appear."
    )


def _idle_callback(callback: Callable[[], None]) -> bool:
    callback()
    return False


@dataclass(frozen=True)
class TrayMenuItem:
    item_id: int
    label: str
    callback: Callable[[], None] | None = None
    enabled: bool = True
    item_type: str = "standard"
    icon_name: str = ""
    hidden: bool = False

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.item_id,
            "label": self.label,
            "enabled": self.enabled,
            "type": self.item_type,
            "hidden": self.hidden,
        }
        if self.icon_name:
            payload["icon-name"] = self.icon_name
        if self.callback is not None:
            payload["callback"] = self.callback
        return payload


class _DBusService:
    def __init__(self, *, interface_info, object_path: str, bus: object) -> None:
        if not _GI_AVAILABLE or interface_info is None:
            raise RuntimeError("D-Bus tray runtime is unavailable")
        self._interface_info = interface_info
        self._object_path = object_path
        self._bus = bus
        self._registration_id: int | None = None

    def register(self) -> None:
        self._registration_id = self._bus.register_object(
            object_path=self._object_path,
            interface_info=self._interface_info,
            method_call_closure=self._on_method_call,
            get_property_closure=self._on_get_property,
        )
        if not self._registration_id:
            raise RuntimeError(f"Failed to register D-Bus object {self._object_path}")
        self._interface_info.cache_build()

    def unregister(self) -> None:
        self._interface_info.cache_release()
        if self._registration_id is not None:
            self._bus.unregister_object(self._registration_id)
            self._registration_id = None

    def emit_signal(self, signal_name: str, args: tuple[object, ...] | None = None) -> None:
        signal_info = self._interface_info.lookup_signal(signal_name)
        if signal_info is None:
            return
        parameters = None
        if signal_info.args:
            arg_types = "".join(arg.signature for arg in signal_info.args)
            parameters = GLib.Variant(f"({arg_types})", args)
        self._bus.emit_signal(
            destination_bus_name=None,
            object_path=self._object_path,
            interface_name=self._interface_info.name,
            signal_name=signal_name,
            parameters=parameters,
        )

    def _on_method_call(
        self,
        _connection,
        _sender,
        _path,
        _interface_name,
        method_name: str,
        parameters,
        invocation,
    ) -> None:
        method_info = self._interface_info.lookup_method(method_name)
        if method_info is None:
            invocation.return_dbus_error(
                "com.jing.lean_timer.MethodNotFound",
                f"Unknown D-Bus method: {method_name}",
            )
            return
        method = getattr(self, method_name)
        result = method(*parameters.unpack())
        if not method_info.out_args:
            invocation.return_value(None)
            return
        out_arg_types = "".join(arg.signature for arg in method_info.out_args)
        invocation.return_value(GLib.Variant(f"({out_arg_types})", result))

    def _on_get_property(
        self,
        _connection,
        _sender,
        _path,
        _interface_name,
        property_name: str,
    ):
        property_info = self._interface_info.lookup_property(property_name)
        if property_info is None:
            return None
        return GLib.Variant(property_info.signature, getattr(self, property_name))


class _DBusMenuService(_DBusService):
    def __init__(self, *, bus: object, items: list[dict[str, object]]) -> None:
        super().__init__(
            interface_info=MENU_NODE_INFO,
            object_path="/com/jing/lean_timer/Menu",
            bus=bus,
        )
        self._items: list[dict[str, object]] = []
        self._items_by_id: dict[int, dict[str, object]] = {}
        self._revision = 0
        self.set_items(items)

    def set_items(self, items: list[dict[str, object]]) -> None:
        self._items = items
        self._items_by_id = self._flatten_items(items)
        self._revision += 1
        if self._registration_id is not None:
            self.LayoutUpdated(self._revision, 0)

    def _flatten_items(self, items: list[dict[str, object]]) -> dict[int, dict[str, object]]:
        flat: dict[int, dict[str, object]] = {}
        for item in items:
            if bool(item.get("hidden", False)):
                continue
            item_id = self._item_id(item)
            if item_id is None:
                continue
            flat[item_id] = item
            children = item.get("children")
            if isinstance(children, list):
                flat.update(self._flatten_items(children))
        return flat

    @staticmethod
    def _item_id(item: dict[str, object]) -> int | None:
        value = item.get("id")
        return value if isinstance(value, int) else None

    def _item_properties(self, item: dict[str, object]) -> dict[str, object]:
        properties: dict[str, object] = {}
        for key in ("label", "icon-name", "type", "children-display"):
            value = item.get(key)
            if isinstance(value, str):
                properties[key] = GLib.Variant("s", value)
        enabled = item.get("enabled")
        if isinstance(enabled, bool):
            properties["enabled"] = GLib.Variant("b", enabled)
        return properties

    def _item_to_variant(self, item: dict[str, object], recursion_depth: int):
        if bool(item.get("hidden", False)):
            return None
        item_id = self._item_id(item)
        if item_id is None:
            return None
        children: list[object] = []
        if recursion_depth > 1 or recursion_depth == -1:
            child_items = item.get("children")
            if isinstance(child_items, list):
                children = [
                    variant
                    for variant in (
                        self._item_to_variant(child, recursion_depth - 1)
                        for child in child_items
                    )
                    if variant is not None
                ]
        return GLib.Variant(
            "(ia{sv}av)",
            (item_id, self._item_properties(item), children),
        )

    def _find_children(self, parent_id: int, items: list[dict[str, object]]) -> list[dict[str, object]]:
        if parent_id == 0:
            return items
        for item in items:
            if bool(item.get("hidden", False)):
                continue
            children = item.get("children")
            if not isinstance(children, list):
                continue
            item_id = self._item_id(item)
            if item_id == parent_id:
                return children
            found = self._find_children(parent_id, children)
            if found:
                return found
        return []

    def GetLayout(self, parent_id: int, recursion_depth: int, _property_names: list[str]):
        children = [
            variant
            for variant in (
                self._item_to_variant(item, recursion_depth)
                for item in self._find_children(parent_id, self._items)
            )
            if variant is not None
        ]
        return (
            self._revision,
            (0, {"children-display": GLib.Variant("s", "submenu")}, children),
        )

    def GetGroupProperties(self, ids: list[int], _property_names: list[str]):
        properties: list[tuple[int, dict[str, object]]] = []
        for item_id in ids:
            item = self._items_by_id.get(item_id)
            if item is not None:
                properties.append((item_id, self._item_properties(item)))
        return (properties,)

    def GetProperty(self, item_id: int, name: str):
        item = self._items_by_id.get(item_id)
        if item is None:
            return None
        return self._item_properties(item).get(name)

    def Event(self, item_id: int, event_id: str, _data, _timestamp: int) -> None:
        if event_id != "clicked":
            return
        item = self._items_by_id.get(item_id)
        callback = None if item is None else item.get("callback")
        if callable(callback):
            GLib.idle_add(_idle_callback, callback)

    def EventGroup(self, events: list[tuple[int, str, object, int]]):
        errors: list[int] = []
        for item_id, event_id, _data, _timestamp in events:
            item = self._items_by_id.get(item_id)
            if item is None:
                errors.append(item_id)
                continue
            if event_id != "clicked":
                continue
            callback = item.get("callback")
            if callable(callback):
                GLib.idle_add(_idle_callback, callback)
        return (errors,)

    def AboutToShow(self, _item_id: int):
        return (False,)

    def AboutToShowGroup(self, ids: list[int]):
        errors = [item_id for item_id in ids if item_id not in self._items_by_id]
        return ([], errors)

    def LayoutUpdated(self, revision: int, parent: int) -> None:
        self.emit_signal("LayoutUpdated", (revision, parent))


class _StatusNotifierItemService(_DBusService):
    Category = "ApplicationStatus"
    Status = "Active"
    ItemIsMenu = False
    IconThemePath = ""
    XAyatanaLabel = ""

    def __init__(
        self,
        *,
        bus: object,
        app_id: str,
        title: str,
        icon_name: str,
        menu_items: list[dict[str, object]],
        on_activate: Callable[[], None],
    ) -> None:
        super().__init__(
            interface_info=SNI_NODE_INFO,
            object_path="/com/jing/lean_timer/StatusNotifierItem",
            bus=bus,
        )
        self.Id = app_id
        self.Title = title
        self.IconName = icon_name
        self.ToolTip = ("", [], title, "")
        self._on_activate = on_activate
        self._menu = _DBusMenuService(bus=bus, items=menu_items)
        self.Menu = "/com/jing/lean_timer/Menu"

    def register(self) -> None:
        menu_registered = False
        item_registered = False
        try:
            self._menu.register()
            menu_registered = True
            super().register()
            item_registered = True
            watcher = Gio.DBusProxy.new_sync(
                connection=self._bus,
                flags=Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                info=None,
                name=STATUS_NOTIFIER_WATCHER,
                object_path=STATUS_NOTIFIER_WATCHER_PATH,
                interface_name=STATUS_NOTIFIER_WATCHER_INTERFACE,
                cancellable=None,
            )
            watcher.call_sync(
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self._object_path,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except Exception:
            if item_registered:
                try:
                    super().unregister()
                except Exception:
                    pass
            if menu_registered:
                try:
                    self._menu.unregister()
                except Exception:
                    pass
            raise

    def unregister(self) -> None:
        try:
            super().unregister()
        finally:
            self._menu.unregister()

    def Activate(self, _x: int, _y: int) -> None:
        GLib.idle_add(_idle_callback, self._on_activate)

    def SecondaryActivate(self, _x: int, _y: int) -> None:
        GLib.idle_add(_idle_callback, self._on_activate)

    def ContextMenu(self, _x: int, _y: int) -> None:
        return None

    def set_icon(self, icon_name: str) -> None:
        self.IconName = icon_name
        self.emit_signal("NewIcon")

    def set_tooltip(self, title: str, description: str) -> None:
        self.ToolTip = ("", [], title, description)
        self.emit_signal("NewTooltip")

    def set_status(self, status: str) -> None:
        self.Status = status
        self.emit_signal("NewStatus", (status,))

    def set_menu_items(self, items: list[dict[str, object]]) -> None:
        self._menu.set_items(items)


class TrayIcon:
    def __init__(self, service: _StatusNotifierItemService) -> None:
        self._service = service

    @classmethod
    def create(
        cls,
        *,
        app_id: str,
        title: str,
        icon_name: str,
        on_activate: Callable[[], None],
        menu_items: list[TrayMenuItem],
    ) -> "TrayIcon | None":
        if not tray_runtime_available() or SNI_NODE_INFO is None or MENU_NODE_INFO is None:
            return None
        service = None
        try:
            session_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            Gio.DBusProxy.new_sync(
                connection=session_bus,
                flags=Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                info=None,
                name=STATUS_NOTIFIER_WATCHER,
                object_path=STATUS_NOTIFIER_WATCHER_PATH,
                interface_name=STATUS_NOTIFIER_WATCHER_INTERFACE,
                cancellable=None,
            )
            service = _StatusNotifierItemService(
                bus=session_bus,
                app_id=app_id,
                title=title,
                icon_name=icon_name,
                menu_items=[item.to_payload() for item in menu_items],
                on_activate=on_activate,
            )
            service.register()
        except Exception:
            if service is not None:
                try:
                    service.unregister()
                except Exception:
                    pass
            return None
        return cls(service)

    def shutdown(self) -> None:
        try:
            self._service.unregister()
        except Exception:
            return

    def set_icon(self, icon_name: str) -> None:
        self._service.set_icon(icon_name)

    def set_tooltip(self, title: str, description: str) -> None:
        self._service.set_tooltip(title, description)

    def set_status(self, status: str) -> None:
        self._service.set_status(status)

    def set_menu_items(self, menu_items: list[TrayMenuItem]) -> None:
        self._service.set_menu_items([item.to_payload() for item in menu_items])
