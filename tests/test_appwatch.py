"""Application profiles: rules, window classes and the switch decision."""

from __future__ import annotations

import json

import pytest

from logi_ghub import appwatch


@pytest.fixture()
def rules_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "logi-ghub-linux" / "app-profiles.json"


class TestRules:
    def test_a_pattern_matches_the_window_class(self):
        rule = appwatch.Rule("steam_app_*", "oyun")
        assert rule.matches("steam_app_1234", "")
        assert not rule.matches("firefox", "")

    def test_matching_ignores_case(self):
        assert appwatch.Rule("Firefox", "web").matches("firefox", "")

    def test_a_title_narrows_the_match_only_when_given(self):
        plain = appwatch.Rule("firefox", "web")
        assert plain.matches("firefox", "Mail")  # no title: the caption does not matter
        narrowed = appwatch.Rule("firefox", "web", title="mail")
        assert not narrowed.matches("firefox", "Calendar")
        assert narrowed.matches("firefox", "Mail — inbox")

    def test_a_device_rule_only_answers_for_that_device(self):
        rules = appwatch.AppRules([appwatch.Rule("firefox", "web", device="046d:409f")])
        assert rules.profile_for("046d:409f", "firefox", "") == "web"
        assert rules.profile_for("046d:c359", "firefox", "") is None

    def test_a_rule_without_a_device_answers_for_every_device(self):
        rules = appwatch.AppRules([appwatch.Rule("firefox", "web")])
        assert rules.profile_for("046d:c359", "firefox", "") == "web"
        assert rules.profile_for("046d:409f", "firefox", "") == "web"

    def test_the_first_matching_rule_wins(self):
        rules = appwatch.AppRules([
            appwatch.Rule("steam_app_*", "oyun"),
            appwatch.Rule("*", "genel"),
        ])
        assert rules.profile_for("x", "steam_app_9", "") == "oyun"
        assert rules.profile_for("x", "firefox", "") == "genel"

    def test_the_default_applies_when_no_rule_matches(self):
        rules = appwatch.AppRules([appwatch.Rule("firefox", "web")], {"046d:c359": "masaustu"})
        assert rules.profile_for("046d:c359", "konsole", "") == "masaustu"

    def test_a_default_beats_nothing_only_for_its_own_device(self):
        rules = appwatch.AppRules([], {"046d:c359": "masaustu"})
        assert rules.profile_for("046d:409f", "konsole", "") is None


class TestRuleFile:
    def test_rules_survive_a_round_trip(self, rules_file):
        rules = appwatch.AppRules(
            [appwatch.Rule("firefox", "web", device="046d:409f", title="mail")],
            {"046d:c359": "masaustu"})
        rules.save()
        again = appwatch.AppRules.load()
        assert again.rules == rules.rules
        assert again.defaults == rules.defaults

    def test_a_broken_file_is_not_fatal(self, rules_file):
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        rules_file.write_text("{ this is not json")
        assert appwatch.AppRules.load().rules == []

    def test_a_malformed_rule_is_skipped_and_the_rest_kept(self, rules_file):
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        rules_file.write_text(json.dumps({"rules": [
            {"match": "firefox", "profile": "web"},
            {"match": "no-profile"},
        ]}))
        assert [r.match for r in appwatch.AppRules.load().rules] == ["firefox"]

    def test_adding_the_same_pattern_replaces_it(self, rules_file):
        rules = appwatch.AppRules()
        rules.add("firefox", "web")
        rules.add("firefox", "tarayici")
        assert [(r.match, r.profile) for r in rules.rules] == [("firefox", "tarayici")]

    def test_the_same_pattern_can_answer_for_two_devices(self, rules_file):
        rules = appwatch.AppRules()
        rules.add("firefox", "web-klavye", device="046d:c359")
        rules.add("firefox", "web-fare", device="046d:409f")
        assert len(rules.rules) == 2

    def test_removing_reports_how_many_went(self, rules_file):
        rules = appwatch.AppRules([appwatch.Rule("firefox", "web")])
        assert rules.remove("firefox") == 1
        assert rules.remove("firefox") == 0


class TestAppIdentity:
    def test_kwins_desktop_name_is_trusted(self, monkeypatch):
        monkeypatch.setattr(appwatch, "_search_desktop_files", lambda c: pytest.fail("should not search"))
        assert appwatch.resolve_app_id("zoom", "/usr/share/applications/us.zoom.Zoom.desktop") == "us.zoom.Zoom"

    def test_the_desktop_lookup_is_used_when_kwin_has_no_name(self, monkeypatch):
        appwatch._resolve_cache.clear()
        monkeypatch.setattr(appwatch, "_search_desktop_files", lambda c: "us.zoom.Zoom")
        assert appwatch.resolve_app_id("zoom") == "us.zoom.Zoom"

    def test_an_unknown_class_keeps_its_own_name(self, monkeypatch):
        appwatch._resolve_cache.clear()
        monkeypatch.setattr(appwatch, "_search_desktop_files", lambda c: c)
        assert appwatch.resolve_app_id("some_game") == "some_game"


class TestFocus:
    def test_the_shell_is_ignored(self):
        w = appwatch.Watcher(appwatch.AppRules(), on_focus=lambda *a: pytest.fail("should not fire"))
        w.focus_changed("plasmashell", "Desktop")
        assert w.last_app is None

    def test_a_repeated_focus_does_not_fire_twice(self):
        seen = []
        w = appwatch.Watcher(appwatch.AppRules(), on_focus=lambda app, cap: seen.append(app))
        w.focus_changed("firefox", "Mail")
        w.focus_changed("firefox", "Mail")
        assert seen == ["firefox"]

    def test_a_new_caption_fires_again(self):
        seen = []
        w = appwatch.Watcher(appwatch.AppRules(), on_focus=lambda app, cap: seen.append(cap))
        w.focus_changed("firefox", "Mail")
        w.focus_changed("firefox", "Inbox")
        assert seen == ["Mail", "Inbox"]

    def test_losing_focus_clears_the_last_window(self):
        w = appwatch.Watcher(appwatch.AppRules(), on_focus=lambda *a: None)
        w.focus_changed("firefox", "Mail")
        w.focus_changed("", "")
        assert w.last_app is None
