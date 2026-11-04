"""Alignment of the strip above the F-row."""

from __future__ import annotations

from logi_ghub import layout


def _caps(name):
    return {c.name: c for c in layout.keycaps(layout=name)}


def test_logo_sits_over_the_first_g_column():
    caps = _caps("full")
    logo, g1 = caps["Logo"], caps["G1"]
    assert abs((logo.x + logo.w / 2) - (g1.x + g1.w / 2)) < 0.01


def test_media_keys_are_on_the_f_row_line():
    caps = _caps("full")
    f_row = caps["F1"].y + caps["F1"].h / 2
    for name in ("Previous", "Play/Pause", "Next", "Mute"):
        cap = caps[name]
        assert abs((cap.y + cap.h / 2) - f_row) < 0.01, name


def test_the_strip_does_not_overlap_the_keys_below():
    caps = list(_caps("full").values())
    for i, a in enumerate(caps):
        for b in caps[i + 1:]:
            if a.name == "Enter" and b.name == "Enter":
                continue
            overlaps = (
                a.x < b.x + b.w - 1e-9 and b.x < a.x + a.w - 1e-9
                and a.y < b.y + b.h - 1e-9 and b.y < a.y + a.h - 1e-9
            )
            assert not overlaps, (a.name, b.name)
