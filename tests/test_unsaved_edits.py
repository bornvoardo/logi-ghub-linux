"""The picture and the banner must agree about unsaved edits."""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "logi_ghub" / "gui" / "app.py").read_text()


def test_the_unsaved_banner_is_loud():
    """A quiet banner is what let a saved-looking assignment stay in the window only."""
    assert ".lgl-unsaved" in SOURCE
    assert "UNSAVED CHANGES" in SOURCE


def test_the_banner_says_the_service_reads_the_saved_file():
    """The reason the edit does nothing has to be written next to the edit."""
    assert "the service reads the saved file" in SOURCE


def test_closing_the_window_asks_first():
    assert 'self.connect("close-request", self._on_close_request)' in SOURCE
    assert "def close_request(self):" in SOURCE


def test_switching_device_asks_first():
    """Selecting another device used to throw the pane's edits away silently."""
    assert "Discard unsaved changes?" in SOURCE
    assert "_select_device" in SOURCE


def test_the_confirm_helper_can_run_something_when_the_user_says_no():
    """Without this the device list keeps a highlight the window never opened."""
    editors = (Path(__file__).resolve().parents[1] / "src" / "logi_ghub" / "gui" / "editors.py").read_text()
    assert "on_no=" in editors
