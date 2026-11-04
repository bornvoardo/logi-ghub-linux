"""The panel has to show the layer without reading the daemon's memory.

The tray is a separate process. It learns the layer from one small file, watched
with GLib.FileMonitor, so the indicator follows the key within milliseconds and
costs nothing while the layer is idle. These tests pin the file format on both
sides, because a rename on one side would silently freeze the icon.
"""

from __future__ import annotations

import json

from logi_ghub import daemon as daemon_mod
from logi_ghub import tray as tray_mod


class FakePath:
    def __init__(self, payload: dict | None = None, bad: bool = False):
        self.payload = payload
        self.bad = bad

    def read_text(self) -> str:
        if self.bad:
            raise OSError("gone")
        return json.dumps(self.payload)


class FakeBus:
    def __init__(self):
        self.signals: list[tuple] = []

    def emit_signal(self, _conn, path, iface, name, _params):
        self.signals.append((path, iface, name))


def _tray(gshift_open: bool = False) -> "tray_mod.Tray":
    """A Tray without the D-Bus registration, which needs a session bus."""
    t = tray_mod.Tray.__new__(tray_mod.Tray)
    t.gshift_open = gshift_open
    t.bus = FakeBus()
    return t


# -- what the daemon writes --------------------------------------------------------


def test_the_daemon_writes_the_layer_as_a_plain_flag(tmp_path, monkeypatch):
    written = {}

    monkeypatch.setattr(daemon_mod, "config_dir", lambda: tmp_path)
    d = daemon_mod.Daemon.__new__(daemon_mod.Daemon)
    d._publish_layer(True)
    written["open"] = json.loads((tmp_path / "gshift-state.json").read_text())["open"]
    d._publish_layer(False)
    written["closed"] = json.loads((tmp_path / "gshift-state.json").read_text())["open"]

    assert written == {"open": True, "closed": False}


def test_a_write_that_fails_does_not_stop_the_keyboard(tmp_path, monkeypatch):
    """A read-only config directory must not take the layer down with it."""
    monkeypatch.setattr(daemon_mod, "config_dir", lambda: tmp_path / "missing" / "deep")
    d = daemon_mod.Daemon.__new__(daemon_mod.Daemon)
    d._publish_layer(True)  # must not raise


# -- what the tray reads -----------------------------------------------------------


def test_the_open_flag_arrives():
    t = _tray()
    t._read_layer(FakePath({"open": True}))
    assert t.gshift_open is True
    assert t.bus.signals == [("/StatusNotifierItem", "org.kde.StatusNotifierItem", "NewIcon")]


def test_the_closed_flag_arrives():
    t = _tray(gshift_open=True)
    t._read_layer(FakePath({"open": False}))
    assert t.gshift_open is False


def test_the_same_value_is_not_reported_twice():
    """FileMonitor fires more than once per write; the panel must not flicker."""
    t = _tray(gshift_open=True)
    t._read_layer(FakePath({"open": True}))
    assert t.bus.signals == []


def test_a_missing_file_reads_as_closed():
    t = _tray(gshift_open=True)
    t._read_layer(FakePath(bad=True))
    assert t.gshift_open is False


def test_a_broken_file_reads_as_closed():
    t = _tray(gshift_open=True)
    t._read_layer(FakePath({"nonsense": 1}))
    assert t.gshift_open is False


# -- what the panel shows ----------------------------------------------------------


def test_the_layer_changes_the_icon():
    t = _tray()
    t.states = {}
    normal = t.icon_name()
    t.gshift_open = True
    assert t.icon_name() == "logi-ghub-gshift"
    assert normal != "logi-ghub-gshift"


def test_the_layer_wins_over_the_low_battery_warning():
    """The G is momentary; a battery warning can wait a second."""
    t = _tray(gshift_open=True)

    class State:
        online = True
        battery = 5
        charging = False

    t.states = {"x": State()}
    assert t.icon_name() == "logi-ghub-gshift"
