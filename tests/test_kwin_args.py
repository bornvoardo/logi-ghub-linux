"""The KWin scripting calls: the arguments GLib actually accepts."""

from __future__ import annotations

import pytest

from logi_ghub import appwatch

gi = pytest.importorskip("gi")
gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402


CALLS = [
    ("loadScript", {"path": "/tmp/s.js", "plugin": "logi-ghub-focus"}, "(ss)", "/tmp/s.js", "(i)"),
    ("unloadScript", {"plugin": "logi-ghub-focus"}, "(s)", "logi-ghub-focus", "()"),
    ("start", {}, "()", None, "()"),
    ("isScriptLoaded", {"plugin": "logi-ghub-focus"}, "(s)", "logi-ghub-focus", "(b)"),
]


@pytest.mark.parametrize("method,kwargs,sig,first,reply", CALLS)
def test_the_signatures_match_kwin(method, kwargs, sig, first, reply):
    got_sig, values, got_reply = appwatch._kwin_args(method, kwargs)
    assert got_sig == sig
    assert (values[0] if values else None) == first
    assert got_reply == reply


@pytest.mark.parametrize("method,kwargs,sig,first,reply", CALLS)
def test_glib_builds_the_variant(method, kwargs, sig, first, reply):
    """The old code wrapped each argument in GLib.Variant and handed those to
    another GLib.Variant, which fails with "Must be string, not Variant" — the
    script never loaded and window profiles never switched."""
    got_sig, values, _ = appwatch._kwin_args(method, kwargs)
    if values:
        variant = GLib.Variant(got_sig, values)
        assert variant.unpack() == values


def test_a_void_method_passes_no_argument_variant():
    """start takes no arguments; passing an empty Variant is not the same as None."""
    _, values, _ = appwatch._kwin_args("start", {})
    assert values == ()


def test_an_unknown_method_gets_no_arguments():
    sig, values, reply = appwatch._kwin_args("somethingElse", {})
    assert sig == "()" and values == () and reply == "()"


def test_the_script_is_loaded_under_a_fixed_plugin_name():
    """unloadScript and isScriptLoaded find the script by this name."""
    src = open(appwatch.__file__).read()
    assert 'plugin="logi-ghub-focus"' in src
