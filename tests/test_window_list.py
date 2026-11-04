"""The window list the app's picker shows."""

from __future__ import annotations

import json

from logi_ghub import appwatch


def _blob(*windows):
    return appwatch.SEP_WINDOW.join(
        appwatch.SEP_FIELD.join(fields) for fields in windows)


def test_the_kwin_string_is_split_into_windows():
    blob = _blob(("org.kde.konsole", "~ : zsh", "org.kde.konsole"),
                 ("steam_app_5335510", "MoonSweepers", ""))
    windows = appwatch.parse_windows(blob)
    assert [w["class"] for w in windows] == ["org.kde.konsole", "steam_app_5335510"]
    assert windows[0]["title"] == "~ : zsh"
    assert windows[1]["desktop"] == ""


def test_the_class_is_resolved_to_the_value_a_rule_matches():
    """The picker must fill in what Rule.matches compares against, not the raw
    class: for a KDE application those differ."""
    blob = _blob(("konsole", "~ : zsh", "org.kde.konsole"))
    window = appwatch.parse_windows(blob)[0]
    assert window["app_id"] == "org.kde.konsole"
    assert appwatch.Rule(window["app_id"], "x").matches(window["app_id"], "")


def test_an_empty_report_gives_no_windows():
    assert appwatch.parse_windows("") == []
    assert appwatch.parse_windows("\x02\x02") == []


def test_a_caption_with_a_separator_is_kept_whole():
    """Captions come from applications, so they are not trusted to stay clean."""
    blob = _blob(("firefox", "a b c", ""))
    assert appwatch.parse_windows(blob)[0]["title"] == "a b c"


def test_the_list_survives_a_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    appwatch.save_windows(_blob(("org.kde.konsole", "~ : zsh", "org.kde.konsole")))
    saved = json.loads((tmp_path / "logi-ghub-linux" / "windows.json").read_text())
    assert saved["windows"][0]["app_id"] == "org.kde.konsole"
    assert appwatch.load_windows()[0]["class"] == "org.kde.konsole"


def test_a_missing_file_reads_as_no_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert appwatch.load_windows() == []


def test_the_service_declares_the_report_method():
    """The KWin script calls windowsReported; the interface must offer it."""
    assert "windowsReported" in appwatch.SERVICE_XML


def test_the_kwin_script_pushes_the_window_list():
    from pathlib import Path

    script = (Path(appwatch.__file__).parent.parent.parent / "data" / "kwin" / "logi-ghub-focus.js").read_text()
    assert "windowsReported" in script
    assert "workspace.windowList" in script
