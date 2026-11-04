"""Editing a window rule, and the notification that says which profile is running."""

from __future__ import annotations

import json

from logi_ghub import appwatch, cli

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _rules_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "logi-ghub-linux" / "app-profiles.json"


def test_editing_a_rule_replaces_the_pattern_and_the_profile(tmp_path, monkeypatch):
    """The dialog drops the old rule before adding the new one."""
    path = _rules_file(tmp_path, monkeypatch)
    rules = appwatch.AppRules()
    rules.add("firefox", "web", "046d:c359")
    rules.save()
    rules.remove("firefox", "046d:c359")
    rules.add("firefox*", "tarayici", "046d:c359")
    rules.save()
    saved = json.loads(path.read_text())
    assert [(r["match"], r["profile"]) for r in saved["rules"]] == [("firefox*", "tarayici")]


def test_the_change_dialog_offers_the_current_values():
    """A blank dialog for an edit would silently reset the profile."""
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    assert "match.set_text(rule.match)" in src
    assert "picker.set_selected(names.index(rule.profile))" in src
    assert '"Save" if editing else "Add"' in src


def test_a_rule_row_can_be_activated_to_edit_it():
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    assert 'row.connect("activated", lambda _r, ru=rule: self._add_app_rule(names, ru))' in src


def test_switching_a_profile_says_so():
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    assert "def _announce(self, profile_name" in src
    assert "notify(profile_name)" in src


def test_the_notification_is_short_lived_and_names_the_profile():
    """It is a passing message, not something to dismiss."""
    from logi_ghub import notify as notify_mod

    src = (ROOT / "src" / "logi_ghub" / "notify.py").read_text()
    assert "expire_ms: int = 3000" in src
    assert notify_mod.APP_NAME


def test_unloading_a_profile_says_nothing():
    """Turning the profile off is not a switch to another profile."""
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    assert "if active.get(key) not in (None, s.profile.name):" in src
