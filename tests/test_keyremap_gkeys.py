"""G-key assignment: the G-keys arrive as F13..F21, so a profile names them by G."""

from __future__ import annotations

import pytest

from logi_ghub import keyremap
from logi_ghub.actions import Action


@pytest.mark.parametrize("g,code", [(f"G{i}", 182 + i) for i in range(1, 10)])
def test_g_keys_resolve_to_their_function_key(g, code):
    assert keyremap.key_code(g) == code


def test_g_key_names_are_kept_as_profile_keys():
    assert keyremap.canonical("G1") == "G1"


def test_a_profile_can_assign_a_g_key():
    mapping = keyremap.resolve({"G1": Action.keypress(4, []), "G9": Action("none")})
    assert mapping == {183: Action.keypress(4, []), 191: Action("none")}


def test_g_keys_do_not_shadow_real_key_names():
    """F13 is a real key name too; it must still mean F13."""
    assert keyremap.key_code("F13") == 183
    assert keyremap.key_code("F21") == 191
