"""Physical keyboard layout: where each lighting zone sits, for drawing and for wave animations.

Two boards are described here: the G915 X LIGHTSPEED TKL and the full-size
G915 X. Both use the same per-key zone ids, so the difference is only where the
keys sit and which extra keys exist.

A key entry in ``rows`` is ``(name, width)``. ``None`` as the name draws a gap.
Widths are in key units (1 unit = one standard keycap). ``rows`` are laid out
left to right from x=0 and describe the main block only. Keys that are not part
of the main block (the navigation cluster, the numpad, the G-key column) go in
``extra`` with an explicit position. That keeps the TKL rows identical to what
they were before the full-size board was added.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import keys
from .features import lighting

# The strip above the keys, at this y. Lit names have a zone; the rest are drawn only.
TOP_Y = -1.45

# --- TKL ---------------------------------------------------------------------
# Rows of (key name or None for a gap, width in key units). Names are keys.KEY_NAMES or lighting.SPECIAL_ZONES.
TKL_ANSI: list[list[tuple[str | None, float]]] = [
    [("Esc", 1), (None, 1), ("F1", 1), ("F2", 1), ("F3", 1), ("F4", 1), (None, 0.5), ("F5", 1), ("F6", 1), ("F7", 1),
     ("F8", 1), (None, 0.5), ("F9", 1), ("F10", 1), ("F11", 1), ("F12", 1), (None, 0.25), ("PrintScreen", 1),
     ("ScrollLock", 1), ("Pause", 1)],
    [("Grave", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1), ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1),
     ("Minus", 1), ("Equal", 1), ("Backspace", 2), (None, 0.25), ("Insert", 1), ("Home", 1), ("PageUp", 1)],
    [("Tab", 1.5), ("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1), ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1),
     ("LeftBracket", 1), ("RightBracket", 1), ("Backslash", 1.5), (None, 0.25), ("Delete", 1), ("End", 1), ("PageDown", 1)],
    [("CapsLock", 1.75), ("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1), ("H", 1), ("J", 1), ("K", 1), ("L", 1),
     ("Semicolon", 1), ("Apostrophe", 1), ("Enter", 2.25)],
    [("LeftShift", 2.25), ("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1), ("N", 1), ("M", 1), ("Comma", 1), ("Dot", 1),
     ("Slash", 1), ("RightShift", 2.75), (None, 1.25), ("Up", 1)],
    [("LeftCtrl", 1.25), ("LeftMeta", 1.25), ("LeftAlt", 1.25), ("Space", 6.25), ("RightAlt", 1.25), ("RightMeta", 1.25),
     ("Menu", 1.25), ("RightCtrl", 1.25), (None, 0.25), ("Left", 1), ("Down", 1), ("Right", 1)],
]

# The strip above the keys on the G915 X TKL: (name, x, width). Lit ones have a zone; the rest are drawn only.
TOP_ROW: list[tuple[str, float, float]] = [
    ("Logo", 0.1, 0.8),
    ("Brightness", 5.1, 0.8),
    ("Previous", 12.6, 0.8), ("Play/Pause", 13.6, 0.8), ("Next", 14.6, 0.8), ("Mute", 15.6, 0.8),
]
ROUND = {"Brightness", "Previous", "Play/Pause", "Next", "Mute"}
# Unlit parts of that strip, for the picture: (kind, x, y, width, height)
DECOR: list[tuple[str, float, float, float, float]] = [
    ("button", 2.1, TOP_Y, 0.8, 0.8), ("button", 3.1, TOP_Y, 0.8, 0.8), ("button", 4.1, TOP_Y, 0.8, 0.8),
    ("badge", 7.65, TOP_Y - 0.05, 2.2, 0.9),
    ("roller", 16.75, TOP_Y - 0.2, 1.45, 1.05),
]

# --- full-size ---------------------------------------------------------------
# The main block is the same on both boards: 15 key units wide, without the
# navigation cluster. On the TKL the cluster shares the main rows (see above);
# on the full-size it is its own block, so the rows stop after Backslash /
# RightShift.
MAIN_ROWS: list[list[tuple[str | None, float]]] = [
    [("Esc", 1), (None, 1), ("F1", 1), ("F2", 1), ("F3", 1), ("F4", 1), (None, 0.5), ("F5", 1), ("F6", 1), ("F7", 1),
     ("F8", 1), (None, 0.5), ("F9", 1), ("F10", 1), ("F11", 1), ("F12", 1)],
    [("Grave", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1), ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1),
     ("Minus", 1), ("Equal", 1), ("Backspace", 2)],
    [("Tab", 1.5), ("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1), ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1),
     ("LeftBracket", 1), ("RightBracket", 1), ("Backslash", 1.5)],
    [("CapsLock", 1.75), ("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1), ("H", 1), ("J", 1), ("K", 1), ("L", 1),
     ("Semicolon", 1), ("Apostrophe", 1), ("Enter", 2.25)],
    [("LeftShift", 2.25), ("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1), ("N", 1), ("M", 1), ("Comma", 1), ("Dot", 1),
     ("Slash", 1), ("RightShift", 2.75)],
    [("LeftCtrl", 1.25), ("LeftMeta", 1.25), ("LeftAlt", 1.25), ("Space", 6.25), ("RightAlt", 1.25), ("RightMeta", 1.25),
     ("Menu", 1.25), ("RightCtrl", 1.25)],
]

# Main block ends at x=15. Then the navigation block (3 wide) and the numpad
# (4 wide), each separated by a 0.25-unit gap, as on a standard ANSI board.
NAV_X = 15.25
PAD_X = 18.5
GKEY_X = -1.25  # the G1..G5 column sits to the left of the main block


def _nav_and_pad() -> list["KeySpec"]:
    """The navigation cluster and the numpad of a full-size board."""
    specs = [
        # top row of the navigation cluster, level with the F-row
        KeySpec("PrintScreen", NAV_X, 0, 1), KeySpec("ScrollLock", NAV_X + 1, 0, 1),
        KeySpec("Pause", NAV_X + 2, 0, 1),
        # the six-key block
        KeySpec("Insert", NAV_X, 1.25, 1), KeySpec("Home", NAV_X + 1, 1.25, 1),
        KeySpec("PageUp", NAV_X + 2, 1.25, 1),
        KeySpec("Delete", NAV_X, 2.25, 1), KeySpec("End", NAV_X + 1, 2.25, 1),
        KeySpec("PageDown", NAV_X + 2, 2.25, 1),
        # arrows, the inverted T
        KeySpec("Up", NAV_X + 1, 4.25, 1),
        KeySpec("Left", NAV_X, 5.25, 1), KeySpec("Down", NAV_X + 1, 5.25, 1),
        KeySpec("Right", NAV_X + 2, 5.25, 1),
        # numpad
        KeySpec("NumLock", PAD_X, 1.25, 1), KeySpec("KPSlash", PAD_X + 1, 1.25, 1),
        KeySpec("KPAsterisk", PAD_X + 2, 1.25, 1), KeySpec("KPMinus", PAD_X + 3, 1.25, 1),
        KeySpec("KP7", PAD_X, 2.25, 1), KeySpec("KP8", PAD_X + 1, 2.25, 1), KeySpec("KP9", PAD_X + 2, 2.25, 1),
        KeySpec("KPPlus", PAD_X + 3, 2.25, 1, h=2.0),
        KeySpec("KP4", PAD_X, 3.25, 1), KeySpec("KP5", PAD_X + 1, 3.25, 1), KeySpec("KP6", PAD_X + 2, 3.25, 1),
        KeySpec("KP1", PAD_X, 4.25, 1), KeySpec("KP2", PAD_X + 1, 4.25, 1), KeySpec("KP3", PAD_X + 2, 4.25, 1),
        KeySpec("KPEnter", PAD_X + 3, 4.25, 1, h=2.0),
        KeySpec("KP0", PAD_X, 5.25, 2), KeySpec("KPDot", PAD_X + 2, 5.25, 1),
    ]
    # G1..G5 are a column on the left edge, level with the rows below the F-row.
    for i in range(5):
        specs.append(KeySpec(f"G{i + 1}", GKEY_X, 1.25 + i, 1))
    return specs


@dataclass(frozen=True)
class KeySpec:
    """A key that is not part of the main rows: an explicit position in key units."""

    name: str
    x: float
    y: float
    w: float
    h: float = 1.0


@dataclass(frozen=True)
class KeyboardLayout:
    name: str
    rows: list[list[tuple[str | None, float]]]
    top_row: list[tuple[str, float, float]]
    decor: list[tuple[str, float, float, float, float]]
    round_keys: frozenset[str]
    extra: tuple[KeySpec, ...] = ()


TKL = KeyboardLayout("tkl", TKL_ANSI, TOP_ROW, DECOR, frozenset(ROUND))

# Media keys right-aligned over the numpad, G6..G9 in the strip on the left.
FULL_TOP_ROW: list[tuple[str, float, float]] = [
    ("Logo", 0.1, 0.8),
    ("G6", 1.9, 0.8), ("G7", 2.9, 0.8), ("G8", 3.9, 0.8), ("G9", 4.9, 0.8),
    ("Brightness", 6.4, 0.8),
    ("Previous", 18.6, 0.8), ("Play/Pause", 19.6, 0.8), ("Next", 20.6, 0.8), ("Mute", 21.6, 0.8),
]
FULL_DECOR: list[tuple[str, float, float, float, float]] = [
    ("button", 6.4, TOP_Y, 0.8, 0.8),          # game mode, left of the media keys of the strip
    ("badge", 8.0, TOP_Y - 0.05, 2.2, 0.9),
    ("button", 10.6, TOP_Y, 0.8, 0.8), ("button", 11.6, TOP_Y, 0.8, 0.8), ("button", 12.6, TOP_Y, 0.8, 0.8),
    ("roller", 22.75, TOP_Y - 0.2, 1.45, 1.05),
]
FULL = KeyboardLayout(
    "full", MAIN_ROWS, FULL_TOP_ROW, FULL_DECOR,
    frozenset({"Brightness", "Previous", "Play/Pause", "Next", "Mute", "G6", "G7", "G8", "G9"}),
    tuple(_nav_and_pad()),
)

LAYOUTS: dict[str, KeyboardLayout] = {TKL.name: TKL, FULL.name: FULL}
DEFAULT_LAYOUT = TKL.name

LABELS = {
    "Grave": "`", "Minus": "-", "Equal": "=", "LeftBracket": "[", "RightBracket": "]", "Backslash": "\\",
    "Semicolon": ";", "Apostrophe": "'", "Comma": ",", "Dot": ".", "Slash": "/", "Backspace": "⌫", "Enter": "⏎",
    "LeftShift": "Shift", "RightShift": "Shift", "LeftCtrl": "Ctrl", "RightCtrl": "Ctrl", "LeftAlt": "Alt",
    "RightAlt": "AltGr", "LeftMeta": "Super", "RightMeta": "Super", "Menu": "☰", "CapsLock": "Caps",
    "PrintScreen": "PrtSc", "ScrollLock": "ScrLk", "PageUp": "PgUp", "PageDown": "PgDn", "Delete": "Del",
    "Insert": "Ins", "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "Space": "", "Brightness": "☀",
    "Previous": "⏮", "Next": "⏭", "Mute": "×", "Play/Pause": "⏯", "Pause": "Pause", "Logo": "G",
    "NumLock": "Num", "KPSlash": "/", "KPAsterisk": "*", "KPMinus": "-", "KPPlus": "+", "KPEnter": "⏎",
    "KPDot": ".", "KPEqual": "=",
}

@dataclass(frozen=True)
class KeyCap:
    name: str
    zone: int
    x: float  # left edge, key units
    y: float  # top edge, rows
    w: float
    h: float = 1.0
    rounded: bool = False  # drawn as a round button of the strip above the keys

    @property
    def round(self) -> bool:
        return self.rounded

    @property
    def label(self) -> str:
        if self.name in LABELS:
            return LABELS[self.name]
        if self.name.startswith("KP") and self.name[2:].isdigit():
            return self.name[2:]
        return self.name

    @property
    def cx(self) -> float:
        return self.x + self.w / 2


def zone_of(name: str) -> int | None:
    if name in lighting.SPECIAL_ZONES:
        return lighting.SPECIAL_ZONES[name]
    if name in keys.KEY_BY_NAME:
        return lighting.zone_for_hid(keys.hid_for(name))
    return None


def get_layout(name: str | None) -> KeyboardLayout:
    """The named layout, or the default when the name is unknown."""
    return LAYOUTS.get(name or "", LAYOUTS[DEFAULT_LAYOUT])


def keycaps(available_zones: list[int] | None = None, layout: str = DEFAULT_LAYOUT) -> list[KeyCap]:
    """Key positions, with the logo and media buttons in the strip above the function row like on the keyboard."""
    board = get_layout(layout)
    caps = []

    def add(name, x, y, w, h=1.0):
        zone = zone_of(name)
        if zone is not None and (available_zones is None or zone in available_zones):
            caps.append(KeyCap(name, zone, x, y, w, h, name in board.round_keys))

    for name, x, w in board.top_row:
        add(name, x, TOP_Y, w, w)
    for r, row in enumerate(board.rows):
        y = r + (0.25 if r else 0)  # small gap under the F-row
        x = 0.0
        for name, width in row:
            if name is not None:
                add(name, x, y, width)
            x += width
    for spec in board.extra:
        add(spec.name, spec.x, spec.y, spec.w, spec.h)
    return caps


def bounds(caps: list[KeyCap], decor: bool = False,
           layout: str = DEFAULT_LAYOUT) -> tuple[float, float, float, float]:
    boxes = [(c.x, c.y, c.x + c.w, c.y + c.h) for c in caps]
    if decor:
        boxes += [(x, y, x + w, y + h) for _k, x, y, w, h in get_layout(layout).decor]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
