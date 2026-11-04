"""The second keyboard layer: a profile can carry G-Shift key assignments.

The keyboard's own layer is a plain dict, the same shape as the mouse's
gshift_buttons. What matters here is that it survives a save/load round trip and
that profiles written before it existed still open.
"""

from __future__ import annotations

import json

from logi_ghub import profiles
from logi_ghub.actions import Action

DEV = "046d:c359"


def test_a_new_profile_has_an_empty_layer():
    p = profiles.Profile(name="Work", device=DEV)
    assert p.gshift_key_actions == {}


def test_the_layer_survives_a_round_trip():
    p = profiles.Profile(name="Work", device=DEV)
    p.gshift_key_actions["A"] = Action("key", key=0x29)  # Escape
    p.key_actions["A"] = Action("key", key=0x04)  # A
    back = profiles.Profile.from_dict(json.loads(json.dumps(p.to_dict())))
    assert back.gshift_key_actions["A"].key == 0x29
    # The first layer is untouched by the second.
    assert back.key_actions["A"].key == 0x04


def test_the_two_layers_are_separate_dictionaries(tmp_path, monkeypatch):
    """Sharing one dict would make the second layer overwrite the first."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = profiles.Profile(name="Work", device=DEV)
    p.key_actions["A"] = Action("key", key=0x04)
    p.gshift_key_actions["A"] = Action("key", key=0x29)
    profiles.save_profile(p)
    back = profiles.load_profile(DEV, "Work")
    assert back.key_actions["A"].key == 0x04
    assert back.gshift_key_actions["A"].key == 0x29


def test_a_profile_written_before_the_layer_still_opens(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = profiles.profile_dir(DEV)
    path.mkdir(parents=True, exist_ok=True)
    (path / "Old.json").write_text(json.dumps({
        "name": "Old", "device": DEV,
        "key_actions": {"A": {"kind": "key", "key": 4}},
    }))
    back = profiles.load_profile(DEV, "Old")
    assert back.gshift_key_actions == {}
    assert back.key_actions["A"].key == 0x04


def test_an_empty_layer_is_not_written_as_null(tmp_path, monkeypatch):
    """A null would fail to load; an empty object is the right shape."""
    p = profiles.Profile(name="Work", device=DEV)
    assert p.to_dict()["gshift_key_actions"] == {}


def test_assigning_one_layer_leaves_the_other_empty():
    p = profiles.Profile(name="Work", device=DEV)
    p.gshift_key_actions["B"] = Action("key", key=0x05)
    assert p.key_actions == {}
