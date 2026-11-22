"""Rows marked "not on Bannergress" whose banner is on the done list by now are flagged for the agent."""
from ingress_banners.match import RowMatch, group
from ingress_banners.site import _norm, outdated_choices

DONE = [
    {'id': 'secondsunday-2026-4-atacames-d92b', 'title': '#SecondSunday 2026-4 Atacames', 'missions': 6, 'picture': '/p/1'},
    {'id': 'memento-cygnus-3c8c', 'title': 'Memento: Cygnus', 'missions': 18, 'picture': '/p/2'},
    {'id': 'other-banner', 'title': 'Other banner', 'missions': 6, 'picture': '/p/3'},
]


def test_norm_ignores_hash_and_punctuation():
    assert _norm('#SecondSunday 2026-4 Atacames') == _norm('SecondSunday 2026 4 atacames') == 'secondsunday 2026 4 atacames'
    assert _norm(None) == ''


def test_group_keeps_what_the_pictures_matched():
    ms = [RowMatch(0, 'medal:SecondSunday 2026-4 Atacames', None, 0.0, 1.0, overridden=('secondsunday-2026-4-atacames-d92b', 0.02))]
    (e,) = group(ms)
    assert e['overridden'] == [('secondsunday-2026-4-atacames-d92b', 0.02)]


def test_picture_match_of_a_free_done_banner_is_flagged():
    entries = [{'id': 'memento-cygnus-3c8c', 'rows': [0]},
               {'id': 'medal:Some local name', 'rows': [1], 'overridden': [('secondsunday-2026-4-atacames-d92b', 0.021)]}]
    found = outdated_choices(entries, DONE)
    assert list(found) == [1]
    assert found[1][0]['id'] == 'secondsunday-2026-4-atacames-d92b' and found[1][0]['dist'] == 0.021


def test_same_title_is_flagged_without_a_picture_match():
    entries = [{'id': 'medal:SecondSunday 2026-4 Atacames', 'rows': [0]}]
    assert outdated_choices(entries, DONE)[0][0]['id'] == 'secondsunday-2026-4-atacames-d92b'


def test_banner_with_its_own_medals_is_not_suggested():
    # Memento: Cygnus has medals of its own: the "not on Bannergress" row isn't it
    entries = [{'id': 'memento-cygnus-3c8c', 'rows': [0]},
               {'id': 'medal:Memento Cygnus', 'rows': [1], 'overridden': [('memento-cygnus-3c8c', 0.01)]}]
    assert outdated_choices(entries, DONE) == {}


def test_other_rows_are_left_alone():
    entries = [{'id': 'medal:Not on Bannergress at all', 'rows': [0]},
               {'id': 'single:Single missions', 'rows': [1]},
               {'id': None, 'rows': [2]}]
    assert outdated_choices(entries, DONE) == {}
