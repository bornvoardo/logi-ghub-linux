"""The daemon and the command line carry the second keyboard layer through."""

from __future__ import annotations

from pathlib import Path

from logi_ghub import keyremap, profiles
from logi_ghub.actions import Action

ROOT = Path(__file__).resolve().parents[1]
DEV = "046d:c359"


def test_resolve_handles_both_layers_the_same_way():
    """One function, two layers: the second is not a special case."""
    first = keyremap.resolve({"A": Action("key", key=0x04)})
    second = keyremap.resolve({"A": Action("key", key=0x29)})
    assert first != second
    assert keyremap.key_code("A") in first
    assert keyremap.key_code("A") in second


def test_resolve_drops_keys_left_at_default():
    assert keyremap.resolve({"A": Action("default")}) == {}


def test_resolve_skips_a_name_it_cannot_read():
    """A bad name must not take the whole layer down with it."""
    out = keyremap.resolve({"NotAKey": Action("key", key=0x04), "A": Action("key", key=0x05)})
    assert len(out) == 1


# -- the daemon ------------------------------------------------------------------


def _daemon_source() -> str:
    return (ROOT / "src" / "logi_ghub" / "daemon.py").read_text()


def test_the_daemon_passes_the_second_layer():
    src = _daemon_source()
    assert "keyremap.resolve(self.profile.gshift_key_actions)" in src
    assert "gshift_mapping=gshift_mapping" in src


def test_a_profile_with_only_a_second_layer_still_remaps():
    """A G-Shift layer naming keys the first layer does not is still worth running."""
    src = _daemon_source()
    body = src[src.index("def ensure_keys"):src.index("def on_gshift")]
    assert "self.profile.key_actions or self.profile.gshift_key_actions" in body
    assert "if not mapping and not gshift_mapping:" in body


def test_the_daemon_records_the_layer_on_the_session():
    """The mouse half reads session.gshift, so it must be kept up to date."""
    src = _daemon_source()
    body = src[src.index("def on_gshift"):src.index("def _keys_problem")]
    assert "self.gshift = on" in body


def test_the_layer_change_is_queued_not_applied_inline():
    """on_gshift runs on the reader thread; blocking there would stall typing."""
    src = _daemon_source()
    body = src[src.index("def on_gshift"):src.index("def _keys_problem")]
    assert 'self.events.put(("gshift"' in body


# -- the command line ------------------------------------------------------------


def test_the_cli_can_fill_the_second_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = profiles.Profile(name="Work", device=DEV)
    p.gshift_key_actions["A"] = Action("key", key=0x29)
    profiles.save_profile(p)
    back = profiles.load_profile(DEV, "Work")
    assert back.gshift_key_actions["A"].key == 0x29


def test_the_cli_offers_the_second_layer_flags():
    src = (ROOT / "src" / "logi_ghub" / "cli.py").read_text()
    assert '"--gshift", dest="gshift_assign"' in src
    assert '"--gshift-reset"' in src
    assert '"--gshift-clear"' in src


def test_the_cli_lists_a_key_that_is_only_in_the_second_layer():
    src = (ROOT / "src" / "logi_ghub" / "cli.py").read_text()
    assert "(only in G-Shift)" in src
