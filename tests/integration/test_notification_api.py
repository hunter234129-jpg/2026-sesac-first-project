"""키워드 구독 + 알림 API 통합테스트."""
import pytest

pytestmark = pytest.mark.integration


def test_keyword_add_list_delete(client, user):
    r = client.post('/api/keywords', headers=user['headers'], json={'keyword': '파이썬'})
    assert r.status_code == 201

    r = client.get('/api/keywords', headers=user['headers'])
    assert r.status_code == 200
    assert any(k['keyword'] == '파이썬' for k in r.get_json()['data'])

    r = client.delete('/api/keywords/파이썬', headers=user['headers'])
    assert r.status_code == 200

    r = client.get('/api/keywords', headers=user['headers'])
    assert all(k['keyword'] != '파이썬' for k in r.get_json()['data'])


def test_keyword_duplicate_rejected(client, user):
    client.post('/api/keywords', headers=user['headers'], json={'keyword': '자바'})
    r = client.post('/api/keywords', headers=user['headers'], json={'keyword': '자바'})
    assert r.status_code == 409
    assert r.get_json()['code'] == 'DUPLICATE'


def test_keyword_missing_rejected(client, user):
    r = client.post('/api/keywords', headers=user['headers'], json={'keyword': ''})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_FIELDS'


def test_delete_unknown_keyword_returns_404(client, user):
    r = client.delete('/api/keywords/없는키워드', headers=user['headers'])
    assert r.status_code == 404


def test_keyword_triggers_notification_on_matching_post(client, user, other_user):
    client.post('/api/keywords', headers=user['headers'], json={'keyword': '알고리즘'})

    r = client.post('/api/posts', headers=other_user['headers'], json={
        'title': '알고리즘 스터디 모집', 'content': '', 'type': 'post'
    })
    assert r.status_code == 201

    r = client.get('/api/notifications', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['unread'] >= 1


def test_mark_notification_read_and_read_all(client, user, other_user):
    client.post('/api/keywords', headers=user['headers'], json={'keyword': '리액트'})
    client.post('/api/posts', headers=other_user['headers'], json={
        'title': '리액트 스터디', 'content': '', 'type': 'post'
    })

    r = client.get('/api/notifications', headers=user['headers'])
    nid = r.get_json()['data']['notifications'][0]['id']

    r = client.patch(f'/api/notifications/{nid}/read', headers=user['headers'])
    assert r.status_code == 200

    r = client.patch('/api/notifications/read-all', headers=user['headers'])
    assert r.status_code == 200

    r = client.get('/api/notifications', headers=user['headers'])
    assert r.get_json()['data']['unread'] == 0


def test_mark_unknown_notification_read_returns_404(client, user):
    r = client.patch('/api/notifications/999999999/read', headers=user['headers'])
    assert r.status_code == 404
