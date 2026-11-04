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


def test_switching_a_profile_says_which_device_and_which_profile():
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    assert "def _announce(self, device_name: str, profile_name: str, device_key: str" in src
    assert 'notify(f"{device_name} — {profile_name}", silent=silent)' in src


def test_the_notification_comes_after_the_profile_applied():
    """A profile that fails to load must not be announced as running."""
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    applied = src.index("session.apply()")
    announced = src.index("self._announce(dev.name, name, dev.key)")
    assert applied < announced


def test_the_first_profile_after_start_is_announced_too():
    """The message used to be tied to dropping an old session, so the first load
    after start was silent and it looked intermittent."""
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    scan = src[src.index("def scan(self)"):src.index("def end(self, key")]
    # The teardown loop must not speak; only a successful start does.
    teardown = scan[:scan.index("for s in self.sessions.values()")]
    assert "_announce" not in teardown
    assert "self._announce(dev.name, name, dev.key)" in scan


def test_window_watching_starts_even_without_a_rules_file():
    """A rule added from the app used to need a service restart."""
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    body = src[src.index("def start_app_watch(self)"):src.index("def shutdown(self)")]
    assert "rules_path().exists()" not in body


def test_the_notification_is_short_lived():
    src = (ROOT / "src" / "logi_ghub" / "notify.py").read_text()
    assert "expire_ms: int = 3000" in src


def test_a_device_runs_one_profile_so_the_picker_is_a_button():
    """A switch implied independent on/off states for a one-of-many choice."""
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    body = src[src.index('title="Profiles on this computer"'):src.index("def set_host")]
    assert "Gtk.Switch" not in body
    assert 'label="Running" if running else "Use"' in body
