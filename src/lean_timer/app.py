from __future__ import annotations

import math
import time

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Notify", "0.7")

from gi.repository import Gdk, GLib, Gtk

from lean_timer.alerts import AlertService
from lean_timer.config import AppConfig, load_config, save_config
from lean_timer.timer_engine import (
    DeepFocusPhase,
    DisplayState,
    PomodoroPhase,
    TimerEngine,
    TimerMode,
)


class MicroRestOverlay(Gtk.Window):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, modal=True)
        self.set_title("闭眼休息")
        if hasattr(self, "set_decorated"):
            self.set_decorated(False)
        if hasattr(self, "set_opacity"):
            self.set_opacity(0.75)

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
        self.set_transient_for(parent)
        self.set_modal(True)
        self.present()
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
        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.append(TimerMode.COUNTUP.value, "正计时")
        self.mode_combo.append(TimerMode.POMODORO.value, "番茄钟")
        self.mode_combo.append(TimerMode.DEEP_FOCUS.value, "深度专注")
        self.mode_combo.set_active_id(self.engine.mode.value)
        self.mode_combo.connect("changed", self._on_mode_changed)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.END)
        self.status_label.set_hexpand(True)

        top.append(self.mode_combo)
        top.append(self.status_label)

        self.timer_face = CircularTimerFace()
        self.phase_label = Gtk.Label(label="")
        self.info_label = Gtk.Label(label="")
        self.info_label.set_wrap(True)

        self.deep_focus_box = Gtk.Frame(label="深度专注参数")
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)

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
        self.reset_settings_btn = Gtk.Button(label="恢复默认参数")
        self.reset_settings_btn.connect("clicked", self._on_reset_settings)
        grid.attach(self.reset_settings_btn, 0, 5, 2, 1)
        self.deep_focus_box.set_child(grid)

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

        root.append(top)
        root.append(self.timer_face)
        root.append(self.phase_label)
        root.append(self.info_label)
        root.append(self.deep_focus_box)
        root.append(controls)
        self.set_child(root)

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

    def _apply_window_preferences(self) -> None:
        if self.config.window_always_on_top and hasattr(self, "set_keep_above"):
            self.set_keep_above(True)

    def _on_tick(self) -> bool:
        events = self.engine.tick(time.monotonic())
        if "milestone_hit" in events:
            minute = int(events["milestone_hit"])
            self.alerts.notify("学习里程碑", f"已累计学习 {minute} 分钟")
            self.alerts.beep()

        if events.get("phase_changed"):
            state = self.engine.get_display_state()
            if state.phase == PomodoroPhase.FOCUS:
                self.alerts.notify("番茄钟", f"第 {state.cycle_index} 轮专注开始")
            else:
                self.alerts.notify("番茄钟", "进入休息阶段")
            self.alerts.beep()

        if events.get("random_prompt_hit"):
            self.alerts.notify(
                "深度专注",
                f"闭上眼睛休息 {self.config.micro_rest_seconds} 秒",
            )
            self.alerts.beep()

        if events.get("long_break_started"):
            self.alerts.notify(
                "深度专注",
                f"已专注 {self.config.deep_focus_minutes} 分钟，进入 "
                f"{self.config.deep_break_minutes} 分钟长休息",
            )
            self.alerts.beep()

        if events.get("long_break_finished"):
            self.alerts.notify("深度专注", "长休息结束，开始下一轮专注")
            self.alerts.beep()

        self._refresh_ui()
        return True

    def _on_mode_changed(self, _combo: Gtk.ComboBoxText) -> None:
        active = self.mode_combo.get_active_id() or TimerMode.COUNTUP.value
        self.config.mode_default = active
        save_config(self.config)
        self.engine.switch_mode(TimerMode(active))
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
        self._sync_deep_focus_controls()

    def _on_start(self, _btn: Gtk.Button) -> None:
        self.engine.start(time.monotonic())
        self._refresh_ui()

    def _on_pause(self, _btn: Gtk.Button) -> None:
        self.engine.pause(time.monotonic())
        self._refresh_ui()

    def _on_reset(self, _btn: Gtk.Button) -> None:
        self.engine.reset()
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        state = self.engine.get_display_state()
        self.status_label.set_label("运行中" if state.running else "已暂停")
        self.deep_focus_box.set_visible(state.mode == TimerMode.DEEP_FOCUS)
        self.start_btn.set_sensitive(not state.running)
        self.pause_btn.set_sensitive(state.running)

        if state.mode == TimerMode.COUNTUP:
            self._update_timer_face(
                time_text=TimerEngine.format_hhmmss(state.elapsed_seconds),
                caption="正计时",
                progress=self._countup_progress(state.elapsed_seconds),
                accent=(0.22, 0.73, 0.54),
            )
            self.phase_label.set_label("模式: 正计时")
            self.info_label.set_label("按开始即可累计学习时间")
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
            self.phase_label.set_label(f"模式: 番茄钟 | 阶段: {phase} | 轮次: {state.cycle_index}")
            self.info_label.set_label(
                f"本阶段剩余: {TimerEngine.format_hhmmss(state.phase_remaining_seconds or 0)}"
            )
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
            self.phase_label.set_label(
                f"模式: 深度专注 | 第 {deep_state.cycle_index} 轮 | 本轮剩余: "
                f"{TimerEngine.format_hhmmss(deep_state.phase_remaining_seconds or 0)}"
            )
            self.info_label.set_label(
                "随机提示音已启用，请在响起时立刻闭眼休息"
            )
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
            self.phase_label.set_label(
                f"模式: 深度专注 | {self.config.micro_rest_seconds} 秒微休息"
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
        self.phase_label.set_label(f"模式: 深度专注 | 第 {deep_state.cycle_index} 轮长休息")
        self.info_label.set_label(
            f"{self.config.deep_break_minutes} 分钟长休息中，随机提示音已暂停"
        )
        self._hide_overlay()

    def _show_overlay(self, seconds: int) -> None:
        if not self.overlay_window.is_visible():
            self.overlay_window.show_countdown(seconds, self)
            return
        self.overlay_window.update_countdown(seconds)

    def _hide_overlay(self) -> None:
        if self.overlay_window.is_visible():
            self.overlay_window.hide()

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


class LeanTimerApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.jing.lean_timer")

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = LeanTimerWindow(self)
        win.present()


def main() -> None:
    ok = Gtk.init_check()
    if not ok:
        raise RuntimeError("GTK display initialization failed")
    if Gdk.Display.get_default() is None:
        raise RuntimeError("No active GDK display")

    app = LeanTimerApp()
    app.run(None)


if __name__ == "__main__":
    main()
