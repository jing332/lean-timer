from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from random import randint
from typing import Callable, Iterable


class TimerMode(str, Enum):
    COUNTUP = "countup"
    POMODORO = "pomodoro"
    DEEP_FOCUS = "deep_focus"


class PomodoroPhase(str, Enum):
    FOCUS = "focus"
    BREAK = "break"


class DeepFocusPhase(str, Enum):
    FOCUS = "focus"
    MICRO_REST = "micro_rest"
    LONG_BREAK = "long_break"


@dataclass(frozen=True)
class DisplayState:
    mode: TimerMode
    running: bool
    elapsed_seconds: int
    phase: PomodoroPhase | DeepFocusPhase | None
    cycle_index: int
    milestones_triggered: tuple[int, ...]
    phase_name: str | None
    phase_remaining_seconds: int | None
    next_prompt_in_seconds: int | None
    is_overlay_active: bool


class TimerEngine:
    """Monotonic-clock timer engine for count-up, pomodoro, and deep focus modes."""

    def __init__(
        self,
        *,
        mode: TimerMode = TimerMode.COUNTUP,
        pomodoro_focus_minutes: int = 25,
        pomodoro_break_minutes: int = 5,
        milestones_minutes: Iterable[int] = (30, 60, 90),
        deep_focus_minutes: int = 90,
        deep_break_minutes: int = 20,
        random_prompt_min_minutes: int = 3,
        random_prompt_max_minutes: int = 5,
        micro_rest_seconds: int = 10,
        randrange_inclusive: Callable[[int, int], int] | None = None,
    ) -> None:
        self.mode = mode
        self.pomodoro_focus_seconds = max(1, pomodoro_focus_minutes) * 60
        self.pomodoro_break_seconds = max(1, pomodoro_break_minutes) * 60
        self.milestones_seconds = sorted({max(1, m) * 60 for m in milestones_minutes})
        self.deep_focus_seconds = max(1, deep_focus_minutes) * 60
        self.deep_break_seconds = max(1, deep_break_minutes) * 60
        self.random_prompt_min_seconds = max(1, random_prompt_min_minutes) * 60
        self.random_prompt_max_seconds = max(
            self.random_prompt_min_seconds,
            max(1, random_prompt_max_minutes) * 60,
        )
        self.micro_rest_seconds = max(1, micro_rest_seconds)
        self._randrange_inclusive = randrange_inclusive or randint

        self._running = False
        self._last_monotonic: float | None = None
        self._countup_elapsed = 0.0
        self._pomodoro_phase_elapsed = 0.0
        self._pomodoro_phase = PomodoroPhase.FOCUS
        self._cycle_index = 1
        self._milestones_triggered: set[int] = set()

        self._deep_phase = DeepFocusPhase.FOCUS
        self._deep_focus_elapsed = 0.0
        self._deep_phase_elapsed = 0.0
        self._next_prompt_at_focus_elapsed: float | None = None
        self._initialize_mode_state(mode)

    def start(self, now_monotonic: float) -> None:
        if self._running:
            return
        self._running = True
        self._last_monotonic = now_monotonic
        if self.mode == TimerMode.DEEP_FOCUS and self._deep_phase == DeepFocusPhase.FOCUS:
            self._ensure_next_prompt()

    def pause(self, now_monotonic: float) -> None:
        if not self._running:
            return
        self.tick(now_monotonic)
        self._running = False
        self._last_monotonic = None

    def reset(self) -> None:
        self._running = False
        self._last_monotonic = None
        self._countup_elapsed = 0.0
        self._pomodoro_phase_elapsed = 0.0
        self._pomodoro_phase = PomodoroPhase.FOCUS
        self._cycle_index = 1
        self._milestones_triggered.clear()
        self._deep_phase = DeepFocusPhase.FOCUS
        self._deep_focus_elapsed = 0.0
        self._deep_phase_elapsed = 0.0
        self._next_prompt_at_focus_elapsed = None
        self._initialize_mode_state(self.mode)

    def switch_mode(self, mode: TimerMode) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self._running = False
        self._last_monotonic = None
        self._initialize_mode_state(mode)

    def update_deep_focus_settings(
        self,
        *,
        deep_focus_minutes: int,
        deep_break_minutes: int,
        random_prompt_min_minutes: int,
        random_prompt_max_minutes: int,
        micro_rest_seconds: int,
    ) -> None:
        self.deep_focus_seconds = max(1, deep_focus_minutes) * 60
        self.deep_break_seconds = max(1, deep_break_minutes) * 60
        self.random_prompt_min_seconds = max(1, random_prompt_min_minutes) * 60
        self.random_prompt_max_seconds = max(
            self.random_prompt_min_seconds,
            max(1, random_prompt_max_minutes) * 60,
        )
        self.micro_rest_seconds = max(1, micro_rest_seconds)
        if self.mode == TimerMode.DEEP_FOCUS:
            self.reset()

    def tick(self, now_monotonic: float) -> dict[str, object]:
        events: dict[str, object] = {}
        if not self._running or self._last_monotonic is None:
            return events

        delta = max(0.0, now_monotonic - self._last_monotonic)
        self._last_monotonic = now_monotonic

        if self.mode == TimerMode.COUNTUP:
            self._tick_countup(delta, events)
        elif self.mode == TimerMode.POMODORO:
            self._tick_pomodoro(delta, events)
        else:
            self._tick_deep_focus(delta, events)

        return events

    def get_display_state(self) -> DisplayState:
        phase: PomodoroPhase | DeepFocusPhase | None = None
        elapsed = int(self._countup_elapsed)
        phase_name: str | None = None
        phase_remaining_seconds: int | None = None
        next_prompt_in_seconds: int | None = None
        is_overlay_active = False

        if self.mode == TimerMode.POMODORO:
            phase = self._pomodoro_phase
            elapsed = int(self._pomodoro_phase_elapsed)
            phase_name = "focus" if phase == PomodoroPhase.FOCUS else "break"
            limit = (
                self.pomodoro_focus_seconds
                if phase == PomodoroPhase.FOCUS
                else self.pomodoro_break_seconds
            )
            phase_remaining_seconds = max(0, int(limit - self._pomodoro_phase_elapsed))
        elif self.mode == TimerMode.DEEP_FOCUS:
            phase = self._deep_phase
            if phase == DeepFocusPhase.FOCUS:
                elapsed = int(self._deep_focus_elapsed)
                phase_name = "focus"
                phase_remaining_seconds = max(
                    0,
                    int(self.deep_focus_seconds - self._deep_focus_elapsed),
                )
                if self._next_prompt_at_focus_elapsed is not None:
                    next_prompt_in_seconds = max(
                        0,
                        int(self._next_prompt_at_focus_elapsed - self._deep_focus_elapsed),
                    )
            elif phase == DeepFocusPhase.MICRO_REST:
                elapsed = max(0, int(self.micro_rest_seconds - self._deep_phase_elapsed))
                phase_name = "micro_rest"
                phase_remaining_seconds = elapsed
                is_overlay_active = True
            else:
                elapsed = max(0, int(self.deep_break_seconds - self._deep_phase_elapsed))
                phase_name = "long_break"
                phase_remaining_seconds = elapsed

        return DisplayState(
            mode=self.mode,
            running=self._running,
            elapsed_seconds=elapsed,
            phase=phase,
            cycle_index=self._cycle_index,
            milestones_triggered=tuple(sorted(self._milestones_triggered)),
            phase_name=phase_name,
            phase_remaining_seconds=phase_remaining_seconds,
            next_prompt_in_seconds=next_prompt_in_seconds,
            is_overlay_active=is_overlay_active,
        )

    def _initialize_mode_state(self, mode: TimerMode) -> None:
        self._countup_elapsed = 0.0
        self._pomodoro_phase_elapsed = 0.0
        self._pomodoro_phase = PomodoroPhase.FOCUS
        self._deep_phase = DeepFocusPhase.FOCUS
        self._deep_focus_elapsed = 0.0
        self._deep_phase_elapsed = 0.0
        self._next_prompt_at_focus_elapsed = None
        self._milestones_triggered.clear()
        self._cycle_index = 1
        if mode == TimerMode.DEEP_FOCUS:
            self._ensure_next_prompt()

    def _tick_countup(self, delta: float, events: dict[str, object]) -> None:
        self._countup_elapsed += delta
        elapsed_int = int(self._countup_elapsed)
        for sec in self.milestones_seconds:
            if sec <= elapsed_int and sec not in self._milestones_triggered:
                self._milestones_triggered.add(sec)
                events["milestone_hit"] = sec // 60
                break

    def _tick_pomodoro(self, delta: float, events: dict[str, object]) -> None:
        self._pomodoro_phase_elapsed += delta
        phase_limit = (
            self.pomodoro_focus_seconds
            if self._pomodoro_phase == PomodoroPhase.FOCUS
            else self.pomodoro_break_seconds
        )
        while self._pomodoro_phase_elapsed >= phase_limit:
            self._pomodoro_phase_elapsed -= phase_limit
            if self._pomodoro_phase == PomodoroPhase.FOCUS:
                self._pomodoro_phase = PomodoroPhase.BREAK
            else:
                self._pomodoro_phase = PomodoroPhase.FOCUS
                self._cycle_index += 1
            events["phase_changed"] = True
            phase_limit = (
                self.pomodoro_focus_seconds
                if self._pomodoro_phase == PomodoroPhase.FOCUS
                else self.pomodoro_break_seconds
            )

    def _tick_deep_focus(self, delta: float, events: dict[str, object]) -> None:
        remaining = delta
        while remaining > 0:
            if self._deep_phase == DeepFocusPhase.FOCUS:
                remaining = self._tick_deep_focus_focus(remaining, events)
            elif self._deep_phase == DeepFocusPhase.MICRO_REST:
                remaining = self._tick_deep_focus_micro_rest(remaining, events)
            else:
                remaining = self._tick_deep_focus_long_break(remaining, events)

    def _tick_deep_focus_focus(self, delta: float, events: dict[str, object]) -> float:
        self._ensure_next_prompt()
        to_long_break = self.deep_focus_seconds - self._deep_focus_elapsed
        to_prompt = (
            self._next_prompt_at_focus_elapsed - self._deep_focus_elapsed
            if self._next_prompt_at_focus_elapsed is not None
            else to_long_break
        )
        step = min(delta, to_long_break, max(0.0, to_prompt))
        if step > 0:
            self._deep_focus_elapsed += step
            self._deep_phase_elapsed += step
            delta -= step

        if self._deep_focus_elapsed >= self.deep_focus_seconds:
            self._start_long_break(events)
            return delta

        if (
            self._next_prompt_at_focus_elapsed is not None
            and self._deep_focus_elapsed >= self._next_prompt_at_focus_elapsed
        ):
            events["random_prompt_hit"] = True
            self._deep_phase = DeepFocusPhase.MICRO_REST
            self._deep_phase_elapsed = 0.0
            self._next_prompt_at_focus_elapsed = None
            events["micro_rest_started"] = True
        return delta

    def _tick_deep_focus_micro_rest(self, delta: float, events: dict[str, object]) -> float:
        to_end = self.micro_rest_seconds - self._deep_phase_elapsed
        step = min(delta, to_end)
        if step > 0:
            self._deep_phase_elapsed += step
            delta -= step

        if self._deep_phase_elapsed >= self.micro_rest_seconds:
            self._deep_phase = DeepFocusPhase.FOCUS
            self._deep_phase_elapsed = 0.0
            self._schedule_next_prompt()
            events["micro_rest_finished"] = True
        return delta

    def _tick_deep_focus_long_break(self, delta: float, events: dict[str, object]) -> float:
        to_end = self.deep_break_seconds - self._deep_phase_elapsed
        step = min(delta, to_end)
        if step > 0:
            self._deep_phase_elapsed += step
            delta -= step

        if self._deep_phase_elapsed >= self.deep_break_seconds:
            self._cycle_index += 1
            self._deep_phase = DeepFocusPhase.FOCUS
            self._deep_focus_elapsed = 0.0
            self._deep_phase_elapsed = 0.0
            self._schedule_next_prompt()
            events["long_break_finished"] = True
        return delta

    def _start_long_break(self, events: dict[str, object]) -> None:
        self._deep_phase = DeepFocusPhase.LONG_BREAK
        self._deep_phase_elapsed = 0.0
        self._next_prompt_at_focus_elapsed = None
        events["long_break_started"] = True

    def _ensure_next_prompt(self) -> None:
        if self._deep_phase != DeepFocusPhase.FOCUS:
            return
        if self._next_prompt_at_focus_elapsed is None:
            self._schedule_next_prompt()

    def _schedule_next_prompt(self) -> None:
        interval = self._randrange_inclusive(
            self.random_prompt_min_seconds,
            self.random_prompt_max_seconds,
        )
        self._next_prompt_at_focus_elapsed = self._deep_focus_elapsed + float(interval)

    @staticmethod
    def format_hhmmss(total_seconds: int) -> str:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
