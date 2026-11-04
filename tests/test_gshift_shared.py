"""G-Shift belongs to the machine, not to one device.

The keyboard's trigger opens the layer; every device's assignments must answer to
it, because the point of the feature is "hold this key and the other half of the
desk changes". Before this, the flag lived on one session, so a keyboard key only
ever changed the keyboard.

The layer is a single object shared by all sessions:
  * read by the mouse half, so its buttons follow a keyboard trigger
  * written by whoever holds the trigger, keyboard or mouse
  * locked, because the keyboard reader and the mouse listener are different threads
"""

from __future__ import annotations

import threading

from logi_ghub import appwatch, keyremap
from logi_ghub.actions import Action
from logi_ghub.daemon import Session


class FakeSpy:
    """Stands in for the button spy: records what remapping was installed."""

    count = 4

    def __init__(self):
        self.table: list[int] | None = None
        self.started = False

    def set_remapping(self, table):
        self.table = list(table)

    def start(self):
        self.started = True

    def stop(self):
        pass

    def identity(self):
        return [0] * self.count


def _session(gshift_buttons=None, buttons=None, shared=None) -> tuple[Session, FakeSpy]:
    from logi_ghub import profiles

    spy = FakeSpy()
    dev = type("Dev", (), {})()
    dev.key = "046d:409f"
    dev.name = "G502 X"
    dev.online = True
    dev.onboard = None
    dev.button_spy = spy
    dev.binding_count = lambda: 4
    dev.dpi = None
    dev.rgb = None
    dev.info = type("I", (), {"path": "fake:1", "behind_receiver": False})()

    p = profiles.Profile(name="Work", device="046d:409f")
    p.buttons = buttons or {0: Action("key", key=0x04)}
    p.gshift_buttons = gshift_buttons or {0: Action("key", key=0x29)}

    import queue

    s = Session(dev, p, queue.Queue(), None, None, gshift=shared)
    return s, spy


# -- the flag is shared ---------------------------------------------------------


def test_two_sessions_see_the_same_layer():
    from logi_ghub.daemon import GShift

    shared = GShift()
    a, _ = _session(shared=shared)
    b, _ = _session(shared=shared)
    a.set_gshift(True)
    assert b.gshift is True


def test_closing_the_layer_closes_it_for_everyone():
    from logi_ghub.daemon import GShift

    shared = GShift()
    a, _ = _session(shared=shared)
    b, _ = _session(shared=shared)
    a.set_gshift(True)
    b.set_gshift(False)
    assert a.gshift is False


def test_the_mouse_answers_a_keyboard_trigger():
    """The whole point: a keyboard key changes the mouse's buttons."""
    s, _ = _session()
    assert s.action_for(0).key == 0x04  # first layer: A
    s.set_gshift(True)
    assert s.action_for(0).key == 0x29  # second layer: Esc


def test_the_layer_reaches_the_spy():
    """action_for changing is not enough: the device also has to be told."""
    s, spy = _session()
    s.set_gshift(True)
    s.apply_remapping()
    assert spy.table is not None


def test_a_session_with_no_spy_is_not_an_error():
    """Keyboards have no button spy; the layer still has to work for them."""
    s, _ = _session()
    s.spy = None
    s.set_gshift(True)  # must not raise
    s.apply_remapping()


# -- the keyboard side still works -----------------------------------------------


def test_the_trigger_constant_is_still_the_one_the_keyboard_uses():
    assert keyremap.GSHIFT == 0x0B
