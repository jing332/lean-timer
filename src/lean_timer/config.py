from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    mode_default: str = "countup"
    pomodoro_focus_minutes: int = 25
    pomodoro_break_minutes: int = 5
    milestones_minutes: tuple[int, ...] = (30, 60, 90)
    deep_focus_minutes: int = 90
    deep_break_minutes: int = 20
    deep_focus_auto_continue: bool = False
    random_prompt_min_minutes: int = 3
    random_prompt_max_minutes: int = 5
    micro_rest_seconds: int = 10
    overlay_enabled: bool = True
    notifications_enabled: bool = True
    window_always_on_top: bool = True
    prompt_window_always_on_top: bool = True
    close_to_tray: bool = True


def _config_path() -> Path:
    base = Path.home() / ".config" / "lean-timer"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> AppConfig:
    path = _config_path()
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg)
        return cfg

    raw = json.loads(path.read_text(encoding="utf-8"))
    milestones = raw.get("milestones_minutes", [30, 60, 90])
    safe_milestones = tuple(
        sorted({int(v) for v in milestones if isinstance(v, int) or str(v).isdigit()})
    ) or (30, 60, 90)

    return AppConfig(
        mode_default=raw.get("mode_default", "countup"),
        pomodoro_focus_minutes=max(1, int(raw.get("pomodoro_focus_minutes", 25))),
        pomodoro_break_minutes=max(1, int(raw.get("pomodoro_break_minutes", 5))),
        milestones_minutes=safe_milestones,
        deep_focus_minutes=max(1, int(raw.get("deep_focus_minutes", 90))),
        deep_break_minutes=max(1, int(raw.get("deep_break_minutes", 20))),
        deep_focus_auto_continue=bool(raw.get("deep_focus_auto_continue", False)),
        random_prompt_min_minutes=max(1, int(raw.get("random_prompt_min_minutes", 3))),
        random_prompt_max_minutes=max(
            max(1, int(raw.get("random_prompt_min_minutes", 3))),
            int(raw.get("random_prompt_max_minutes", 5)),
        ),
        micro_rest_seconds=max(1, int(raw.get("micro_rest_seconds", 10))),
        overlay_enabled=bool(raw.get("overlay_enabled", True)),
        notifications_enabled=bool(raw.get("notifications_enabled", True)),
        window_always_on_top=bool(raw.get("window_always_on_top", True)),
        prompt_window_always_on_top=bool(raw.get("prompt_window_always_on_top", True)),
        close_to_tray=bool(raw.get("close_to_tray", True)),
    )


def save_config(config: AppConfig) -> None:
    payload = {
        "mode_default": config.mode_default,
        "pomodoro_focus_minutes": config.pomodoro_focus_minutes,
        "pomodoro_break_minutes": config.pomodoro_break_minutes,
        "milestones_minutes": list(config.milestones_minutes),
        "deep_focus_minutes": config.deep_focus_minutes,
        "deep_break_minutes": config.deep_break_minutes,
        "deep_focus_auto_continue": config.deep_focus_auto_continue,
        "random_prompt_min_minutes": config.random_prompt_min_minutes,
        "random_prompt_max_minutes": config.random_prompt_max_minutes,
        "micro_rest_seconds": config.micro_rest_seconds,
        "overlay_enabled": config.overlay_enabled,
        "notifications_enabled": config.notifications_enabled,
        "window_always_on_top": config.window_always_on_top,
        "prompt_window_always_on_top": config.prompt_window_always_on_top,
        "close_to_tray": config.close_to_tray,
    }
    _config_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
