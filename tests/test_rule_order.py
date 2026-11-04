"""Rule order: first match wins, so the order is part of the meaning."""

from __future__ import annotations

import pytest

from logi_ghub import appwatch

DEV = "046d:c359"


@pytest.fixture
def rules():
    r = appwatch.AppRules()
    r.add("a*", "profil-a", DEV)
    r.add("b*", "profil-b", DEV)
    r.add("c*", "profil-c", DEV)
    return r


def test_editing_a_rule_keeps_its_position(rules):
    """add() used to drop the old rule and append the new one, which silently
    changed which rule won for a window matching both."""
    rules.add("a*", "yeni", DEV)
    assert [r.match for r in rules.rules] == ["a*", "b*", "c*"]
    assert rules.rules[0].profile == "yeni"


def test_editing_does_not_duplicate(rules):
    rules.add("a*", "yeni", DEV)
    assert len(rules.rules) == 3


def test_a_new_rule_goes_last(rules):
    rules.add("d*", "profil-d", DEV)
    assert [r.match for r in rules.rules] == ["a*", "b*", "c*", "d*"]


def test_move_up(rules):
    assert rules.move("b*", DEV, -1)
    assert [r.match for r in rules.rules] == ["b*", "a*", "c*"]


def test_move_down(rules):
    assert rules.move("b*", DEV, +1)
    assert [r.match for r in rules.rules] == ["a*", "c*", "b*"]


def test_move_stops_at_the_edges(rules):
    assert not rules.move("a*", DEV, -1)
    assert not rules.move("c*", DEV, +1)
    assert [r.match for r in rules.rules] == ["a*", "b*", "c*"]


def test_move_an_unknown_rule_reports_failure(rules):
    assert not rules.move("nope*", DEV, -1)


def test_the_order_decides_the_winner(rules):
    """The reason the order matters: profile_for returns the first match."""
    rules.rules = []
    rules.add("steam_app_*", "genel-oyun", DEV)
    rules.add("steam_app_5335510", "moon-sweepers", DEV)
    assert rules.profile_for(DEV, "steam_app_5335510", "") == "genel-oyun"
    rules.move("steam_app_5335510", DEV, -1)
    assert [r.match for r in rules.rules] == ["steam_app_5335510", "steam_app_*"]
    assert rules.profile_for(DEV, "steam_app_5335510", "") == "moon-sweepers"


def test_move_shifts_by_one_position(rules):
    """The arrows in the app move a rule one place, never to an arbitrary index."""
    assert rules.move("c*", DEV, -1)
    assert [r.match for r in rules.rules] == ["a*", "c*", "b*"]
    # A delta larger than one still only swaps with the neighbour.
    assert rules.move("b*", DEV, -5)
    assert [r.match for r in rules.rules] == ["a*", "b*", "c*"]


def test_a_specific_pattern_wins_when_it_comes_first(rules):
    rules.rules = []
    rules.add("steam_app_*", "genel-oyun", DEV)
    rules.add("steam_app_5335510", "moon-sweepers", DEV)
    # First match wins, so the general rule answers even for the specific window.
    assert rules.profile_for(DEV, "steam_app_5335510", "") == "genel-oyun"
    # Moving the specific rule up makes it win.
    rules.move("steam_app_5335510", DEV, -1)
    assert rules.profile_for(DEV, "steam_app_5335510", "") == "moon-sweepers"


def test_index_of_reports_the_position(rules):
    assert rules.index_of("b*", DEV) == 1
    assert rules.index_of("nope*", DEV) is None


def test_move_to_puts_a_renamed_rule_back_where_it_was(rules):
    """Renaming a pattern changes its identity, so the app restores the position."""
    position = rules.index_of("b*", DEV)
    rules.remove("b*", DEV)
    rules.add("b-neu*", "profil-b", DEV)
    assert rules.index_of("b-neu*", DEV) == 2
    assert rules.move_to("b-neu*", DEV, position)
    assert [r.match for r in rules.rules] == ["a*", "b-neu*", "c*"]


def test_move_to_clamps_to_the_list(rules):
    rules.move_to("a*", DEV, 99)
    assert [r.match for r in rules.rules] == ["b*", "c*", "a*"]
    rules.move_to("a*", DEV, -5)
    assert [r.match for r in rules.rules] == ["a*", "b*", "c*"]
