"""Renaming a profile has to carry the name to everything that refers to it."""

from __future__ import annotations

import json

import pytest

from logi_ghub import appwatch, profiles

DEV = "046d:c359"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = profiles.Profile(name="konsole", device=DEV)
    p.key_actions["G1"] = profiles.Action("key")
    profiles.save_profile(p)
    return tmp_path


def test_a_rename_keeps_the_contents(store):
    profiles.rename_profile(DEV, "konsole", "Terminal")
    loaded = profiles.load_profile(DEV, "Terminal")
    assert loaded.name == "Terminal"
    assert "G1" in loaded.key_actions


def test_the_old_file_is_gone(store):
    profiles.rename_profile(DEV, "konsole", "Terminal")
    # "Default" is created by list_profiles and is not this test's subject.
    names = [p.name for p in profiles.list_profiles(DEV) if p.name != profiles.DEFAULT_NAME]
    assert names == ["Terminal"]


def test_the_active_profile_follows_the_new_name(store):
    """Otherwise the device would keep pointing at a profile that no longer exists."""
    profiles.set_active(DEV, "konsole")
    profiles.rename_profile(DEV, "konsole", "Terminal")
    assert profiles.get_active()[DEV] == "Terminal"


def test_a_window_rule_follows_the_new_name(store):
    """A rule naming the old profile would stop matching and silently do nothing."""
    rules = appwatch.AppRules()
    rules.add("org.kde.konsole", "konsole", DEV)
    rules.save()
    profiles.rename_profile(DEV, "konsole", "Terminal")
    assert appwatch.AppRules.load().rules[0].profile == "Terminal"


def test_a_rule_for_another_device_is_left_alone(store):
    rules = appwatch.AppRules()
    rules.add("org.kde.konsole", "konsole", "046d:409f")
    rules.save()
    profiles.rename_profile(DEV, "konsole", "Terminal")
    assert appwatch.AppRules.load().rules[0].profile == "konsole"


def test_an_existing_name_is_refused(store):
    profiles.save_profile(profiles.Profile(name="baska", device=DEV))
    with pytest.raises(ValueError, match="already exists"):
        profiles.rename_profile(DEV, "konsole", "baska")
    # Nothing changed.
    assert sorted(p.name for p in profiles.list_profiles(DEV) if p.name != profiles.DEFAULT_NAME) == ["baska", "konsole"]


def test_renaming_to_the_same_name_is_a_no_op(store):
    profiles.rename_profile(DEV, "konsole", "konsole")
    assert [p.name for p in profiles.list_profiles(DEV) if p.name != profiles.DEFAULT_NAME] == ["konsole"]


def test_the_name_is_written_inside_the_file(store):
    """The file name and the stored name must agree, or loading goes wrong."""
    path = profiles.rename_profile(DEV, "konsole", "Terminal")
    assert path.name == "Terminal.json"
    assert json.loads(path.read_text())["name"] == "Terminal"


def test_a_rename_with_no_active_profile_does_not_invent_one(store):
    profiles.rename_profile(DEV, "konsole", "Terminal")
    assert DEV not in profiles.get_active()
