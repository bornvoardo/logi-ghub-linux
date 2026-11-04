"""Where the live-update methods live, and that the window can call them.

This is a static check on purpose: the GUI needs GTK, a display and real devices,
so it cannot be built in CI. What broke was a method defined on the wrong class,
and that is visible in the source.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "src" / "logi_ghub" / "gui" / "app.py"

OWN_METHODS = {"watch_active_changes", "_on_active_changed", "_redraw_profiles"}


def _classes():
    tree = ast.parse(APP.read_text())
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def _methods(class_node) -> set[str]:
    return {n.name for n in class_node.body if isinstance(n, ast.FunctionDef)}


def test_the_live_update_methods_belong_to_the_window():
    """They touch current_pane, the pane's stack and build_profiles, all of which
    only the window has. They were written on DevicePane, so MainWindow.__init__
    raised AttributeError the moment the app started."""
    classes = _classes()
    assert OWN_METHODS <= _methods(classes["MainWindow"])


def test_the_device_pane_does_not_carry_them():
    """A pane does not know whether it is the one on screen; the window does."""
    classes = _classes()
    assert not (OWN_METHODS & _methods(classes["DevicePane"]))


def test_the_window_initialises_what_the_monitor_needs_before_starting_it():
    """A monitor assigned in __init__ after watch_active_changes() would fail."""
    src = APP.read_text()
    start = src.index("class MainWindow")
    body = src[start:]
    monitor_at = body.index("self._active_monitor = None")
    pending_at = body.index("self._pending_redraw = 0")
    call_at = body.index("self.watch_active_changes()")
    assert monitor_at < call_at
    assert pending_at < call_at


def test_the_call_is_guarded_against_fake_mode():
    """The fake run has no config directory to watch."""
    src = APP.read_text()[APP.read_text().index("class MainWindow"):]
    assert "if not fake:" in src
    guard = src.index("if not fake:")
    assert guard < src.index("self.watch_active_changes()")


def test_the_redraw_only_touches_the_page_on_screen():
    """Redrawing a hidden page does work for nothing, and redrawing under an open
    dialog would drop what the user typed."""
    src = APP.read_text()
    body = src[src.index("def _redraw_profiles"):src.index("def _on_close_request")]
    assert "dirty" in body
    assert 'get_visible_child_name() != "profiles"' in src
