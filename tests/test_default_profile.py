"""Every device has a default profile, and it cannot be lost.

A device without a fallback had to be offered "No default" on the rules page, which
read like a setting rather than the gap it was. The default profile is now created
when missing, listed first, and protected from delete and rename.
"""

from __future__ import annotations

import pytest

from logi_ghub import profiles

DEV = "046d:c359"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def test_a_device_with_no_profiles_gets_a_default(store):
    """Listing is what repairs it, so the very first visit already shows a default."""
    names = [p.name for p in profiles.list_profiles(DEV)]
    assert names == [profiles.DEFAULT_NAME]


def test_the_default_comes_first(store):
    profiles.save_profile(profiles.Profile(name="aaa", device=DEV))
    profiles.save_profile(profiles.Profile(name="zzz", device=DEV))
    names = [p.name for p in profiles.list_profiles(DEV)]
    assert names[0] == profiles.DEFAULT_NAME
    assert names[1:] == ["aaa", "zzz"]


def test_asking_twice_creates_it_once(store):
    first = profiles.ensure_default(DEV)
    second = profiles.ensure_default(DEV)
    assert first.name == second.name
    assert len(list(profiles.profile_dir(DEV).glob("*.json"))) == 1


def test_a_broken_default_file_is_replaced(store):
    path = profiles.profile_dir(DEV) / "Default.json"
    path.write_text("{ not json")
    created = profiles.ensure_default(DEV)
    assert created.name == profiles.DEFAULT_NAME
    assert profiles.load_profile(DEV, profiles.DEFAULT_NAME).name == profiles.DEFAULT_NAME


def test_the_default_cannot_be_deleted(store):
    profiles.list_profiles(DEV)
    with pytest.raises(ValueError, match="cannot be deleted"):
        profiles.delete_profile(DEV, profiles.DEFAULT_NAME)
    assert profiles.load_profile(DEV, profiles.DEFAULT_NAME).name == profiles.DEFAULT_NAME


def test_the_default_cannot_be_renamed(store):
    profiles.list_profiles(DEV)
    with pytest.raises(ValueError, match="cannot be renamed"):
        profiles.rename_profile(DEV, profiles.DEFAULT_NAME, "Baska")


def test_nothing_else_can_take_the_default_name(store):
    """A second profile called Default would make the protected one ambiguous."""
    profiles.list_profiles(DEV)
    profiles.save_profile(profiles.Profile(name="konsole", device=DEV))
    with pytest.raises(ValueError, match="reserved"):
        profiles.rename_profile(DEV, "konsole", profiles.DEFAULT_NAME)


def test_an_ordinary_profile_still_deletes(store):
    profiles.save_profile(profiles.Profile(name="konsole", device=DEV))
    profiles.delete_profile(DEV, "konsole")
    names = [p.name for p in profiles.list_profiles(DEV)]
    assert "konsole" not in names


def test_the_flag_matches_the_name():
    assert profiles.is_protected(profiles.DEFAULT_NAME)
    assert not profiles.is_protected("konsole")
