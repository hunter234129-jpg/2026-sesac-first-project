"""공부 세션(study) API 통합테스트."""
import time

import pytest

pytestmark = pytest.mark.integration


def test_start_status_end_flow(client, user):
    r = client.post('/api/study/start', headers=user['headers'])
    assert r.status_code == 201

    r = client.get('/api/study/status', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['active'] is True

    r = client.post('/api/study/start', headers=user['headers'])
    assert r.status_code == 409
    assert r.get_json()['code'] == 'SESSION_ACTIVE'

    time.sleep(1)
    r = client.post('/api/study/end', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['duration_sec'] >= 1

    r = client.get('/api/study/status', headers=user['headers'])
    assert r.get_json()['data']['active'] is False


def test_end_without_active_session_rejected(client, user):
    r = client.post('/api/study/end', headers=user['headers'])
    assert r.status_code == 404
    assert r.get_json()['code'] == 'NO_ACTIVE_SESSION'


def test_stats_and_ranking_are_reachable(client, user):
    r = client.get('/api/study/stats', headers=user['headers'])
    assert r.status_code == 200
    assert 'stats' in r.get_json()['data']

    r = client.get('/api/study/ranking?period=all')
    assert r.status_code == 200
    assert 'ranking' in r.get_json()['data']


def test_streak_shape(client, user):
    r = client.get('/api/study/streak', headers=user['headers'])
    assert r.status_code == 200
    data = r.get_json()['data']
    assert set(['current_streak', 'longest_streak', 'studied_today', 'total_days']) == set(data.keys())


def test_goal_get_default_and_set(client, user):
    r = client.get('/api/study/goal', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['daily_goal_min'] == 240

    r = client.put('/api/study/goal', headers=user['headers'], json={'daily_goal_min': 60})
    assert r.status_code == 200

    r = client.get('/api/study/goal', headers=user['headers'])
    assert r.get_json()['data']['daily_goal_min'] == 60


def test_goal_out_of_range_rejected(client, user):
    r = client.put('/api/study/goal', headers=user['headers'], json={'daily_goal_min': 5})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_GOAL'

    r = client.put('/api/study/goal', headers=user['headers'], json={'daily_goal_min': 'not-a-number'})
    assert r.status_code == 400


def test_heatmap_live_and_planet_are_reachable(client, user):
    r = client.get('/api/study/heatmap', headers=user['headers'])
    assert r.status_code == 200
    assert 'days' in r.get_json()['data']

    r = client.get('/api/study/live')
    assert r.status_code == 200
    assert 'count' in r.get_json()['data']

    r = client.get('/api/study/planet', headers=user['headers'])
    assert r.status_code == 200
    assert 'level' in r.get_json()['data']
