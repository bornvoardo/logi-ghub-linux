"""A rule can stay quiet, and no message is kept in the notification history."""

from __future__ import annotations

import json
from pathlib import Path

from logi_ghub import appwatch

ROOT = Path(__file__).resolve().parents[1]
DEV = "046d:c359"


def _rules(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return appwatch.AppRules()


# -- the rule carries the choice ------------------------------------------------


def test_a_new_rule_notifies_and_is_silent(tmp_path, monkeypatch):
    rules = _rules(tmp_path, monkeypatch)
    rule = rules.add("org.kde.konsole", "konsole", DEV)
    assert rule.notify is True
    assert rule.silent is True


def test_a_rule_can_turn_its_notification_off(tmp_path, monkeypatch):
    rules = _rules(tmp_path, monkeypatch)
    rule = rules.add("org.kde.konsole", "konsole", DEV, notify=False)
    assert rule.notify is False
    # Silent is about sound, so it is independent of whether anything is shown.
    assert rule.silent is True


def test_a_rule_can_be_loud(tmp_path, monkeypatch):
    rules = _rules(tmp_path, monkeypatch)
    rule = rules.add("org.kde.konsole", "konsole", DEV, silent=False)
    assert rule.notify is True
    assert rule.silent is False


def test_both_choices_survive_a_reload(tmp_path, monkeypatch):
    rules = _rules(tmp_path, monkeypatch)
    rules.add("org.kde.konsole", "konsole", DEV, notify=False, silent=False)
    rules.save()
    back = appwatch.AppRules.load().rules[0]
    assert (back.notify, back.silent) == (False, False)


def test_a_rule_file_without_the_keys_behaves_like_the_default(tmp_path, monkeypatch):
    """Files written before this change have no notify/silent keys. Reading them as
    False would silence every existing rule."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = appwatch.rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "enabled": True,
        "rules": [{"match": "firefox", "profile": "web", "device": DEV}],
        "defaults": {},
    }))
    rule = appwatch.AppRules.load().rules[0]
    assert rule.notify is True
    assert rule.silent is True


def test_re_adding_a_rule_takes_the_new_choices(tmp_path, monkeypatch):
    """Editing a rule goes through add(), so the switches must be carried with it."""
    rules = _rules(tmp_path, monkeypatch)
    rules.add("firefox", "web", DEV, notify=True)
    rules.add("firefox", "web", DEV, notify=False)
    assert len(rules.rules) == 1
    assert rules.rules[0].notify is False


# -- the daemon reads what the watcher wrote -----------------------------------


def test_the_choice_is_recorded_with_the_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    appwatch.save_last_switch({DEV: "Konsole"}, {DEV: False}, {DEV: False})
    data = json.loads(appwatch.state_path().read_text())
    assert data["by_app"] == {DEV: "Konsole"}
    assert data["notify"] == {DEV: False}
    assert data["silent"] == {DEV: False}


def test_the_daemon_learns_to_stay_quiet(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    appwatch.save_last_switch({DEV: "Konsole"}, {DEV: False}, {DEV: True})
    show, silent = appwatch.load_notify_choice(DEV)
    assert show is False
    assert silent is True


def test_a_device_with_no_record_is_announced_normally(tmp_path, monkeypatch):
    """The first start, and a switch back to the default, have no rule."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert appwatch.load_notify_choice(DEV) == (True, True)


def test_a_missing_state_file_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nowhere"))
    assert appwatch.load_notify_choice(DEV) == (True, True)


def test_the_label_is_still_written_next_to_the_choice(tmp_path, monkeypatch):
    """The app reads by_app for the running row; adding two keys must not drop it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    appwatch.save_last_switch({DEV: "Konsole"}, {DEV: True}, {DEV: True})
    assert appwatch.load_last_switch() == {DEV: "Konsole"}


# -- nothing is kept in the history --------------------------------------------


def test_every_message_is_transient():
    """KDE reads 'transient' as TransientRole, "not kept in history". Without it a
    switch per window piles up in the notification list."""
    src = (ROOT / "src" / "logi_ghub" / "notify.py").read_text()
    body = src[src.index("hints = {"):src.index("if silent:")]
    assert '"transient": GLib.Variant("b", True)' in body


def test_the_message_names_the_desktop_entry():
    """KDE only stores a notification it can tie to an app, and only lets the user
    configure one it can name. The value must match the installed .desktop file."""
    entry = (ROOT / "src" / "logi_ghub" / "notify.py").read_text()
    desktop = next((ROOT / "data").glob("*.desktop")).name.removesuffix(".desktop")
    assert f'DESKTOP_ENTRY = "{desktop}"' in entry


def test_silence_is_a_hint_not_a_separate_call():
    src = (ROOT / "src" / "logi_ghub" / "notify.py").read_text()
    assert '"suppress-sound"' in src
    assert "if silent:" in src


def test_the_default_is_silent():
    src = (ROOT / "src" / "logi_ghub" / "notify.py").read_text()
    assert "silent: bool = False" in src  # the call site decides, see below
    daemon = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    assert "load_notify_choice(device_key) if device_key else (True, True)" in daemon


def test_the_daemon_skips_the_call_when_the_rule_says_so():
    """Returning early matters: the rule asked for no message, not an empty one."""
    src = (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()
    body = src[src.index("def _announce"):src.index("def start_app_watch")]
    assert "if not show:" in body
    assert "return" in body[body.index("if not show:"):]


# -- the app offers both switches ----------------------------------------------


def test_the_rule_dialog_has_a_notifications_group_at_the_end():
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    body = src[src.index("def _add_app_rule"):src.index("def build_profiles")]
    assert 'title="Notifications"' in body
    # Last group in the dialog: nothing is appended to the box after it.
    last = body.rindex("box.append(")
    assert "ngroup" in body[last:last + 40]


def test_both_switches_start_on():
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    body = src[src.index("def _add_app_rule"):src.index("def build_profiles")]
    assert "notify_row.set_active(rule.notify if editing else True)" in body
    assert "silent_row.set_active(rule.silent if editing else True)" in body


def test_silence_is_disabled_when_nothing_is_shown():
    """A silent switch on a rule that says nothing is a setting with no effect."""
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    body = src[src.index("def _add_app_rule"):src.index("def build_profiles")]
    assert 'bind_property("active", silent_row, "sensitive"' in body


def test_the_dialog_saves_both_choices():
    src = (ROOT / "src" / "logi_ghub" / "gui" / "app.py").read_text()
    body = src[src.index("def _add_app_rule"):src.index("def build_profiles")]
    assert "notify=notify_row.get_active()" in body
    assert "silent=silent_row.get_active()" in body


# -- the command line can set them too -----------------------------------------


def test_the_cli_can_turn_a_rule_off():
    src = (ROOT / "src" / "logi_ghub" / "cli.py").read_text()
    assert '"--no-notify", dest="notify", action="store_false"' in src
    assert '"--loud", dest="silent", action="store_false"' in src
