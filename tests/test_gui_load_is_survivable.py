"""One HID++ call the device refuses must not blank the whole window.

What went wrong: load() hands read() to run_async(fn, done, error). If read()
raises, done is never called, so loaded() never runs, so build_profiles(),
build_dpi() and the rest never run, and every pane stays empty. The only trace was
a toast reading "Error: HID++ error 0x02 ... RGB_EFFECTS fn 5".

The trigger was get_sw_control(), which the G915 X answers with "invalid argument"
while it is in on-board mode: a normal state, not a fault. That one readout cost the
entire content area.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "logi_ghub" / "gui" / "app.py"


def _read_fn():
    """The nested read() inside DevicePane.load()."""
    tree = ast.parse(APP.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "read":
            if any(isinstance(n, ast.Name) and n.id == "attempt" for n in ast.walk(node)):
                return node
    return None


def test_every_readout_goes_through_the_guarded_helper():
    """A bare data["k"] = dev.something() inside read() is the bug coming back.

    The helper itself writes data[key], and read_stored() writes the second half of
    the pair it read; both are checked to be on the safe side of a try.
    """
    read = _read_fn()
    assert read is not None, "read() should use the guarded attempt() helper"

    def guarded(node) -> bool:
        """Whether this assign sits inside the attempt() helper or a try block."""
        for parent in ast.walk(read):
            if not isinstance(parent, (ast.Try, ast.FunctionDef)):
                continue
            if parent is read:
                continue
            if any(n is node for n in ast.walk(parent)):
                return True
        return False

    for node in ast.walk(read):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if guarded(node):
                continue
            key = getattr(target.slice, "value", None)
            raise AssertionError(f"unguarded read: data[{key!r}] = ...")


def test_the_helper_catches_what_a_device_can_raise():
    src = APP.read_text()
    body = src[src.index("def attempt(key, fn):"):src.index("if dev.onboard:")]
    for exc in ("HIDPPError", "DeviceOffline", "TimeoutError", "OSError", "ValueError", "KeyError"):
        assert exc in body, f"{exc} should be caught"


def test_a_failed_readout_does_not_stop_the_others():
    """The helper must write the key only on success, and must not re-raise."""
    src = APP.read_text()
    body = src[src.index("def attempt(key, fn):"):src.index("if dev.onboard:")]
    assert "data[key] = fn()" in body
    assert "raise" not in body.split("except")[1]


def test_the_lighting_readout_is_guarded():
    """The exact call that blanked the window."""
    src = APP.read_text()
    read = src[src.index("def read():"):src.index("run_async(read, self.loaded, self.fail)")]
    assert 'attempt("sw_control"' in read
    assert 'attempt("onboard_effects"' in read


def test_an_empty_pane_is_never_the_result_of_a_failed_readout():
    """loaded() is what builds the panes; it must not depend on readouts that are
    allowed to fail."""
    src = APP.read_text()
    loaded = src[src.index("def loaded(self, data: dict):"):src.index("def rebuild(self):")]
    # Every value it needs has a fallback.
    for key in ("slots", "dpi_values", "hz", "stored_profiles", "onboard_effects"):
        assert f'data.get("{key}"' in loaded, f"{key} needs a default"
