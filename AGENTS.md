# AGENTS.md - Lean Timer Project Guide

## Project Overview

Lean Timer is a GTK4-based desktop timer application for Ubuntu, written in Python 3.10+.

Features:
- Count-up timer with milestone notifications
- Pomodoro timer (focus/break cycles)
- Deep Focus mode (90/20 rhythm with random micro-rest prompts)

## Build/Run/Test Commands

### Run the Application
```bash
./scripts/run.sh
```

### Self-Check (Verify Dependencies)
```bash
./scripts/check.sh
```

### Run All Tests
```bash
PYTHONPATH=src python3 -m pytest -q
```

### Run a Single Test
```bash
PYTHONPATH=src python3 -m pytest tests/test_timer_engine.py::test_name -v
```

### Run Tests with Output
```bash
PYTHONPATH=src python3 -m pytest -v
```

## Dependencies

System packages (Ubuntu):
```bash
sudo apt install -y python3 python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-notify-0.7
```

Python dependencies: None beyond stdlib + PyGObject (system package).

## Project Structure

```
lean-timer/
├── scripts/
│   ├── run.sh        # Main entry point
│   └── check.sh      # Dependency verification
├── src/lean_timer/
│   ├── __init__.py   # Package exports
│   ├── __main__.py   # CLI entry point
│   ├── app.py        # GTK UI (windows, widgets)
│   ├── timer_engine.py  # Core state machine logic
│   ├── config.py     # User configuration (JSON)
│   ├── alerts.py     # Notifications and sounds
│   └── bootstrap.py  # Runtime checks
└── tests/
    └── test_timer_engine.py  # Unit tests
```

## Code Style Guidelines

### Imports

```python
from __future__ import annotations  # Always first

import standard_library  # Stdlib first, alphabetical
import time

import gi  # Third-party next
import cairo

from gi.repository import Gdk, Gtk  # Third-party specific imports

from lean_timer.config import AppConfig  # Local imports last
from lean_timer.timer_engine import TimerEngine
```

- Use explicit imports: `from module import Name`
- Avoid `import *` except in `__init__.py` for `__all__`
- Group imports: stdlib → third-party → local (blank line between)

### Type Hints

```python
# Use modern union syntax (Python 3.10+)
def get_display_state(self) -> DisplayState:
    ...

phase: PomodoroPhase | DeepFocusPhase | None = None
phase_remaining_seconds: int | None = None

# Callable types
randrange_inclusive: Callable[[int, int], int] | None = None

# Iterable for sequences
milestones_minutes: Iterable[int] = (30, 60, 90)
```

- All functions and methods must have type hints
- Use `|` for unions (not `Optional` or `Union`)
- Use `None` explicitly for optional types

### Naming Conventions

```python
# Classes: PascalCase
class TimerEngine:
class DeepFocusPhase(str, Enum):

# Functions/methods: snake_case
def get_display_state(self) -> DisplayState:
def _tick_deep_focus(self, delta: float) -> float:

# Variables: snake_case
elapsed_seconds = 0
phase_remaining_seconds = None

# Constants: UPPER_SNAKE_CASE
REQUIRED_APT_PACKAGES = ("python3-gi",)

# Private methods: prefix with _
def _initialize_mode_state(self, mode: TimerMode) -> None:
```

### Dataclasses

```python
from dataclasses import dataclass

@dataclass(frozen=True)  # Use frozen=True for immutable state
class DisplayState:
    mode: TimerMode
    running: bool
    elapsed_seconds: int
    phase: PomodoroPhase | DeepFocusPhase | None = None
```

### Enums

```python
from enum import Enum

class TimerMode(str, Enum):  # Inherit from str for JSON serialization
    COUNTUP = "countup"
    POMODORO = "pomodoro"
    DEEP_FOCUS = "deep_focus"
```

### Error Handling

```python
# Check GTK API availability with hasattr()
if hasattr(self, "set_decorated"):
    self.set_decorated(False)

# Raise RuntimeError for critical failures
if not ok:
    raise RuntimeError("GTK display initialization failed")

# Subprocess calls with check=False (don't fail on errors)
subprocess.run([notify_send, title, body], check=False)
```

### Formatting

- Indentation: 4 spaces
- Max line length: ~88-100 characters
- Blank lines between class methods
- No trailing whitespace
- No blank lines after function docstrings

### GTK4 Patterns

```python
# Widget setup
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
box.set_margin_top(16)
box.set_halign(Gtk.Align.CENTER)

# Signal connections
self.start_btn.connect("clicked", self._on_start)

# Markup for labels
label.set_markup('<span size="32000" weight="bold">00:00:00</span>')

# Escape user text in markup
f'<span size="32000" weight="bold">{GLib.markup_escape_text(time_text)}</span>'
```

### Configuration

- User config stored in `~/.config/lean-timer/config.json`
- Use `dataclass` for config schema
- Validate/transform on load with defaults

## Testing Guidelines

```python
# Test file: tests/test_timer_engine.py

# Helper functions at module level
def constant_random(_minimum: int, _maximum: int) -> int:
    return _minimum

# Function-based tests (not class-based)
def test_countup_pause_resume_continuous() -> None:
    engine = TimerEngine(mode=TimerMode.COUNTUP, milestones_minutes=(30,))
    engine.start(100.0)
    engine.tick(105.0)
    engine.pause(105.0)
    assert engine.get_display_state().elapsed_seconds == 5

# Descriptive test names: test_<feature>_<scenario>
def test_deep_focus_random_prompt_triggers_micro_rest() -> None:
    ...

# Inject dependencies for deterministic testing
engine = TimerEngine(
    mode=TimerMode.DEEP_FOCUS,
    randrange_inclusive=constant_random,  # Fixed random for tests
)
```

## Key Architecture Notes

1. **State Machine**: `TimerEngine` is a pure state machine. It accepts monotonic timestamps, not wall-clock time.

2. **UI Separation**: `app.py` handles all GTK UI. `timer_engine.py` has no UI dependencies.

3. **Event-Driven**: `tick()` returns a dict of events (`{"milestone_hit": 30, "phase_changed": True}`). UI reacts to events.

4. **Configuration**: Config is loaded on startup and saved immediately on user changes.

5. **Chinese Localization**: UI text is in Chinese. Keep this consistent.