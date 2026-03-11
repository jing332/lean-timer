from lean_timer.timer_engine import DeepFocusPhase, PomodoroPhase, TimerEngine, TimerMode


def constant_random(_minimum: int, _maximum: int) -> int:
    return _minimum


def test_countup_pause_resume_continuous() -> None:
    engine = TimerEngine(mode=TimerMode.COUNTUP, milestones_minutes=(30,))

    engine.start(100.0)
    engine.tick(105.0)
    engine.pause(105.0)
    assert engine.get_display_state().elapsed_seconds == 5

    engine.start(200.0)
    engine.tick(203.0)
    assert engine.get_display_state().elapsed_seconds == 8


def test_reset_from_any_state() -> None:
    engine = TimerEngine(mode=TimerMode.COUNTUP)
    engine.start(10.0)
    engine.tick(70.0)
    engine.reset()
    state = engine.get_display_state()
    assert state.elapsed_seconds == 0
    assert state.running is False


def test_pomodoro_switches_focus_to_break() -> None:
    engine = TimerEngine(
        mode=TimerMode.POMODORO,
        pomodoro_focus_minutes=1,
        pomodoro_break_minutes=1,
    )
    engine.start(0.0)
    events = engine.tick(60.0)
    state = engine.get_display_state()
    assert events.get("phase_changed") is True
    assert state.phase == PomodoroPhase.BREAK


def test_milestone_fires_once() -> None:
    engine = TimerEngine(mode=TimerMode.COUNTUP, milestones_minutes=(1,))
    engine.start(0.0)
    events1 = engine.tick(60.0)
    events2 = engine.tick(120.0)
    assert events1.get("milestone_hit") == 1
    assert "milestone_hit" not in events2


def test_deep_focus_random_prompt_triggers_micro_rest() -> None:
    engine = TimerEngine(
        mode=TimerMode.DEEP_FOCUS,
        deep_focus_minutes=90,
        deep_break_minutes=20,
        random_prompt_min_minutes=3,
        random_prompt_max_minutes=5,
        micro_rest_seconds=10,
        randrange_inclusive=constant_random,
    )

    engine.start(0.0)
    events = engine.tick(180.0)
    state = engine.get_display_state()

    assert events.get("random_prompt_hit") is True
    assert events.get("micro_rest_started") is True
    assert state.phase == DeepFocusPhase.MICRO_REST
    assert state.is_overlay_active is True


def test_deep_focus_micro_rest_returns_to_focus_and_reschedules() -> None:
    engine = TimerEngine(
        mode=TimerMode.DEEP_FOCUS,
        random_prompt_min_minutes=3,
        random_prompt_max_minutes=3,
        micro_rest_seconds=10,
        randrange_inclusive=constant_random,
    )

    engine.start(0.0)
    engine.tick(180.0)
    events = engine.tick(190.0)
    state = engine.get_display_state()

    assert events.get("micro_rest_finished") is True
    assert state.phase == DeepFocusPhase.FOCUS
    assert state.next_prompt_in_seconds == 180


def test_deep_focus_reaches_long_break_and_stops_after_break() -> None:
    engine = TimerEngine(
        mode=TimerMode.DEEP_FOCUS,
        deep_focus_minutes=1,
        deep_break_minutes=1,
        random_prompt_min_minutes=10,
        random_prompt_max_minutes=10,
        micro_rest_seconds=10,
        randrange_inclusive=constant_random,
    )

    engine.start(0.0)
    events1 = engine.tick(60.0)
    state1 = engine.get_display_state()
    assert events1.get("long_break_started") is True
    assert state1.phase == DeepFocusPhase.LONG_BREAK

    events2 = engine.tick(120.0)
    state2 = engine.get_display_state()
    assert events2.get("long_break_finished") is True
    assert state2.phase == DeepFocusPhase.FOCUS
    assert state2.running is False
    assert state2.cycle_index == 1
    assert state2.phase_remaining_seconds == 60


def test_deep_focus_auto_continue_starts_next_round_after_break() -> None:
    engine = TimerEngine(
        mode=TimerMode.DEEP_FOCUS,
        deep_focus_minutes=1,
        deep_break_minutes=1,
        deep_focus_auto_continue=True,
        random_prompt_min_minutes=10,
        random_prompt_max_minutes=10,
        micro_rest_seconds=10,
        randrange_inclusive=constant_random,
    )

    engine.start(0.0)
    engine.tick(60.0)
    events = engine.tick(120.0)
    state = engine.get_display_state()

    assert events.get("long_break_finished") is True
    assert state.phase == DeepFocusPhase.FOCUS
    assert state.running is True
    assert state.cycle_index == 2
    assert state.phase_remaining_seconds == 60


def test_deep_focus_pause_resume_keeps_prompt_schedule() -> None:
    engine = TimerEngine(
        mode=TimerMode.DEEP_FOCUS,
        random_prompt_min_minutes=3,
        random_prompt_max_minutes=3,
        randrange_inclusive=constant_random,
    )

    engine.start(0.0)
    engine.tick(120.0)
    engine.pause(120.0)
    assert engine.get_display_state().next_prompt_in_seconds == 60

    engine.start(220.0)
    events = engine.tick(280.0)
    assert events.get("random_prompt_hit") is True
