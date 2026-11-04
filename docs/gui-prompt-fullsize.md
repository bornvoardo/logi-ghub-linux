# GUI promptu — G915 X full-size klavye çizimi

Bu promptu bir AI kod aracına (Claude Code, Codex, Cursor vb.) verin.
Çıktıyı `~/projects/logi-ghub-linux` içine uygulayacağız; kod incelemesini ben yapacağım.

---

You are extending a Python GTK4/libadwaita app called logi-ghub-linux. It draws
an on-screen picture of a Logitech keyboard for per-key RGB lighting and key
assignment. The app currently supports only the G915 X LIGHTSPEED TKL. Add
support for the G915 X WIRED FULL-SIZE (with numpad).

## Hard rules
- Do NOT invent zone numbers, HID usages or key widths. If a value is not given
  below and cannot be derived, leave a clearly marked `# TODO(verify):` comment
  instead of guessing.
- Do NOT change the drawing engine (class KeyboardView in gui/keyboard.py).
  It already scales automatically from layout.bounds().
- Keep the existing TKL layout working byte-for-byte. No behaviour change for it.
- Python 3.11+, stdlib only, no new dependencies.

## Files you will touch
1. src/logi_ghub/layout.py       (the layout data + keycaps())
2. src/logi_ghub/gui/keyboard.py (one call site, line ~46)
3. src/logi_ghub/lightfx.py      (one call site, line ~90)
4. tests/                        (one new test file)

## Current code you must match
layout.py defines:
```
TKL_ANSI: list[list[tuple[str | None, float]]]    # rows: (key name or gap, width in key units)
TOP_Y = -1.45
TOP_ROW: list[tuple[str, float, float]]           # (name, x, width) — the strip above the F-row
ROUND: set[str]                                   # keys drawn round
DECOR: list[tuple[str, float, float, float, float]]  # (kind, x, y, w, h) — unlit drawn-only parts
LABELS: dict[str, str]                            # key name -> printed legend

@dataclass(frozen=True)
class KeyCap:
    name: str
    zone: int
    x: float      # left edge, key units
    y: float      # top edge, rows
    w: float
    h: float = 1.0

def zone_of(name: str) -> int | None
def keycaps(available_zones: list[int] | None = None) -> list[KeyCap]
def bounds(caps: list[KeyCap], decor: bool = False) -> tuple[float, float, float, float]
```

`keycaps()` iterates `TOP_ROW` then `TKL_ANSI`, and for each named key calls
`add(name, x, y, w, h)`, which appends a KeyCap only when `zone_of(name)`
returns a zone that is present in `available_zones` (when that argument is not
None).

## Reference: the existing TKL rows (copy this style exactly)
```python
[
 [("Esc",1),(None,1),("F1",1),("F2",1),("F3",1),("F4",1),(None,0.5),("F5",1),("F6",1),("F7",1),
  ("F8",1),(None,0.5),("F9",1),("F10",1),("F11",1),("F12",1),(None,0.25),("PrintScreen",1),
  ("ScrollLock",1),("Pause",1)],
 [("Grave",1),("1",1),("2",1),("3",1),("4",1),("5",1),("6",1),("7",1),("8",1),("9",1),("0",1),
  ("Minus",1),("Equal",1),("Backspace",2),(None,0.25),("Insert",1),("Home",1),("PageUp",1)],
 [("Tab",1.5),("Q",1),("W",1),("E",1),("R",1),("T",1),("Y",1),("U",1),("I",1),("O",1),("P",1),
  ("LeftBracket",1),("RightBracket",1),("Backslash",1.5),(None,0.25),("Delete",1),("End",1),("PageDown",1)],
 [("CapsLock",1.75),("A",1),("S",1),("D",1),("F",1),("G",1),("H",1),("J",1),("K",1),("L",1),
  ("Semicolon",1),("Apostrophe",1),("Enter",2.25)],
 [("LeftShift",2.25),("Z",1),("X",1),("C",1),("V",1),("B",1),("N",1),("M",1),("Comma",1),("Dot",1),
  ("Slash",1),("RightShift",2.75),(None,1.25),("Up",1)],
 [("LeftCtrl",1.25),("LeftMeta",1.25),("LeftAlt",1.25),("Space",6.25),("RightAlt",1.25),
  ("RightMeta",1.25),("Menu",1.25),("RightCtrl",1.25),(None,0.25),("Left",1),("Down",1),("Right",1)],
]
```
Note: in the TKL layout the nav cluster (Insert..PageDown, arrows) sits directly
to the right of the main block, behind a 0.25-unit gap. On the full-size board
the nav cluster is a separate 3-wide block and the numpad sits to its right.

## What to build

### 1. Two layout variants, selectable by name
Add a module-level registry:

```python
@dataclass(frozen=True)
class KeyboardLayout:
    name: str                 # "tkl" | "full"
    rows: list[list[tuple]]
    top_row: list[tuple[str, float, float]]
    decor: list[tuple[str, float, float, float, float]]
    round_keys: frozenset[str]

LAYOUTS: dict[str, KeyboardLayout] = {"tkl": ..., "full": ...}
DEFAULT_LAYOUT = "tkl"
```
Move the current TKL values into the `"tkl"` entry unchanged.

### 2. The full-size layout
Build `FULL_ANSI` in the same (name, width) row format:

- Main block: same 6 rows as TKL, same widths, but the nav cluster keys
  (PrintScreen, ScrollLock, Pause, Insert, Home, PageUp, Delete, End, PageDown,
  Up, Down, Left, Right) must NOT appear inside the main rows. Put them in a
  separate block to the right of the main block.
- F-row: Esc, gap, F1..F4, gap 0.5, F5..F8, gap 0.5, F9..F12, then
  PrintScreen, ScrollLock, Pause (these three are part of the F-row on a
  full-size board).
- Nav block: Insert/Home/PageUp, Delete/End/PageDown, then a gap row with Up,
  then Left/Down/Right. Three columns wide.
- Numpad block: NumLock, KPSlash, KPAsterisk, KPMinus in the first row;
  KP7, KP8, KP9, KPPlus next (KPPlus 2 tall); KP4, KP5, KP6 (KPPlus continues);
  KP1, KP2, KP3, KPEnter (KPEnter 2 tall); KP0 (2 wide), KPDot.
  All these names already exist in src/logi_ghub/keys.py. Do not rename them.
- Standard widths: Tab 1.5, CapsLock 1.75, LeftShift 2.25, Backspace 2,
  Enter 2.25, RightShift 2.75, Space 6.25, the six modifiers 1.25.

Because some keys are 2 units tall, the row list alone cannot express them.
Extend the row format minimally: `(name, width)` stays valid and
`(name, width, height)` is also accepted. Do not break existing rows.

### 3. Top strip for the full-size board
The G915 X full-size has, left to right: logo, five G-keys, game-mode button,
brightness, three profile keys (M1/M2/M3), media keys (previous, play/pause,
next, mute), and a volume roller at the far right.

- G-key lighting zone ids come from a reverse-engineered HID++ 0x8081 map that
  was confirmed on this keyboard family: G1..G9 = zone 180..188, one per key.
  The current `SPECIAL_ZONES` dict defines only G1..G5 (180..184). Add
  G6..G9 as 185..188 with the comment:
  `# zone ids from the 0x8081 LED map; confirmed range for G1..G9 = 180..188 —
  # verify the exact ids against the device bitmap before shipping`
- Use `DECOR` for parts that have no lighting zone (logo, game mode, M1/M2/M3,
  roller, brightness) so they are drawn but not clickable.

### 4. Selecting the layout
Change the signature to:

```python
def keycaps(available_zones: list[int] | None = None, layout: str = DEFAULT_LAYOUT) -> list[KeyCap]
```

Rules:
- Keep layout.py free of device logic. It must not inspect device names.
- `gui/keyboard.py`: accept a layout name in the constructor, pass it to
  `layout.keycaps()`, and use `LAYOUTS[name].decor` / `.round_keys` instead of
  the module-level constants. Default to `DEFAULT_LAYOUT`.
- `gui/app.py`: add ONE obvious hook that decides which layout name to pass,
  with a `# TODO:` comment. Do not write the device-matching logic.
- `lightfx.py:90`: pass the layout name through (add the parameter, default
  `DEFAULT_LAYOUT`).

### 5. Tests
Add `tests/test_layout.py` with at least:
- TKL layout produces the same KeyCap list (names + zone ids, in order) as the
  pre-change code path. Snapshot test.
- Full layout contains all of: NumLock, KPSlash, KPAsterisk, KPMinus, KPPlus,
  KPEnter, KP0..KP9, KPDot, and Insert/Delete/Home/End/PageUp/PageDown/arrows.
- Full layout has no overlapping keycaps (pairwise rectangle overlap on x/y/w/h).
- `bounds()` for the full layout is wider relative to height than the TKL one.
- `available_zones` filtering still works for both layouts.

## Definition of done
- `python3 -m pytest -q` passes (66 existing tests + new ones).
- `python3 -m compileall -q src` is clean.
- No behaviour change for the TKL layout.
- A short summary listing every value you left as `TODO(verify)` and why.
