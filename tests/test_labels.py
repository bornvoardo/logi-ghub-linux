"""Keycap legends match the printing on the real board."""

from __future__ import annotations

import pytest

from logi_ghub import layout

# Measured from the keyboard: the lower symbol is printed next to the upper one
# on these keys, and the key between ; and Enter prints a backslash-pipe.
PRINTED = {
    "Grave": "`~",
    "Equal": "=+",
    "LeftBracket": "[{",
    "RightBracket": "]}",
    "Semicolon": ";:",
    "Apostrophe": "'\"",
    "Comma": ",<",
    "Dot": ".>",
    "Slash": "/?",
    "NonUSHash": "\\|",
    "RightMeta": "FN",
}


@pytest.mark.parametrize("name,legend", sorted(PRINTED.items()))
def test_legend_matches_the_keyboard(name, legend):
    assert layout.LABELS[name] == legend


def test_plain_keys_keep_their_single_legend():
    assert layout.LABELS["Minus"] == "-"
    assert layout.LABELS["Backspace"] == "⌫"
    assert layout.LABELS["CapsLock"] == "Caps"
    assert layout.LABELS["LeftShift"] == "Shift"
    assert layout.LABELS["LeftMeta"] == "Super"
    assert layout.LABELS["Space"] == ""


def test_keys_without_an_entry_show_their_name():
    """Esc and the digits have no separate legend; the name is what is printed."""
    for name in ("Esc", "1", "5", "0", "F1", "Q"):
        assert name not in layout.LABELS
        assert layout.KeyCap(name, 0, 0, 0, 1).label == name


def test_the_full_size_strip_has_no_badge_or_extra_buttons():
    """The board has no LIGHTSPEED badge and no three buttons to its right."""
    kinds = [kind for kind, *_rest in layout.FULL.decor]
    assert "badge" not in kinds
    assert kinds.count("button") == 1  # game mode only
    assert kinds.count("roller") == 1
