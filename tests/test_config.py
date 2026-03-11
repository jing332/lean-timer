from __future__ import annotations

import json

from lean_timer.bootstrap import TRAY_SUPPORT_NOTE, runtime_check
from lean_timer.config import load_config


def test_load_config_creates_default_close_to_tray(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load_config()

    assert config.close_to_tray is True
    assert config.deep_focus_auto_continue is False
    assert config.prompt_window_always_on_top is True
    payload = json.loads((tmp_path / ".config" / "lean-timer" / "config.json").read_text())
    assert payload["close_to_tray"] is True
    assert payload["deep_focus_auto_continue"] is False
    assert payload["prompt_window_always_on_top"] is True


def test_load_config_reads_close_to_tray_false(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config_path = tmp_path / ".config" / "lean-timer" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "mode_default": "countup",
                "pomodoro_focus_minutes": 25,
                "pomodoro_break_minutes": 5,
                "milestones_minutes": [30, 60, 90],
                "deep_focus_minutes": 90,
                "deep_break_minutes": 20,
                "deep_focus_auto_continue": True,
                "random_prompt_min_minutes": 3,
                "random_prompt_max_minutes": 5,
                "micro_rest_seconds": 10,
                "overlay_enabled": True,
                "window_always_on_top": True,
                "prompt_window_always_on_top": False,
                "close_to_tray": False,
            }
        ),
        encoding="utf-8",
    )

    config = load_config()

    assert config.close_to_tray is False
    assert config.deep_focus_auto_continue is True
    assert config.prompt_window_always_on_top is False


def test_runtime_check_reports_tray_support_hint(monkeypatch) -> None:
    monkeypatch.setattr("lean_timer.bootstrap._has_module", lambda _name: True)
    monkeypatch.setattr("lean_timer.bootstrap._has_display_session", lambda: True)

    ok, message = runtime_check(require_display=True)

    assert ok is True
    assert TRAY_SUPPORT_NOTE in message
