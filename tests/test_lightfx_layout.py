"""The lighting frame must cover every key the keyboard has.

Painting one key sends the whole frame to the keyboard, so a key missing from
the frame is a key that goes dark.
"""

from __future__ import annotations

import pytest

from logi_ghub import layout, lightfx

STATIC_WHITE = {"zones": {"0": {"effect": 1, "color": 0xFFFFFF}}}


def _zones(name):
    return [c.zone for c in layout.keycaps(layout=name)]


@pytest.mark.parametrize("name", ["tkl", "full"])
def test_frame_covers_every_key_of_the_board(name):
    zones = _zones(name)
    renderer = lightfx.Renderer(STATIC_WHITE, zones)
    frame = renderer.frame(0.0)
    assert set(frame) == set(zones)


def test_frame_covers_the_numpad_and_the_g_keys():
    """These are exactly the keys that went dark on a full-size board."""
    frame = lightfx.Renderer(STATIC_WHITE, _zones("full")).frame(0.0)
    numpad = [c.zone for c in layout.keycaps(layout="full") if c.name.startswith("KP") or c.name == "NumLock"]
    g_keys = [c.zone for c in layout.keycaps(layout="full") if c.name.startswith("G") and c.name[1:].isdigit()]
    assert set(numpad) <= set(frame)
    assert set(g_keys) <= set(frame)


def test_renderer_picks_the_board_from_the_zone_list():
    """A caller that passes no layout name still gets the right board."""
    full = lightfx.Renderer(STATIC_WHITE, _zones("full"))
    tkl = lightfx.Renderer(STATIC_WHITE, _zones("tkl"))
    assert len(full.caps) > len(tkl.caps)


def test_an_explicit_layout_name_still_wins():
    renderer = lightfx.Renderer(STATIC_WHITE, _zones("full"), layout_name="tkl")
    assert len(renderer.caps) == len(layout.keycaps(layout="tkl"))
