"""One visit to the key dialog sets both readings of the key.

GTK is not installed where the tests run, so the dialog cannot be built here. These
tests read the source instead and check the wiring that would otherwise only show up
as a lost assignment on a real desktop: the layer chooser must exist, switching it
must keep the edits of the layer being left, and both readings must come back.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "logi_ghub"
EDITORS = SRC / "gui" / "editors.py"
APP = SRC / "gui" / "app.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _class(path: Path, name: str) -> ast.ClassDef:
    for node in _tree(path).body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is missing from {path.name}")


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{cls.name}.{name} is missing")


def _source(path: Path, node: ast.AST) -> str:
    return ast.get_source_segment(path.read_text(), node) or ""


# -- the dialog --------------------------------------------------------------------


def test_the_dialog_takes_a_second_reading():
    init = _method(_class(EDITORS, "ActionDialog"), "__init__")
    names = [a.arg for a in init.args.args]
    assert "second" in names


def test_a_layer_chooser_is_built_only_when_there_are_two_layers():
    init = _source(EDITORS, _method(_class(EDITORS, "ActionDialog"), "__init__"))
    assert "self.has_layers" in init
    assert "if self.has_layers:" in init
    assert "G-Shift (while held)" in init


def test_switching_the_layer_keeps_what_was_typed():
    """Without _remember the first layer's edits vanish on a switch."""
    body = _source(EDITORS, _method(_class(EDITORS, "ActionDialog"), "_layer_changed"))
    assert "_remember" in body
    assert body.index("_remember") < body.index("self.action, self.second")


def test_both_readings_come_back():
    body = _source(EDITORS, _method(_class(EDITORS, "ActionDialog"), "_ok"))
    assert "self.on_done(self.action, self.second)" in body


def test_the_plain_reading_is_always_the_first_argument():
    """The page writes (plain, gshift); swapping them would cross the layers."""
    body = _source(EDITORS, _method(_class(EDITORS, "ActionDialog"), "_ok"))
    assert "self.on_done(self.second, self.action)" not in body


def test_the_second_reading_is_never_none():
    """Rows must not guard for None on every line; a default stands in."""
    init = _source(EDITORS, _method(_class(EDITORS, "ActionDialog"), "__init__"))
    assert 'Action("default")' in init


# -- the page ----------------------------------------------------------------------


def test_the_key_page_passes_both_layers():
    body = _source(APP, _method(_class(APP, "DevicePane"), "edit_key"))
    assert "second=second" in body
    assert "p.gshift_key_actions.get(name" in body


def test_the_page_writes_both_layers():
    body = _source(APP, _method(_class(APP, "DevicePane"), "edit_key"))
    assert "p.gshift_key_actions" in body
    assert "p.key_actions" in body


def test_the_dialog_opens_on_the_clicked_layer():
    body = _source(APP, _method(_class(APP, "DevicePane"), "edit_key"))
    assert "set_selected(1)" in body


def test_the_callback_accepts_two_actions():
    body = _source(APP, _method(_class(APP, "DevicePane"), "edit_key"))
    assert "def done(a: Action, b: Action)" in body
