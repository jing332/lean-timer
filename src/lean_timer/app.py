from __future__ import annotations

import math
import time
from typing import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Notify", "0.7")

from gi.repository import Gdk, Gio, GLib, Gtk

from lean_timer.alerts import AlertService
from lean_timer.config import AppConfig, load_config, save_config
from lean_timer.tray import TrayIcon, TrayMenuItem
from lean_timer.timer_engine import (
    DeepFocusPhase,
    DisplayState,
    PomodoroPhase,
    TimerEngine,
    TimerMode,
)


class MicroRestOverlay(Gtk.Window):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.set_title("闭眼休息")
        if hasattr(self, "set_decorated"):
            self.set_decorated(False)
        if hasattr(self, "set_opacity"):
            self.set_opacity(0.75)
        if hasattr(self, "set_modal"):
            self.set_modal(False)
        if hasattr(self, "set_resizable"):
            self.set_resizable(False)
        if hasattr(self, "set_can_focus"):
            self.set_can_focus(True)
        if hasattr(self, "set_can_target"):
            self.set_can_target(True)
        if hasattr(self, "set_hide_on_close"):
            self.set_hide_on_close(True)
        if hasattr(self, "set_focusable"):
            self.set_focusable(True)
        if hasattr(self, "set_can_default"):
            self.set_can_default(True)
        if hasattr(self, "set_default_size"):
            self.set_default_size(1920, 1080)
        if hasattr(self, "set_keep_above"):
            self.set_keep_above(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)

        title = Gtk.Label(label="闭上眼睛休息")
        title.set_markup('<span size="26000" weight="bold">闭上眼睛休息</span>')
        self.countdown_label = Gtk.Label(label="00:10")
        self.countdown_label.set_markup(self._format_big_mmss(10))
        hint = Gtk.Label(label="10 秒后继续专注")
        hint.set_markup('<span size="18000">10 秒后继续专注</span>')

        box.append(title)
        box.append(self.countdown_label)
        box.append(hint)
        self.set_child(box)

    def show_countdown(self, seconds: int, parent: Gtk.Window) -> None:
        self.countdown_label.set_markup(self._format_big_mmss(seconds))
        if hasattr(self, "set_transient_for"):
            self.set_transient_for(None)
        if hasattr(self, "set_modal"):
            self.set_modal(False)
        self.present()
        if hasattr(self, "set_fullscreened"):
            self.set_fullscreened(True)
        if hasattr(self, "fullscreen"):
            self.fullscreen()

    def update_countdown(self, seconds: int) -> None:
        self.countdown_label.set_markup(self._format_big_mmss(seconds))

    @staticmethod
    def _format_mmss(seconds: int) -> str:
        minutes = seconds // 60
        remain = seconds % 60
        return f"{minutes:02d}:{remain:02d}"

    @classmethod
    def _format_big_mmss(cls, seconds: int) -> str:
        return f'<span size="42000" weight="bold">{cls._format_mmss(seconds)}</span>'


class MicroRestPrompt(Gtk.Window):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.set_title("微休息提示")
        self.set_default_size(360, 180)
        if hasattr(self, "set_modal"):
            self.set_modal(False)
        if hasattr(self, "set_decorated"):
            self.set_decorated(False)
        if hasattr(self, "set_resizable"):
            self.set_resizable(False)
        if hasattr(self, "set_opacity"):
            self.set_opacity(0.94)

        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(22)
        box.set_margin_bottom(22)
        box.set_margin_start(22)
        box.set_margin_end(22)

        badge = Gtk.Label()
        badge.set_markup('<span size="14000" alpha="75%">微休息提醒</span>')
        title = Gtk.Label()
        title.set_markup('<span size="22000" weight="bold">闭上眼睛，暂停 10 秒</span>')
        self.countdown_label = Gtk.Label()
        self.countdown_label.set_markup('<span size="32000" weight="bold">00:10</span>')
        hint = Gtk.Label()
        hint.set_markup('<span size="14000" alpha="75%">倒计时结束后继续当前任务</span>')

        for widget in (badge, title, self.countdown_label, hint):
            widget.set_halign(Gtk.Align.CENTER)

        box.append(badge)
        box.append(title)
        box.append(self.countdown_label)
        box.append(hint)
        frame.set_child(box)
        self.set_child(frame)

    def show_countdown(self, seconds: int, parent: Gtk.Window) -> None:
        self.update_countdown(seconds)
        self.set_transient_for(parent)
        if hasattr(self, "set_keep_above"):
            self.set_keep_above(True)
        self.present()

    def update_countdown(self, seconds: int) -> None:
        text = self._format_mmss(seconds)
        self.countdown_label.set_markup(f'<span size="32000" weight="bold">{text}</span>')

    @staticmethod
    def _format_mmss(seconds: int) -> str:
        minutes = seconds // 60
        remain = seconds % 60
        return f"{minutes:02d}:{remain:02d}"


class DeepFocusSettingsDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(transient_for=parent, modal=True)
        self.set_title("参数设置")
        self.set_default_size(360, 360)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        frame = Gtk.Frame(label="参数设置")
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        frame.set_child(grid)
        self.grid = grid

        # Close button at bottom
        close_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        close_box.set_halign(Gtk.Align.END)
        close_box.set_margin_top(8)
        close_box.set_margin_bottom(8)
        close_box.set_margin_start(12)
        close_box.set_margin_end(12)
        close_btn = Gtk.Button(label="关闭")
        close_btn.connect("clicked", self._on_close_clicked)
        close_box.append(close_btn)

        main_box.append(frame)
        main_box.append(close_box)
        self.set_child(main_box)

        # Hide minimize/maximize buttons, keep only close button
        if hasattr(self, "set_deletable"):
            self.set_deletable(True)
        if hasattr(self, "set_decorated"):
            self.set_decorated(False)

    def _on_close_clicked(self, _btn: Gtk.Button) -> None:
        self.hide()


class RunningTimerCloseDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window, on_confirm: Callable[[], None]) -> None:
        super().__init__(transient_for=parent, modal=True)
        self.set_title("结束计时？")
        self.set_default_size(380, 220)
        self._on_confirm = on_confirm

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        frame = Gtk.Frame(label="关闭提示")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        title = Gtk.Label()
        title.set_halign(Gtk.Align.START)
        title.set_wrap(True)
        title.set_markup('<span weight="bold" size="16000">当前有计时正在进行</span>')

        body = Gtk.Label(
            label=(
                "如果现在关闭窗口，程序会退出，当前计时也会结束。\n"
                "如需关闭时收起到托盘，可在“参数设置”中启用该功能。"
            )
        )
        body.set_halign(Gtk.Align.START)
        body.set_wrap(True)

        content.append(title)
        content.append(body)
        frame.set_child(content)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        actions.set_margin_top(8)
        actions.set_margin_bottom(8)
        actions.set_margin_start(12)
        actions.set_margin_end(12)

        cancel_btn = Gtk.Button(label="继续计时")
        cancel_btn.connect("clicked", self._on_cancel_clicked)
        confirm_btn = Gtk.Button(label="结束并退出")
        confirm_btn.connect("clicked", self._on_confirm_clicked)

        actions.append(cancel_btn)
        actions.append(confirm_btn)

        main_box.append(frame)
        main_box.append(actions)
        self.set_child(main_box)

    def _on_cancel_clicked(self, _btn: Gtk.Button) -> None:
        self.hide()

    def _on_confirm_clicked(self, _btn: Gtk.Button) -> None:
        self.hide()
        self._on_confirm()

    def do_close_request(self) -> bool:
        self.hide()
        return True


class CircularTimerFace(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        self._progress = 0.0
        self._accent = (0.22, 0.73, 0.54)

        overlay = Gtk.Overlay()
        overlay.set_size_request(260, 260)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_content_width(260)
        self.drawing_area.set_content_height(260)
        self.drawing_area.set_draw_func(self._draw)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)

        self.caption_label = Gtk.Label(label="")
        self.caption_label.set_markup('<span size="15000" alpha="75%">准备开始</span>')
        self.time_label = Gtk.Label(label="")
        self.time_label.set_markup('<span size="32000" weight="bold">00:00:00</span>')

        center.append(self.caption_label)
        center.append(self.time_label)

        overlay.set_child(self.drawing_area)
        overlay.add_overlay(center)
        self.append(overlay)

    def update_face(
        self,
        *,
        time_text: str,
        caption: str,
        progress: float,
        accent: tuple[float, float, float],
    ) -> None:
        self._progress = max(0.0, min(progress, 1.0))
        self._accent = accent
        self.time_label.set_markup(
            f'<span size="32000" weight="bold">{GLib.markup_escape_text(time_text)}</span>'
        )
        self.caption_label.set_markup(
            f'<span size="15000" alpha="75%">{GLib.markup_escape_text(caption)}</span>'
        )
        self.drawing_area.queue_draw()

    def _draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 14
        line_width = 14

        cr.set_source_rgba(0.14, 0.16, 0.20, 0.22)
        cr.set_line_width(line_width)
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.stroke()

        cr.set_source_rgba(self._accent[0], self._accent[1], self._accent[2], 0.95)
        cr.set_line_width(line_width)
        cr.set_line_cap(1)
        start = -math.pi / 2
        end = start + 2 * math.pi * self._progress
        cr.arc(center_x, center_y, radius, start, end)
        cr.stroke()


class LeanTimerWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.set_title("学习时钟")
        self.set_default_size(420, 340)

        self.config = load_config()
        self.default_config = AppConfig()
        self.engine = TimerEngine(
            mode=self._default_mode(),
            pomodoro_focus_minutes=self.config.pomodoro_focus_minutes,
            pomodoro_break_minutes=self.config.pomodoro_break_minutes,
            milestones_minutes=self.config.milestones_minutes,
            deep_focus_minutes=self.config.deep_focus_minutes,
            deep_break_minutes=self.config.deep_break_minutes,
            random_prompt_min_minutes=self.config.random_prompt_min_minutes,
            random_prompt_max_minutes=self.config.random_prompt_max_minutes,
            micro_rest_seconds=self.config.micro_rest_seconds,
        )
        self.alerts = AlertService(app_name="Lean Timer")
        self.overlay_window = MicroRestOverlay(app)
        self.prompt_window = MicroRestPrompt(app)
        self.running_timer_close_dialog = RunningTimerCloseDialog(
            self,
            self._confirm_close_running_timer,
        )
        self._allow_shutdown = False
        self._hidden_to_tray = False
        self.connect("close-request", self._on_close_request)

        self._build_ui()
        self._apply_window_preferences()
        self._sync_deep_focus_controls()
        self._refresh_ui()

        GLib.timeout_add(250, self._on_tick)

    def _default_mode(self) -> TimerMode:
        if self.config.mode_default == TimerMode.POMODORO.value:
            return TimerMode.POMODORO
        if self.config.mode_default == TimerMode.DEEP_FOCUS.value:
            return TimerMode.DEEP_FOCUS
        return TimerMode.COUNTUP

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # Use Gtk.DropDown instead of deprecated ComboBoxText
        self.mode_strings = Gtk.StringList()
        self.mode_strings.append("正计时")
        self.mode_strings.append("番茄钟")
        self.mode_strings.append("深度专注")
        self.mode_combo = Gtk.DropDown(model=self.mode_strings)
        self.mode_combo.set_selected(self._mode_to_index(self.engine.mode))
        self.mode_combo.connect("notify::selected", self._on_mode_changed)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.END)
        self.status_label.set_hexpand(True)

        top.append(self.mode_combo)
        top.append(self.status_label)

        self.timer_face = CircularTimerFace()
        self.phase_label = Gtk.Label(label="")
        self.info_label = Gtk.Label(label="")
        self.info_label.set_wrap(True)

        self.deep_focus_settings_btn = Gtk.Button(label="⚙ 参数设置")
        self.deep_focus_settings_btn.connect("clicked", self._on_open_settings_dialog)

        self.settings_dialog = DeepFocusSettingsDialog(self)
        self.settings_dialog.connect("close-request", self._on_settings_dialog_close_request)
        grid = self.settings_dialog.grid

        self.deep_focus_minutes_spin = self._make_spin(
            self.config.deep_focus_minutes,
            30,
            240,
            1,
        )
        self.deep_break_minutes_spin = self._make_spin(
            self.config.deep_break_minutes,
            5,
            60,
            1,
        )
        self.random_prompt_min_spin = self._make_spin(
            self.config.random_prompt_min_minutes,
            1,
            30,
            1,
        )
        self.random_prompt_max_spin = self._make_spin(
            self.config.random_prompt_max_minutes,
            1,
            30,
            1,
        )

        for widget in (
            self.deep_focus_minutes_spin,
            self.deep_break_minutes_spin,
            self.random_prompt_min_spin,
            self.random_prompt_max_spin,
        ):
            widget.connect("value-changed", self._on_deep_focus_settings_changed)

        grid.attach(
            Gtk.Label(label=f"专注分钟 (默认 {self.default_config.deep_focus_minutes})"),
            0,
            0,
            1,
            1,
        )
        grid.attach(self.deep_focus_minutes_spin, 1, 0, 1, 1)
        grid.attach(
            Gtk.Label(label=f"长休息分钟 (默认 {self.default_config.deep_break_minutes})"),
            0,
            1,
            1,
            1,
        )
        grid.attach(self.deep_break_minutes_spin, 1, 1, 1, 1)
        grid.attach(
            Gtk.Label(
                label=f"随机提醒最小 (默认 {self.default_config.random_prompt_min_minutes})"
            ),
            0,
            2,
            1,
            1,
        )
        grid.attach(self.random_prompt_min_spin, 1, 2, 1, 1)
        grid.attach(
            Gtk.Label(
                label=f"随机提醒最大 (默认 {self.default_config.random_prompt_max_minutes})"
            ),
            0,
            3,
            1,
            1,
        )
        grid.attach(self.random_prompt_max_spin, 1, 3, 1, 1)
        grid.attach(
            Gtk.Label(label=f"微休息固定 {self.default_config.micro_rest_seconds} 秒"),
            0,
            4,
            2,
            1,
        )
        self.overlay_enabled_check = Gtk.CheckButton(
            label=f"启用全屏遮罩 (默认 {'开' if self.default_config.overlay_enabled else '关'})"
        )
        self.overlay_enabled_check.connect("toggled", self._on_overlay_enabled_toggled)
        grid.attach(self.overlay_enabled_check, 0, 5, 2, 1)
        self.close_to_tray_check = Gtk.CheckButton(
            label=(
                "点击关闭按钮时收起到托盘 "
                f"(默认 {'开' if self.default_config.close_to_tray else '关'})"
            )
        )
        self.close_to_tray_check.connect("toggled", self._on_close_to_tray_toggled)
        grid.attach(self.close_to_tray_check, 0, 6, 2, 1)
        self.reset_settings_btn = Gtk.Button(label="恢复默认参数")
        self.reset_settings_btn.connect("clicked", self._on_reset_settings)
        grid.attach(self.reset_settings_btn, 0, 7, 2, 1)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.start_btn = Gtk.Button(label="开始")
        self.pause_btn = Gtk.Button(label="暂停")
        self.reset_btn = Gtk.Button(label="重置")

        self.start_btn.connect("clicked", self._on_start)
        self.pause_btn.connect("clicked", self._on_pause)
        self.reset_btn.connect("clicked", self._on_reset)

        controls.append(self.start_btn)
        controls.append(self.pause_btn)
        controls.append(self.reset_btn)
        controls.append(self.deep_focus_settings_btn)

        root.append(top)
        root.append(self.timer_face)
        root.append(self.phase_label)
        root.append(self.info_label)
        root.append(controls)
        self.set_child(root)

    def _mode_to_index(self, mode: TimerMode) -> int:
        """Convert TimerMode to DropDown index."""
        mode_map = {
            TimerMode.COUNTUP: 0,
            TimerMode.POMODORO: 1,
            TimerMode.DEEP_FOCUS: 2,
        }
        return mode_map.get(mode, 0)

    def _index_to_mode(self, index: int) -> TimerMode:
        """Convert DropDown index to TimerMode."""
        index_map = {
            0: TimerMode.COUNTUP,
            1: TimerMode.POMODORO,
            2: TimerMode.DEEP_FOCUS,
        }
        return index_map.get(index, TimerMode.COUNTUP)

    def _make_spin(self, value: int, lower: int, upper: int, step: int) -> Gtk.SpinButton:
        clamped = min(max(value, lower), upper)
        spin = Gtk.SpinButton.new_with_range(lower, upper, step)
        spin.set_digits(0)
        spin.set_numeric(True)
        spin.set_width_chars(4)
        spin.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)
        spin.set_value(clamped)
        spin.set_text(str(clamped))
        return spin

    def _sync_deep_focus_controls(self) -> None:
        self._set_spin_value(self.deep_focus_minutes_spin, self.config.deep_focus_minutes)
        self._set_spin_value(self.deep_break_minutes_spin, self.config.deep_break_minutes)
        self._set_spin_value(self.random_prompt_min_spin, self.config.random_prompt_min_minutes)
        self._set_spin_value(self.random_prompt_max_spin, self.config.random_prompt_max_minutes)
        self.overlay_enabled_check.set_active(self.config.overlay_enabled)
        self.close_to_tray_check.set_active(self.config.close_to_tray)

    def _apply_window_preferences(self) -> None:
        if self.config.window_always_on_top and hasattr(self, "set_keep_above"):
            self.set_keep_above(True)

    def _on_tick(self) -> bool:
        events = self.engine.tick(time.monotonic())
        if "milestone_hit" in events:
            milestone = events["milestone_hit"]
            minute = int(milestone) if isinstance(milestone, (int, float, str)) else 0
            self.alerts.notify("学习里程碑", f"已累计学习 {minute} 分钟")
            self.alerts.beep()

        if events.get("phase_changed"):
            state = self.engine.get_display_state()
            if state.phase == PomodoroPhase.FOCUS:
                self.alerts.notify("番茄钟", f"第 {state.cycle_index} 轮专注开始")
                self.alerts.play_start()
            else:
                self.alerts.notify("番茄钟", "进入休息阶段")
                self.alerts.beep()

        if events.get("random_prompt_hit"):
            self.alerts.notify(
                "深度专注",
                f"闭上眼睛休息 {self.config.micro_rest_seconds} 秒",
            )
            self.alerts.beep()

        if events.get("micro_rest_finished"):
            self.alerts.notify("深度专注", "微休息结束，恢复专注")
            self.alerts.play_start()

        if events.get("long_break_started"):
            self.alerts.notify(
                "深度专注",
                f"已专注 {self.config.deep_focus_minutes} 分钟，进入 "
                f"{self.config.deep_break_minutes} 分钟长休息",
            )
            self.alerts.beep()

        if events.get("long_break_finished"):
            self.alerts.notify("深度专注", "长休息结束，开始下一轮专注")
            self.alerts.play_start()

        self._refresh_ui()
        return True

    def _on_mode_changed(self, _combo: Gtk.DropDown, _param: object) -> None:
        selected = self.mode_combo.get_selected()
        active_mode = self._index_to_mode(selected)
        self.config.mode_default = active_mode.value
        save_config(self.config)
        self.engine.switch_mode(active_mode)
        self._refresh_ui()

    def _on_deep_focus_settings_changed(self, _widget: Gtk.SpinButton) -> None:
        minimum = int(self.random_prompt_min_spin.get_value())
        maximum = int(self.random_prompt_max_spin.get_value())
        if minimum > maximum:
            maximum = minimum
            self.random_prompt_max_spin.set_value(maximum)

        self._apply_deep_focus_settings(
            deep_focus_minutes=int(self.deep_focus_minutes_spin.get_value()),
            deep_break_minutes=int(self.deep_break_minutes_spin.get_value()),
            random_prompt_min_minutes=minimum,
            random_prompt_max_minutes=maximum,
        )

    def _on_reset_settings(self, _btn: Gtk.Button) -> None:
        self._apply_deep_focus_settings(
            deep_focus_minutes=self.default_config.deep_focus_minutes,
            deep_break_minutes=self.default_config.deep_break_minutes,
            random_prompt_min_minutes=self.default_config.random_prompt_min_minutes,
            random_prompt_max_minutes=self.default_config.random_prompt_max_minutes,
        )
        self.config.overlay_enabled = self.default_config.overlay_enabled
        self.config.close_to_tray = self.default_config.close_to_tray
        save_config(self.config)
        self._sync_deep_focus_controls()

    def _on_open_settings_dialog(self, _btn: Gtk.Button) -> None:
        self._sync_deep_focus_controls()
        self.settings_dialog.present()

    def _on_settings_dialog_close_request(self, _window: Gtk.Window) -> bool:
        if self._allow_shutdown:
            return False
        self.settings_dialog.hide()
        return True

    def _on_overlay_enabled_toggled(self, _btn: Gtk.CheckButton) -> None:
        self.config.overlay_enabled = self.overlay_enabled_check.get_active()
        save_config(self.config)
        if not self.config.overlay_enabled:
            self._hide_overlay()

    def _on_close_to_tray_toggled(self, _btn: Gtk.CheckButton) -> None:
        self.config.close_to_tray = self.close_to_tray_check.get_active()
        save_config(self.config)

    def _on_start(self, _btn: Gtk.Button) -> None:
        self.engine.start(time.monotonic())
        self.alerts.play_start()
        self._refresh_ui()

    def _on_pause(self, _btn: Gtk.Button) -> None:
        self.engine.pause(time.monotonic())
        self._refresh_ui()

    def _on_reset(self, _btn: Gtk.Button) -> None:
        self.engine.reset()
        self._refresh_ui()

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        if self._allow_shutdown:
            self._close_auxiliary_windows()
            return False
        if self._should_close_to_tray() and self._hide_to_tray(notify=True):
            return True
        if self._should_confirm_close_running_timer():
            self.running_timer_close_dialog.present()
            return True
        self._close_auxiliary_windows()
        app = self.get_application()
        if app is not None:
            app.quit()
        return False

    def allow_shutdown(self) -> None:
        self._allow_shutdown = True

    def restore_from_tray(self) -> None:
        self._hidden_to_tray = False
        self.present()
        self._refresh_ui()

    def hide_to_tray(self) -> bool:
        return self._hide_to_tray(notify=False)

    def _hide_to_tray(self, *, notify: bool) -> bool:
        app = self.get_application()
        if app is None or not getattr(app, "has_system_tray", lambda: False)():
            return False
        self._hidden_to_tray = True
        self._hide_overlay()
        self._hide_micro_rest_prompt()
        if self.running_timer_close_dialog.is_visible():
            self.running_timer_close_dialog.hide()
        if self.settings_dialog.is_visible():
            self.settings_dialog.hide()
        self.hide()
        if notify:
            self.alerts.notify("学习时钟", "程序已收起到系统托盘，计时会继续进行")
        return True

    def _close_auxiliary_windows(self) -> None:
        if self.overlay_window.is_visible():
            self.overlay_window.hide()
        if self.prompt_window.is_visible():
            self.prompt_window.hide()
        if self.running_timer_close_dialog.is_visible():
            self.running_timer_close_dialog.hide()
        if self.settings_dialog.is_visible():
            self.settings_dialog.hide()

    def _refresh_ui(self) -> None:
        state = self.engine.get_display_state()
        # Color-coded status: green for running, orange for paused
        if state.running:
            self.status_label.set_markup(
                '<span foreground="#4CAF50" weight="bold">运行中</span>'
            )
        else:
            self.status_label.set_markup(
                '<span foreground="#FF9800" weight="bold">已暂停</span>'
            )
        self.start_btn.set_sensitive(not state.running)
        self.pause_btn.set_sensitive(state.running)
        self._sync_tray_status(state)

        if state.mode == TimerMode.COUNTUP:
            self._update_timer_face(
                time_text=TimerEngine.format_hhmmss(state.elapsed_seconds),
                caption="正计时",
                progress=self._countup_progress(state.elapsed_seconds),
                accent=(0.22, 0.73, 0.54),
            )
            self.phase_label.set_markup("模式: 正计时")
            self.info_label.set_label("按开始即可累计学习时间")
            self._hide_micro_rest_prompt()
            self._hide_overlay()
            return

        if state.mode == TimerMode.POMODORO:
            phase = "专注" if state.phase == PomodoroPhase.FOCUS else "休息"
            phase_total = (
                self.config.pomodoro_focus_minutes * 60
                if state.phase == PomodoroPhase.FOCUS
                else self.config.pomodoro_break_minutes * 60
            )
            self._update_timer_face(
                time_text=TimerEngine.format_hhmmss(state.elapsed_seconds),
                caption=f"番茄钟 {phase}",
                progress=self._bounded_progress(state.elapsed_seconds, phase_total),
                accent=(0.96, 0.57, 0.22) if state.phase == PomodoroPhase.FOCUS else (0.26, 0.63, 0.88),
            )
            self.phase_label.set_markup(
                f'模式: 番茄钟 | 阶段: {phase} | 轮次: <span foreground="#E91E63" weight="bold">{state.cycle_index}</span>'
            )
            self.info_label.set_label(
                f"本阶段剩余: {TimerEngine.format_hhmmss(state.phase_remaining_seconds or 0)}"
            )
            self._hide_micro_rest_prompt()
            self._hide_overlay()
            return

        self._refresh_deep_focus_ui(state)

    def _refresh_deep_focus_ui(self, deep_state: DisplayState) -> None:
        phase = deep_state.phase
        if phase == DeepFocusPhase.FOCUS:
            self._update_timer_face(
                time_text=TimerEngine.format_hhmmss(deep_state.elapsed_seconds),
                caption="深度专注",
                progress=self._bounded_progress(
                    deep_state.elapsed_seconds,
                    self.config.deep_focus_minutes * 60,
                ),
                accent=(0.84, 0.32, 0.29),
            )
            self.phase_label.set_markup(
                f'模式: 深度专注 | 第 <span foreground="#E91E63" weight="bold">{deep_state.cycle_index}</span> 轮 | 本轮剩余: '
                f"{TimerEngine.format_hhmmss(deep_state.phase_remaining_seconds or 0)}"
            )
            self.info_label.set_label(
                "随机提示音已启用，请在响起时立刻闭眼休息"
            )
            self._hide_micro_rest_prompt()
            self._hide_overlay()
            return

        if phase == DeepFocusPhase.MICRO_REST:
            remain = deep_state.phase_remaining_seconds or 0
            self._update_timer_face(
                time_text=TimerEngine.format_hhmmss(remain),
                caption="闭眼休息",
                progress=self._remaining_progress(remain, self.config.micro_rest_seconds),
                accent=(0.46, 0.50, 0.95),
            )
            self.phase_label.set_markup(
                f'模式: 深度专注 | <span foreground="#E91E63" weight="bold">{self.config.micro_rest_seconds}</span> 秒微休息'
            )
            self.info_label.set_label("闭上眼睛休息，倒计时结束后自动恢复专注")
            self._show_overlay(remain)
            return

        remain = deep_state.phase_remaining_seconds or 0
        self._update_timer_face(
            time_text=TimerEngine.format_hhmmss(remain),
            caption="长休息",
            progress=self._remaining_progress(remain, self.config.deep_break_minutes * 60),
            accent=(0.38, 0.70, 0.82),
        )
        self.phase_label.set_markup(
            f'模式: 深度专注 | 第 <span foreground="#E91E63" weight="bold">{deep_state.cycle_index}</span> 轮长休息'
        )
        self.info_label.set_label(
            f"{self.config.deep_break_minutes} 分钟长休息中，随机提示音已暂停"
        )
        self._hide_micro_rest_prompt()
        self._hide_overlay()

    def _show_overlay(self, seconds: int) -> None:
        if self._hidden_to_tray:
            self._hide_overlay()
            return
        if not self.config.overlay_enabled:
            self._show_micro_rest_prompt(seconds)
            return
        self._hide_micro_rest_prompt()
        if not self.overlay_window.is_visible():
            self.overlay_window.show_countdown(seconds, self)
            return
        self.overlay_window.update_countdown(seconds)

    def _hide_overlay(self) -> None:
        if self.overlay_window.is_visible():
            self.overlay_window.hide()

    def _show_micro_rest_prompt(self, seconds: int) -> None:
        if self._hidden_to_tray:
            self._hide_micro_rest_prompt()
            return
        if not self.prompt_window.is_visible():
            self.prompt_window.show_countdown(seconds, self)
            return
        self.prompt_window.update_countdown(seconds)

    def _hide_micro_rest_prompt(self) -> None:
        if self.prompt_window.is_visible():
            self.prompt_window.hide()

    def _apply_deep_focus_settings(
        self,
        *,
        deep_focus_minutes: int,
        deep_break_minutes: int,
        random_prompt_min_minutes: int,
        random_prompt_max_minutes: int,
    ) -> None:
        self.config.deep_focus_minutes = deep_focus_minutes
        self.config.deep_break_minutes = deep_break_minutes
        self.config.random_prompt_min_minutes = random_prompt_min_minutes
        self.config.random_prompt_max_minutes = max(
            random_prompt_min_minutes,
            random_prompt_max_minutes,
        )
        save_config(self.config)
        self.engine.update_deep_focus_settings(
            deep_focus_minutes=self.config.deep_focus_minutes,
            deep_break_minutes=self.config.deep_break_minutes,
            random_prompt_min_minutes=self.config.random_prompt_min_minutes,
            random_prompt_max_minutes=self.config.random_prompt_max_minutes,
            micro_rest_seconds=self.config.micro_rest_seconds,
        )
        self._refresh_ui()

    @staticmethod
    def _set_spin_value(spin: Gtk.SpinButton, value: int) -> None:
        spin.set_value(value)
        spin.set_text(str(value))

    def _update_timer_face(
        self,
        *,
        time_text: str,
        caption: str,
        progress: float,
        accent: tuple[float, float, float],
    ) -> None:
        self.timer_face.update_face(
            time_text=time_text,
            caption=caption,
            progress=progress,
            accent=accent,
        )

    @staticmethod
    def _bounded_progress(value: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return max(0.0, min(value / total, 1.0))

    @staticmethod
    def _remaining_progress(remaining: int, total: int) -> float:
        if total <= 0:
            return 0.0
        elapsed = max(0, total - remaining)
        return max(0.0, min(elapsed / total, 1.0))

    @staticmethod
    def _countup_progress(elapsed: int) -> float:
        cycle = 3600
        return (elapsed % cycle) / cycle

    def _supports_tray(self) -> bool:
        app = self.get_application()
        if app is None:
            return False
        return bool(getattr(app, "has_system_tray", lambda: False)())

    def _sync_tray_status(self, state: DisplayState) -> None:
        app = self.get_application()
        update_tray = None if app is None else getattr(app, "update_tray", None)
        if not callable(update_tray):
            return
        status_text = self._tray_status_text(state)
        icon_name = "media-playback-start-symbolic" if state.running else "media-playback-pause-symbolic"
        update_tray(icon_name=icon_name, status=status_text)

    def _tray_status_text(self, state: DisplayState) -> str:
        running_text = "运行中" if state.running else "已暂停"
        if state.mode == TimerMode.COUNTUP:
            return f"正计时 | {TimerEngine.format_hhmmss(state.elapsed_seconds)} | {running_text}"
        if state.mode == TimerMode.POMODORO:
            phase = "专注" if state.phase == PomodoroPhase.FOCUS else "休息"
            remain = TimerEngine.format_hhmmss(state.phase_remaining_seconds or 0)
            return f"番茄钟-{phase} | 剩余 {remain} | {running_text}"
        if state.phase == DeepFocusPhase.MICRO_REST:
            remain = TimerEngine.format_hhmmss(state.phase_remaining_seconds or 0)
            return f"深度专注-微休息 | 剩余 {remain} | {running_text}"
        if state.phase == DeepFocusPhase.LONG_BREAK:
            remain = TimerEngine.format_hhmmss(state.phase_remaining_seconds or 0)
            return f"深度专注-长休息 | 剩余 {remain} | {running_text}"
        remain = TimerEngine.format_hhmmss(state.phase_remaining_seconds or 0)
        return f"深度专注 | 本轮剩余 {remain} | {running_text}"

    def _should_close_to_tray(self) -> bool:
        if not self.config.close_to_tray:
            return False
        if not self._supports_tray():
            return False
        return self.engine.get_display_state().running

    def _should_confirm_close_running_timer(self) -> bool:
        if self.config.close_to_tray:
            return False
        return self.engine.get_display_state().running

    def _confirm_close_running_timer(self) -> None:
        app = self.get_application()
        request_quit = None if app is None else getattr(app, "request_quit", None)
        if callable(request_quit):
            request_quit()
            return
        self.allow_shutdown()
        self.close()


class LeanTimerApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.jing.lean_timer")
        self._window: LeanTimerWindow | None = None
        self._tray: TrayIcon | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self._add_action("show-window", self._on_show_window_action)
        self._add_action("hide-window", self._on_hide_window_action)
        self._add_action("quit", self._on_quit_action)
        self._tray = TrayIcon.create(
            app_id="com.jing.lean_timer",
            title="学习时钟",
            icon_name="alarm-symbolic",
            on_activate=self.toggle_main_window,
            menu_items=self._tray_menu_items(),
        )

    def do_shutdown(self) -> None:
        if self._window is not None:
            self._window.allow_shutdown()
            self._window._close_auxiliary_windows()
        if self._tray is not None:
            self._tray.shutdown()
            self._tray = None
        Gtk.Application.do_shutdown(self)

    def do_activate(self) -> None:
        self.show_main_window()

    def has_system_tray(self) -> bool:
        return self._tray is not None

    def show_main_window(self) -> None:
        self._ensure_window().restore_from_tray()

    def hide_main_window(self) -> None:
        if self._window is None:
            return
        self._window.hide_to_tray()

    def toggle_main_window(self) -> None:
        if self._window is None or not self._window.is_visible():
            self.show_main_window()
            return
        self.hide_main_window()

    def request_quit(self) -> None:
        if self._window is not None:
            self._window.allow_shutdown()
            self._window._close_auxiliary_windows()
        self.quit()

    def _ensure_window(self) -> LeanTimerWindow:
        if self._window is None:
            self._window = LeanTimerWindow(self)
            self._window.connect("destroy", self._on_window_destroy)
        return self._window

    def _on_window_destroy(self, _window: Gtk.Window) -> None:
        self._window = None

    def update_tray(self, *, icon_name: str, status: str) -> None:
        if self._tray is None:
            return
        self._tray.set_icon(icon_name)
        self._tray.set_status("Active")
        self._tray.set_tooltip("学习时钟", status)

    def _tray_menu_items(self) -> list[TrayMenuItem]:
        return [
            TrayMenuItem(item_id=1, label="显示主窗口", callback=self.show_main_window),
            TrayMenuItem(item_id=2, label="收起主窗口", callback=self.hide_main_window),
            TrayMenuItem(item_id=3, label="", item_type="separator"),
            TrayMenuItem(item_id=4, label="退出", callback=self.request_quit),
        ]

    def _add_action(self, name: str, callback) -> None:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def _on_show_window_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        self.show_main_window()

    def _on_hide_window_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        self.hide_main_window()

    def _on_quit_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        self.request_quit()


def main() -> None:
    ok = Gtk.init_check()
    if not ok:
        raise RuntimeError("GTK display initialization failed")

    app = LeanTimerApp()
    app.run(None)


if __name__ == "__main__":
    main()
