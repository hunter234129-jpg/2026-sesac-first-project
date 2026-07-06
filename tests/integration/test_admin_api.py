"""관리자 API 통합테스트. admin_user fixture는 DB에서 직접 is_admin=1로 승격시킨 유저다."""
import pytest

pytestmark = pytest.mark.integration


def test_non_admin_blocked_from_user_list(client, user):
    r = client.get('/api/admin/users', headers=user['headers'])
    assert r.status_code == 403
    assert r.get_json()['code'] == 'FORBIDDEN'


def test_non_admin_blocked_from_post_list(client, user):
    r = client.get('/api/admin/posts', headers=user['headers'])
    assert r.status_code == 403


def test_non_admin_blocked_from_stats(client, user):
    r = client.get('/api/admin/stats', headers=user['headers'])
    assert r.status_code == 403


def test_admin_can_list_users(client, admin_user):
    r = client.get('/api/admin/users', headers=admin_user['headers'])
    assert r.status_code == 200
    assert 'users' in r.get_json()['data']


def test_admin_can_search_users(client, admin_user, user):
    r = client.get(f"/api/admin/users?q={user['username']}", headers=admin_user['headers'])
    assert r.status_code == 200
    assert any(u['username'] == user['username'] for u in r.get_json()['data']['users'])


def test_admin_can_view_stats(client, admin_user):
    r = client.get('/api/admin/stats', headers=admin_user['headers'])
    assert r.status_code == 200
    body = r.get_json()['data']
    assert {'users', 'posts', 'wiki', 'meetups'}.issubset(body.keys())


def test_admin_cannot_self_delete(client, admin_user):
    r = client.delete(f"/api/admin/users/{admin_user['id']}", headers=admin_user['headers'])
    assert r.status_code == 400
    assert r.get_json()['code'] == 'CANNOT_SELF_DELETE'


def test_admin_can_delete_other_user(client, admin_user, user):
    r = client.delete(f"/api/admin/users/{user['id']}", headers=admin_user['headers'])
    assert r.status_code == 200

    r = client.post('/api/auth/login', json={'email': user['email'], 'password': '1234'})
    assert r.status_code == 401


def test_delete_unknown_user_returns_404(client, admin_user):
    r = client.delete('/api/admin/users/999999999', headers=admin_user['headers'])
    assert r.status_code == 404


def test_admin_can_toggle_admin_flag(client, admin_user, user):
    r = client.patch(f"/api/admin/users/{user['id']}/admin", headers=admin_user['headers'],
                      json={'is_admin': True})
    assert r.status_code == 200
    assert r.get_json()['data']['is_admin'] is True

    r = client.patch(f"/api/admin/users/{user['id']}/admin", headers=admin_user['headers'],
                      json={'is_admin': False})
    assert r.get_json()['data']['is_admin'] is False


def test_admin_can_list_posts_and_soft_delete(client, admin_user, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '관리자삭제대상', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.get('/api/admin/posts', headers=admin_user['headers'])
    assert r.status_code == 200
    assert any(p['id'] == post_id for p in r.get_json()['data']['posts'])

    r = client.delete(f'/api/admin/posts/{post_id}', headers=admin_user['headers'])
    assert r.status_code == 200

    r = client.get(f'/api/posts/{post_id}')
    assert r.status_code == 404


def test_admin_delete_unknown_post_returns_404(client, admin_user):
    r = client.delete('/api/admin/posts/999999999', headers=admin_user['headers'])
    assert r.status_code == 404
