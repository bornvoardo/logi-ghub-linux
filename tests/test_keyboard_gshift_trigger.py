"""The G-Shift key on a keyboard holds a second layer open.

A key assigned special:0x0B used to do nothing on a keyboard: KeyMapper logged
"does nothing" and swallowed it. It is now the layer trigger.

Rules:
  * while held, a key the second layer names does the second-layer action
  * a key the second layer does not name keeps its first-layer action
  * the trigger itself types nothing, in either layer
  * releasing it closes the layer
  * escaping the keyboard closes the layer too, or the next profile inherits it
"""

from __future__ import annotations

import pytest

from logi_ghub import keys, keyremap
from logi_ghub.actions import Action


class FakeKeyboard:
    def __init__(self):
        self.sent: list[tuple[int, bool]] = []

    def key(self, code: int, down: bool) -> None:
        self.sent.append((code, down))

    def down_codes(self) -> list[int]:
        return [c for c, d in self.sent if d]

    def clear(self):
        self.sent.clear()


A_KEY = keyremap.key_code("A")
B_KEY = keyremap.key_code("B")
G6 = keyremap.key_code("G6")
ESC = keyremap.key_code("Esc")


def gshift() -> Action:
    return Action("special", function=keyremap.GSHIFT)


def press(mapper, code):
    mapper.handle(code, 1)


def release(mapper, code):
    mapper.handle(code, 0)


@pytest.fixture
def mapper():
    keyboard = FakeKeyboard()
    first = {
        G6: gshift(),
        A_KEY: Action("key", key=0x04),  # A
        B_KEY: Action("key", key=0x05),  # B
    }
    second = {
        A_KEY: Action("key", key=0x29),  # Escape
    }
    m = keyremap.KeyMapper(first, keyboard, gshift_mapping=second)
    return m, keyboard


# -- the trigger ------------------------------------------------------------------


def test_the_trigger_types_nothing(mapper):
    m, keyboard = mapper
    press(m, G6)
    assert keyboard.sent == []


def test_pressing_the_trigger_opens_the_layer(mapper):
    m, _ = mapper
    assert m.gshift is False
    press(m, G6)
    assert m.gshift is True


def test_releasing_the_trigger_closes_the_layer(mapper):
    m, _ = mapper
    press(m, G6)
    release(m, G6)
    assert m.gshift is False


def test_the_trigger_is_remembered_while_held(mapper):
    """Without this, a release could not tell the trigger from an ordinary key."""
    m, _ = mapper
    press(m, G6)
    assert m.trigger == G6
    release(m, G6)
    assert m.trigger is None


def test_the_trigger_does_not_leak_its_code(mapper):
    """It must not be pressed on the virtual keyboard: F18 is a real key."""
    m, keyboard = mapper
    press(m, G6)
    release(m, G6)
    assert G6 not in keyboard.down_codes()


# -- the second layer -------------------------------------------------------------


def test_a_named_key_uses_the_second_layer(mapper):
    m, keyboard = mapper
    press(m, G6)
    press(m, A_KEY)
    # Actions carry HID usage; the virtual keyboard takes evdev codes.
    assert ESC in keyboard.down_codes()
    assert keyremap.key_code("A") not in keyboard.down_codes()


def test_an_unnamed_key_keeps_its_first_layer_action(mapper):
    """A half-filled layer must not disable every other key."""
    m, keyboard = mapper
    press(m, G6)
    press(m, B_KEY)
    assert keyremap.key_code("B") in keyboard.down_codes()


def test_after_release_the_first_layer_answers_again(mapper):
    m, keyboard = mapper
    press(m, G6)
    release(m, G6)
    keyboard.clear()
    press(m, A_KEY)
    assert keyremap.key_code("A") in keyboard.down_codes()


def test_the_first_layer_is_used_when_no_second_layer_exists():
    keyboard = FakeKeyboard()
    m = keyremap.KeyMapper({A_KEY: Action("key", key=0x04)}, keyboard)
    press(m, A_KEY)
    assert keyremap.key_code("A") in keyboard.down_codes()


def test_the_layer_reports_itself_once_per_change():
    """The tray redraws on this, so a repeated call must not fire twice."""
    seen = []
    m = keyremap.KeyMapper({G6: gshift()}, FakeKeyboard(), on_layer=seen.append)
    press(m, G6)
    press(m, G6)  # auto-repeat is filtered, but a duplicate down must not refire
    release(m, G6)
    release(m, G6)
    assert seen == [True, False]


def test_a_release_without_a_press_does_not_open_the_layer(mapper):
    m, _ = mapper
    release(m, G6)
    assert m.gshift is False


# -- the layer must not outlive the keyboard grab ---------------------------------


def test_escaping_the_keyboard_closes_the_layer(mapper):
    """Otherwise the next profile starts with a layer nobody is holding open."""
    m, _ = mapper
    press(m, G6)
    assert m.gshift is True
    m.release_all()
    assert m.gshift is False
    assert m.trigger is None


def test_closing_a_layer_that_is_already_closed_says_nothing():
    seen = []
    m = keyremap.KeyMapper({}, FakeKeyboard(), on_layer=seen.append)
    m.set_layer(False)
    assert seen == []
