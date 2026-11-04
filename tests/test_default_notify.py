"""The default profile needs its own notification answers.

The default is not a rule: there is no row for it in the rules list, so it had
nowhere to turn notifications off or on, and a switch back to it always announced
itself. Each device now carries the two answers itself.
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
    return tmp_path


def _rules(*, with_rule: bool) -> appwatch.AppRules:
    rules = appwatch.AppRules()
    rules.enabled = True
    rules.defaults[DEV] = profiles.DEFAULT_NAME
    if with_rule:
        rules.add("oyun", "Oyun", DEV, label="Oyun", notify=False, silent=False)
    return rules


def _switch(rules, app_id: str) -> tuple[bool, bool]:
    watch = appwatch.Watcher(rules=rules, on_focus=lambda *_: None)
    watch._apply(app_id, "")
    return appwatch.load_notify_choice(DEV)


def test_the_default_is_announced_by_default(store):
    rules = _rules(with_rule=False)
    rules.default_notify[DEV] = True
    rules.default_silent[DEV] = True
    rules.save()
    assert appwatch.AppRules.load().default_notify[DEV] is True


def test_the_default_can_be_quietened(store):
    rules = _rules(with_rule=False)
    rules.default_notify[DEV] = False
    rules.save()
    assert appwatch.AppRules.load().default_notify[DEV] is False


def test_the_default_keeps_its_own_answers_after_a_rule(store):
    """A rule's settings must not leak into the switch back to the default."""
    rules = _rules(with_rule=True)
    rules.default_notify[DEV] = False
    rules.default_silent[DEV] = True
    assert _switch(rules, "org.kde.plasma.desktop") == (False, True)


def test_a_rule_still_uses_its_own_answers(store):
    rules = _rules(with_rule=True)
    rules.default_notify[DEV] = True
    assert _switch(rules, "oyun") == (False, False)


def test_the_answers_survive_a_round_trip(store):
    rules = _rules(with_rule=False)
    rules.default_notify[DEV] = False
    rules.default_silent[DEV] = False
    rules.save()
    again = appwatch.AppRules.load()
    assert again.default_notify[DEV] is False
    assert again.default_silent[DEV] is False


def test_a_file_without_the_keys_still_loads(store):
    rules = _rules(with_rule=False)
    rules.save()
    again = appwatch.AppRules.load()
    assert again.default_notify == {}
    assert again.default_silent == {}
