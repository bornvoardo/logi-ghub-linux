"""The second layer belongs to the machine, in both directions.

A keyboard trigger reached the mouse's buttons, but the mouse's own G-Shift button
left the keyboard's keys alone: the key remapper keeps its own layer flag, which
nothing outside the key reader could move. These tests pin that link.

The real KeyRemapper is used rather than a stand-in, because the point is that the
method exists on it and touches the mapper without calling back.
"""

from __future__ import annotations

import inspect

from logi_ghub import keyremap


def _bare_remapper():
    """A KeyRemapper with only what the layer method touches.

    __init__ opens input devices, which this machine does not have, so the object is
    built without it.
    """
    r = keyremap.KeyRemapper.__new__(keyremap.KeyRemapper)
    r.name = "G915 X"
    class Sink:
        """A keyboard/pointer that records instead of typing."""
        def key(self, code, down):
            pass
        def wheel(self, clicks, horizontal=False):
            pass

    r.mapper = keyremap.KeyMapper({}, Sink(), pointer=Sink())
    r.on_layer = None
    return r


def test_another_device_can_open_the_keyboard_layer():
    r = _bare_remapper()
    r.set_layer_from_outside(True)
    assert r.mapper.gshift is True


def test_another_device_can_close_it():
    r = _bare_remapper()
    r.mapper.gshift = True
    r.set_layer_from_outside(False)
    assert r.mapper.gshift is False


def test_the_same_value_is_left_alone():
    """The layer is reported once; a second open must not echo back."""
    r = _bare_remapper()
    r.mapper.gshift = True
    r.set_layer_from_outside(True)
    assert r.mapper.gshift is True


def test_a_remapper_without_a_mapper_does_not_crash():
    """Before the reader thread starts there is no mapper; the trigger must not fail."""
    r = _bare_remapper()
    r.mapper = None
    r.set_layer_from_outside(True)  # must not raise


def test_the_method_never_calls_back():
    """Echoing back would make the two devices re-trigger each other."""
    src = inspect.getsource(keyremap.KeyRemapper.set_layer_from_outside)
    assert "self.on_layer(" not in src
    assert "self.set_layer(" not in src


def test_the_layer_chooses_the_second_mapping():
    """The flag the method sets is the one action_for reads."""
    from logi_ghub.actions import Action

    r = _bare_remapper()
    class Sink:
        def key(self, code, down):
            pass
        def wheel(self, clicks, horizontal=False):
            pass

    r.mapper = keyremap.KeyMapper({30: Action("key", key=0x04)}, Sink(), pointer=Sink(),
                                  gshift_mapping={30: Action("key", key=0x29)})
    assert r.mapper.action_for(30).key == 0x04
    r.set_layer_from_outside(True)
    assert r.mapper.action_for(30).key == 0x29
