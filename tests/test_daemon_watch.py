"""The daemon must notice a saved profile on its next loop, not ten seconds later."""

from __future__ import annotations

import os

import pytest

from logi_ghub import daemon, profiles


@pytest.fixture()
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def _touch(path, ns):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    os.utime(path, ns=(ns, ns))


def test_a_newer_profile_changes_the_watched_value(config):
    _touch(profiles._active_path(), 1_000)
    path = profiles.profile_dir("046d:c359") / "test.json"
    _touch(path, 1_000)
    d = daemon.Daemon(fake=True)
    before = d._watched_mtime({"046d:c359": "test"})
    _touch(path, 2_000_000_000)
    assert d._watched_mtime({"046d:c359": "test"}) != before


def test_two_saves_in_one_second_are_distinguishable(config):
    """Whole-second mtimes hid a Save that happened right after the previous one."""
    _touch(profiles._active_path(), 1_000)
    path = profiles.profile_dir("046d:c359") / "test.json"
    d = daemon.Daemon(fake=True)
    _touch(path, 5_000_000_000)
    first = d._watched_mtime({"046d:c359": "test"})
    _touch(path, 5_000_000_500)  # half a second later
    assert d._watched_mtime({"046d:c359": "test"}) != first


def test_no_active_profiles_still_works(config):
    _touch(profiles._active_path(), 1_000)
    assert daemon.Daemon(fake=True)._watched_mtime({}) == 1_000


def test_a_deleted_profile_does_not_raise(config):
    _touch(profiles._active_path(), 1_000)
    d = daemon.Daemon(fake=True)
    assert d._watched_mtime({"046d:c359": "gone"}) == 1_000
