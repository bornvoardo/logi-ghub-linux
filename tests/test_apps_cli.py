"""The rules file, the CLI and the KWin script must agree."""

from __future__ import annotations

import json
from pathlib import Path

from logi_ghub import appwatch, cli

ROOT = Path(__file__).resolve().parents[1]


class Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _rules_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "logi-ghub-linux" / "app-profiles.json"


def test_the_cli_starts_with_nothing_configured(tmp_path, monkeypatch, capsys):
    _rules_file(tmp_path, monkeypatch)
    cli.cmd_apps(Args(apps_cmd="list"))
    out = capsys.readouterr().out
    assert "application profiles: on" in out
    assert "no window rules" in out


def test_off_is_written_and_read_back(tmp_path, monkeypatch):
    path = _rules_file(tmp_path, monkeypatch)
    cli.cmd_apps(Args(apps_cmd="off"))
    assert json.loads(path.read_text())["enabled"] is False
    assert appwatch.AppRules.load().enabled is False


def test_a_disabled_rule_file_does_nothing(tmp_path, monkeypatch):
    _rules_file(tmp_path, monkeypatch)
    cli.cmd_apps(Args(apps_cmd="off"))
    fired = []
    w = appwatch.Watcher(appwatch.AppRules.load(), on_focus=lambda a, c: fired.append(a))
    w.focus_changed("firefox", "Mail")
    assert fired == []


def test_adding_a_rule_for_a_missing_profile_is_refused(tmp_path, monkeypatch):
    _rules_file(tmp_path, monkeypatch)
    try:
        cli.cmd_apps(Args(apps_cmd="add", match="firefox", profile="web", device_model="046d:c359", title=None))
    except SystemExit as e:
        assert "no profile" in str(e)
    else:
        raise AssertionError("should have refused")


def test_a_rule_always_names_its_device(tmp_path, monkeypatch):
    """Rules are per device: each device's page makes its own."""
    path = _rules_file(tmp_path, monkeypatch)
    monkeypatch.setattr(cli.profiles, "list_profiles", lambda key: [type("P", (), {"name": "oyun"})()])
    cli.cmd_apps(Args(apps_cmd="add", match="steam_app_*", profile="oyun", device_model="046d:c359", title=None))
    saved = json.loads(path.read_text())
    assert saved["rules"][0]["match"] == "steam_app_*"
    assert saved["rules"][0]["device"] == "046d:c359"


def test_two_devices_can_bind_the_same_window(tmp_path, monkeypatch):
    path = _rules_file(tmp_path, monkeypatch)
    monkeypatch.setattr(cli.profiles, "list_profiles", lambda key: [type("P", (), {"name": "oyun"})()])
    cli.cmd_apps(Args(apps_cmd="add", match="steam_app_*", profile="oyun", device_model="046d:c359", title=None))
    cli.cmd_apps(Args(apps_cmd="add", match="steam_app_*", profile="oyun", device_model="046d:409f", title=None))
    saved = json.loads(path.read_text())
    assert sorted(r["device"] for r in saved["rules"]) == ["046d:409f", "046d:c359"]


def test_removing_an_unknown_rule_says_so(tmp_path, monkeypatch):
    _rules_file(tmp_path, monkeypatch)
    try:
        cli.cmd_apps(Args(apps_cmd="remove", match="nothing", device_model=None))
    except SystemExit as e:
        assert "no rule" in str(e)
    else:
        raise AssertionError("should have failed")


def test_the_kwin_script_calls_the_service_this_module_owns():
    script = (ROOT / "data" / "kwin" / "logi-ghub-focus.js").read_text()
    assert appwatch.SERVICE in script
    assert appwatch.OBJECT in script
    assert appwatch.INTERFACE in script
    assert "workspace.windowActivated.connect" in script
    assert "resourceClass" in script and "desktopFileName" in script


def test_the_script_reports_the_window_that_is_already_focused():
    """KWin loads the script after a window is up; waiting for the next switch
    would leave the first app without its profile."""
    script = (ROOT / "data" / "kwin" / "logi-ghub-focus.js").read_text()
    assert script.rstrip().endswith("send();")


def test_the_service_xml_declares_both_methods():
    assert "focusChanged" in appwatch.SERVICE_XML
    assert "focusLost" in appwatch.SERVICE_XML
