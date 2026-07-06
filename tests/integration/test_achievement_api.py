"""업적(뱃지) API 통합테스트. 클랜 폐지 이후 'social_clan' 지표는 post_members
(활성 가입 중인 모임 수) 기준으로 계산된다는 걸 함께 확인한다."""
import time

import pytest

pytestmark = pytest.mark.integration


def test_achievements_requires_auth(client):
    r = client.get('/api/achievements')
    assert r.status_code == 401


def test_list_achievements_shape(client, user):
    r = client.get('/api/achievements', headers=user['headers'])
    assert r.status_code == 200
    body = r.get_json()['data']
    assert set(['achievements', 'unlocked_count', 'total_count', 'newly_unlocked']) == set(body.keys())
    assert body['total_count'] == len(body['achievements'])
    item = body['achievements'][0]
    assert set(['key', 'emoji', 'title', 'desc', 'category', 'threshold',
                'current', 'progress', 'unlocked', 'unlocked_at', 'newly']).issubset(item.keys())


def test_first_session_achievement_unlocks_once(client, user):
    client.post('/api/study/start', headers=user['headers'])
    time.sleep(1)
    client.post('/api/study/end', headers=user['headers'])

    r = client.get('/api/achievements', headers=user['headers'])
    body = r.get_json()['data']
    assert 'first_session' in body['newly_unlocked']
    first_session = next(a for a in body['achievements'] if a['key'] == 'first_session')
    assert first_session['unlocked'] is True

    # 두 번째 호출부터는 이미 달성했으니 newly_unlocked에 다시 나오면 안 된다
    r2 = client.get('/api/achievements', headers=user['headers'])
    assert 'first_session' not in r2.get_json()['data']['newly_unlocked']


def test_social_post_achievement_unlocks_after_creating_post(client, user):
    r = client.get('/api/achievements', headers=user['headers'])
    before = next(a for a in r.get_json()['data']['achievements'] if a['key'] == 'social_post')
    assert before['unlocked'] is False

    client.post('/api/posts', headers=user['headers'], json={
        'title': '업적테스트글', 'content': '', 'type': 'post'
    })

    r = client.get('/api/achievements', headers=user['headers'])
    after = next(a for a in r.get_json()['data']['achievements'] if a['key'] == 'social_post')
    assert after['unlocked'] is True


def test_social_clan_metric_counts_active_meetup_membership(client, user, other_user):
    """모임 가입 → 활성 회원으로 잡힘 → 탈퇴하면 다시 미달성으로 안 떨어진다(unlocked는 유지,
    current 지표만 활성 가입 수를 반영)."""
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '업적모임테스트', 'content': '', 'type': 'study'
    })
    post_id = r.get_json()['data']['id']
    client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])

    r = client.get('/api/achievements', headers=other_user['headers'])
    social_clan = next(a for a in r.get_json()['data']['achievements'] if a['key'] == 'social_clan')
    assert social_clan['unlocked'] is True
    assert social_clan['current'] >= 1
