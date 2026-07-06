"""오늘의 미션 API 통합테스트."""
import pytest

pytestmark = pytest.mark.integration


def test_today_mission_created_and_fetchable(client, user):
    r = client.get('/api/missions/today', headers=user['headers'])
    assert r.status_code == 200
    mission = r.get_json()['data']
    assert mission['id']
    assert mission['is_done'] == 0


def test_today_mission_is_stable_across_calls(client, user):
    """같은 날 두 번 호출해도 같은 미션이 나와야 한다(날짜 기반 결정론적 선택)."""
    r1 = client.get('/api/missions/today', headers=user['headers'])
    r2 = client.get('/api/missions/today', headers=user['headers'])
    assert r1.get_json()['data']['id'] == r2.get_json()['data']['id']


def test_complete_mission_and_history(client, user):
    r = client.get('/api/missions/today', headers=user['headers'])
    mission_id = r.get_json()['data']['id']

    r = client.post(f'/api/missions/{mission_id}/done', headers=user['headers'])
    assert r.status_code == 200

    r = client.get('/api/missions/today', headers=user['headers'])
    assert r.get_json()['data']['is_done'] == 1

    r = client.get('/api/missions/history', headers=user['headers'])
    assert r.status_code == 200
    assert len(r.get_json()['data']) >= 1


def test_complete_unknown_mission_returns_404(client, user):
    r = client.post('/api/missions/999999999/done', headers=user['headers'])
    assert r.status_code == 404
    assert r.get_json()['code'] == 'NOT_FOUND'
