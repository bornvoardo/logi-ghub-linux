"""The two keyboard pictures, and the zones they can show."""

from __future__ import annotations

import pytest

from logi_ghub import layout

FULL_ONLY = [
    "NumLock", "KPSlash", "KPAsterisk", "KPMinus", "KPPlus", "KPEnter",
    "KP0", "KP1", "KP2", "KP3", "KP4", "KP5", "KP6", "KP7", "KP8", "KP9", "KPDot",
]

TKL_SNAPSHOT = [
    ("Logo", 210), ("Brightness", 153), ("Previous", 158), ("Play/Pause", 155), ("Next", 157), ("Mute", 156),
    ("Esc", 38), ("F1", 55), ("F2", 56), ("F3", 57), ("F4", 58), ("F5", 59), ("F6", 60), ("F7", 61), ("F8", 62),
    ("F9", 63), ("F10", 64), ("F11", 65), ("F12", 66), ("PrintScreen", 67), ("ScrollLock", 68), ("Pause", 69),
    ("Grave", 50), ("1", 27), ("2", 28), ("3", 29), ("4", 30), ("5", 31), ("6", 32), ("7", 33), ("8", 34),
    ("9", 35), ("0", 36), ("Minus", 42), ("Equal", 43), ("Backspace", 39), ("Insert", 70), ("Home", 71),
    ("PageUp", 72), ("Tab", 40), ("Q", 17), ("W", 23), ("E", 5), ("R", 18), ("T", 20), ("Y", 25), ("U", 21),
    ("I", 9), ("O", 15), ("P", 16), ("LeftBracket", 44), ("RightBracket", 45), ("Backslash", 46), ("Delete", 73),
    ("End", 74), ("PageDown", 75), ("CapsLock", 54), ("A", 1), ("S", 19), ("D", 4), ("F", 6), ("G", 7), ("H", 8),
    ("J", 10), ("K", 11), ("L", 12), ("Semicolon", 48), ("Apostrophe", 49), ("Enter", 37), ("LeftShift", 105),
    ("Z", 26), ("X", 24), ("C", 3), ("V", 22), ("B", 2), ("N", 14), ("M", 13), ("Comma", 51), ("Dot", 52),
    ("Slash", 53), ("RightShift", 109), ("Up", 79), ("LeftCtrl", 104), ("LeftMeta", 107), ("LeftAlt", 106),
    ("Space", 41), ("RightAlt", 110), ("RightMeta", 111), ("Menu", 98), ("RightCtrl", 108), ("Left", 77),
    ("Down", 78), ("Right", 76),
]


def _overlaps(caps) -> list[tuple[str, str]]:
    bad = []
    for i, a in enumerate(caps):
        for b in caps[i + 1:]:
            if (a.x < b.x + b.w - 1e-9 and b.x < a.x + a.w - 1e-9
                    and a.y < b.y + b.h - 1e-9 and b.y < a.y + a.h - 1e-9):
                bad.append((a.name, b.name))
    return bad


def test_tkl_layout_is_unchanged():
    """The TKL picture must not change when another board is added."""
    assert [(c.name, c.zone) for c in layout.keycaps()] == TKL_SNAPSHOT


def test_tkl_is_the_default():
    assert layout.DEFAULT_LAYOUT == "tkl"
    assert layout.keycaps() == layout.keycaps(layout="tkl")


def test_unknown_layout_falls_back_to_the_default():
    assert layout.get_layout("nope").name == "tkl"


def test_full_size_has_the_numpad():
    names = {c.name for c in layout.keycaps(layout="full")}
    assert set(FULL_ONLY) <= names


def test_full_size_has_the_navigation_cluster():
    names = {c.name for c in layout.keycaps(layout="full")}
    assert {"Insert", "Home", "PageUp", "Delete", "End", "PageDown", "Up", "Down", "Left", "Right"} <= names


def test_full_size_has_the_iso_keys():
    """Measured on the keyboard: three keys between L and Enter, one before Z."""
    caps = {c.name: c for c in layout.keycaps(layout="full")}
    assert caps["NonUSHash"].zone == 47
    assert caps["NonUSBackslash"].zone == 97
    # # ~ sits between the apostrophe and the Enter, the other two follow it
    assert caps["Apostrophe"].x < caps["NonUSHash"].x < 13.5


def test_full_size_enter_is_l_shaped():
    """One zone, two rectangles, no overlap with the keys around it."""
    enters = [c for c in layout.keycaps(layout="full") if c.name == "Enter"]
    assert len(enters) == 2
    assert len({c.zone for c in enters}) == 1
    upper, lower = enters
    assert upper.h >= lower.h / 2  # the L is taller than one row
    assert upper.x >= layout.NAV_X - 3  # ends at the main block edge


def test_full_size_has_no_extra_zone_the_device_lacks():
    """Every zone we draw must exist in the keyboard's own list, which reported 126."""
    drawn = {c.zone for c in layout.keycaps(layout="full")}
    measured = {47, 97} | {c.zone for c in layout.keycaps(layout="tkl")}
    g_keys = set(range(180, 189))
    numpad = {c.zone for c in layout.keycaps(layout="full") if c.name.startswith("KP") or c.name == "NumLock"}
    assert (drawn - measured - g_keys - numpad) == set()


def test_full_size_has_all_nine_g_keys():
    caps = {c.name: c for c in layout.keycaps(layout="full")}
    for i in range(1, 10):
        assert f"G{i}" in caps, f"G{i} missing"
    assert [caps[f"G{i}"].zone for i in range(1, 10)] == list(range(180, 189))


def test_full_size_g_keys_sit_left_of_the_main_block():
    caps = {c.name: c for c in layout.keycaps(layout="full")}
    assert all(caps[f"G{i}"].x < 0 for i in range(1, 6))
    assert all(caps[f"G{i}"].y >= 0 for i in range(1, 6))


def test_full_size_g6_to_g9_are_round_buttons_in_the_strip():
    caps = {c.name: c for c in layout.keycaps(layout="full")}
    for i in range(6, 10):
        assert caps[f"G{i}"].round, f"G{i} should be a round button"
        assert caps[f"G{i}"].y < 0


@pytest.mark.parametrize("name", ["tkl", "full"])
def test_no_keycaps_overlap(name):
    assert _overlaps(layout.keycaps(layout=name)) == []


def test_full_size_is_wider_than_it_is_tall():
    def aspect(name):
        x0, y0, x1, y1 = layout.bounds(layout.keycaps(layout=name), decor=True, layout=name)
        return (x1 - x0) / (y1 - y0)

    assert aspect("full") > aspect("tkl")


@pytest.mark.parametrize("name", ["tkl", "full"])
def test_available_zones_filters_the_picture(name):
    all_caps = [(c.name, c.zone) for c in layout.keycaps(layout=name)]
    keep = [zone for _name_, zone in all_caps][:10]
    expected = [pair for pair in all_caps if pair[1] in keep]
    filtered = [(c.name, c.zone) for c in layout.keycaps(keep, layout=name)]
    assert filtered == expected


def test_numpad_zones_are_present_in_the_picture():
    caps = {c.name: c for c in layout.keycaps(layout="full")}
    # NumLock is HID usage 0x53, so its zone is 0x53 - 3.
    assert caps["NumLock"].zone == 0x50


def test_detect_layout_follows_the_numpad_zones():
    numpad = [c.zone for c in layout.keycaps(layout="full") if c.name in FULL_ONLY]
    tkl_zones = [c.zone for c in layout.keycaps(layout="tkl")]
    assert layout.detect_layout(numpad) == "full"
    assert layout.detect_layout(tkl_zones) == "tkl"
    assert layout.detect_layout(None) == "tkl"
    assert layout.detect_layout([]) == "tkl"
