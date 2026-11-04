"""A per-key frame must cover the whole board, or the keyboard blacks out keys."""

from __future__ import annotations

import pytest

from logi_ghub import layout, lightfx

ZONES = sorted({c.zone for c in layout.keycaps(layout="full")})
NUMPAD = {z for z in ZONES if 80 <= z <= 100}
GKEYS = {z for z in ZONES if 180 <= z <= 188}


class FakePerKey:
    def __init__(self):
        self.zones = ZONES
        self.last: dict[int, int] | None = None

    def set_colors(self, colors):
        self.last = dict(colors)


class FakeRGB:
    zones = [0, 1]

    def claim(self):
        pass

    def hold_static(self, skip=()):
        pass

    def set_effect(self, zone, effect):
        pass


class FakeDevice:
    key = "046d:c359"
    rgb = FakeRGB()
    brightness = None

    def __init__(self):
        self.per_key = FakePerKey()


def _apply(layout_name=None):
    dev = FakeDevice()
    lightfx.apply(dev, {"zones": {"0": {"effect": 1, "color": 0xFFFFFF}},
                        "keys": {"52": 0xFF0000}}, layout_name=layout_name)
    return dev.per_key.last or {}


def test_the_frame_has_every_zone_even_without_a_layout_name():
    """The service calls apply() without a layout name; that used to build a TKL
    frame, and the keyboard switched off every zone the frame left out."""
    frame = _apply()
    assert set(frame) == set(ZONES)


def test_the_numpad_and_the_g_keys_are_lit():
    frame = _apply()
    for zone in NUMPAD | GKEYS:
        assert frame[zone] != 0, zone


def test_a_wrong_layout_name_still_lights_the_whole_board():
    """The app's own board choice must not be able to black out keys either."""
    frame = _apply("tkl")
    assert set(frame) == set(ZONES)


def test_a_painted_key_keeps_its_colour():
    frame = _apply()
    assert frame[52] == 0xFF0000


def test_widen_leaves_a_complete_frame_alone():
    complete = {z: 0x00FF00 for z in ZONES}
    assert lightfx._widen(complete, ZONES) == complete


def test_widen_fills_the_gaps_it_finds():
    partial = {52: 0xFF0000}
    widened = lightfx._widen(partial, ZONES)
    assert set(widened) == set(ZONES)
    assert widened[52] == 0xFF0000
    assert all(c != 0 for z, c in widened.items() if z != 52)
