"""Falling back to the default must not name the window that ended a rule.

The label is what the profiles page prints as "chosen for ...". When no rule names a
device the app falls back to the default profile, and the label used to be the class
of the window that had just lost focus, so the default row read "chosen for
com.nousresearch.hermes" — an application that had chosen nothing.
"""

from __future__ import annotations

import pytest

from logi_ghub import appwatch, profiles

DEV = "046d:c359"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profiles.save_profile(profiles.Profile(name="Oyun", device=DEV))
    profiles.save_profile(profiles.Profile(name="Default", device=DEV))
    monkeypatch.setattr(appwatch, "notify_switch", lambda *a, **k: None, raising=False)
    return tmp_path


def _rules(*, with_rule: bool) -> appwatch.AppRules:
    rules = appwatch.AppRules()
    rules.enabled = True
    rules.defaults[DEV] = profiles.DEFAULT_NAME
    if with_rule:
        rules.add("oyun", "Oyun", DEV, label="Oyun")
    return rules


def _apply(rules, app_id: str) -> dict[str, str]:
    # No D-Bus and no notification daemon in a unit test: only the label matters.
    watch = appwatch.Watcher(rules=rules, on_focus=lambda *_: None)
    watch._apply(app_id, "")
    return appwatch.load_last_switch()


def test_a_rule_names_itself(store):
    labels = _apply(_rules(with_rule=True), "oyun")
    assert labels.get(DEV) == "Oyun"


def test_the_default_names_nothing(store):
    labels = _apply(_rules(with_rule=False), "com.nousresearch.hermes")
    assert labels.get(DEV, "") == ""


def test_the_default_after_a_rule_clears_the_label(store):
    """Leaving the game for the desktop must not keep saying "chosen for the game"."""
    rules = _rules(with_rule=True)
    _apply(rules, "oyun")
    labels = _apply(rules, "org.kde.plasma.desktop")
    assert labels.get(DEV, "") == ""
