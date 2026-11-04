"""Rule labels, the state the app reads, and the window filter."""

from __future__ import annotations

import json

from logi_ghub import appwatch, cli

DEV = "046d:c359"


class Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# -- labels -------------------------------------------------------------------

def test_a_rule_without_a_label_shows_the_window_class():
    rule = appwatch.Rule("org.kde.konsole", "konsole", DEV)
    assert rule.display_name("org.kde.konsole") == "org.kde.konsole"


def test_a_rule_with_a_label_shows_the_label():
    rule = appwatch.Rule("org.kde.konsole", "konsole", DEV, label="Terminal")
    assert rule.display_name("org.kde.konsole") == "Terminal"


def test_an_empty_label_falls_back_to_the_class():
    """Clearing the field must mean "no name", not an empty line in the app."""
    rule = appwatch.Rule("org.kde.konsole", "konsole", DEV, label="   ")
    assert rule.display_name("org.kde.konsole") == "org.kde.konsole"


def test_the_label_survives_a_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rules = appwatch.AppRules()
    rules.add("org.kde.konsole", "konsole", DEV, label="Terminal")
    rules.save()
    loaded = appwatch.AppRules.load()
    assert loaded.rules[0].label == "Terminal"
    assert loaded.rules[0].display_name("org.kde.konsole") == "Terminal"


def test_a_rule_without_a_label_loads_as_none(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "logi-ghub-linux" / "app-profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"rules": [{"match": "firefox", "profile": "web",
                                           "device": DEV, "title": None}]}))
    assert appwatch.AppRules.load().rules[0].label is None


def test_rule_for_returns_the_rule_not_just_the_profile():
    """The label lives on the rule, so the applier needs the rule itself."""
    rules = appwatch.AppRules()
    rules.add("org.kde.konsole", "konsole", DEV, label="Terminal")
    rules.defaults[DEV] = "g915x-default"
    rule = rules.rule_for(DEV, "org.kde.konsole", "~ : zsh")
    assert rule is not None and rule.profile == "konsole"
    assert rules.rule_for(DEV, "firefox", "Mail") is None


def test_the_default_profile_still_answers_when_no_rule_matches():
    rules = appwatch.AppRules()
    rules.add("org.kde.konsole", "konsole", DEV)
    rules.defaults[DEV] = "g915x-default"
    assert rules.profile_for(DEV, "firefox", "") == "g915x-default"


def test_the_cli_shows_the_label_and_the_class(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(cli.profiles, "list_profiles", lambda key: [type("P", (), {"name": "konsole"})()])
    cli.cmd_apps(Args(apps_cmd="add", match="org.kde.konsole", profile="konsole",
                      device_model=DEV, title=None, label="Terminal"))
    cli.cmd_apps(Args(apps_cmd="list"))
    out = capsys.readouterr().out
    assert "Terminal" in out
    assert "org.kde.konsole" in out


# -- the state file the app reads ---------------------------------------------

def test_the_last_switch_is_saved_for_the_app(tmp_path, monkeypatch):
    """The app cannot see a window change on Wayland, so the daemon records it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    appwatch.save_last_switch({DEV: "Terminal"})
    assert appwatch.load_last_switch() == {DEV: "Terminal"}


def test_no_state_file_reads_as_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert appwatch.load_last_switch() == {}


def test_a_broken_state_file_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "logi-ghub-linux" / "app-state.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert appwatch.load_last_switch() == {}


def test_applying_a_switch_records_the_label(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rules = appwatch.AppRules()
    rules.add("org.kde.konsole", "konsole", DEV, label="Terminal")

    switched = {}

    class FakeProfiles:
        @staticmethod
        def get_active():
            return {}

        @staticmethod
        def set_active(device, name):
            switched[device] = name

        @staticmethod
        def list_profiles(device):
            return [type("P", (), {"name": "konsole"})()]

    monkeypatch.setattr(appwatch, "profile_exists", lambda d, n: True)
    import logi_ghub.profiles as real_profiles
    monkeypatch.setattr(real_profiles, "get_active", FakeProfiles.get_active)
    monkeypatch.setattr(real_profiles, "set_active", FakeProfiles.set_active)

    appwatch.Watcher(rules).focus_changed("org.kde.konsole", "~ : zsh", "org.kde.konsole")
    assert switched == {DEV: "konsole"}
    assert appwatch.load_last_switch() == {DEV: "Terminal"}


# -- the window filter --------------------------------------------------------

def test_the_filter_matches_the_class_and_the_title():
    """The picker filters in the app; this is the matching rule it uses."""
    def keeps(needle, app_id, title):
        haystack = (app_id + " " + title).lower()
        return not needle or needle.strip().lower() in haystack

    assert keeps("", "org.kde.konsole", "~ : zsh")
    assert keeps("KONS", "org.kde.konsole", "~ : zsh")
    assert keeps("zsh", "org.kde.konsole", "~ : zsh")
    assert not keeps("firefox", "org.kde.konsole", "~ : zsh")
