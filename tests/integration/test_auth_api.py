"""회원가입/로그인/내 정보 API 통합테스트. 실제 DB 필요."""
import pytest

from .conftest import _unique_suffix

pytestmark = pytest.mark.integration


def test_register_success(client):
    suffix = _unique_suffix()
    r = client.post('/api/auth/register', json={
        'username': f'reg_{suffix}', 'email': f'reg_{suffix}@test.com', 'password': '1234'
    })
    assert r.status_code == 201
    assert r.get_json()['data']['username'] == f'reg_{suffix}'


def test_register_missing_fields(client):
    r = client.post('/api/auth/register', json={'username': 'x'})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_FIELDS'


def test_register_duplicate_email_rejected(client, user):
    r = client.post('/api/auth/register', json={
        'username': 'someoneelse', 'email': user['email'], 'password': '1234'
    })
    assert r.status_code == 409
    assert r.get_json()['code'] == 'DUPLICATE'


def test_login_wrong_password(client, user):
    r = client.post('/api/auth/login', json={'email': user['email'], 'password': 'wrong'})
    assert r.status_code == 401
    assert r.get_json()['code'] == 'INVALID_CREDENTIALS'


def test_login_unknown_email(client):
    r = client.post('/api/auth/login', json={'email': 'nobody@nowhere.com', 'password': '1234'})
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get('/api/auth/me')
    assert r.status_code == 401
    assert r.get_json()['code'] == 'UNAUTHORIZED'


def test_me_rejects_garbage_token(client):
    r = client.get('/api/auth/me', headers={'Authorization': 'Bearer not-a-real-token'})
    assert r.status_code == 401
    assert r.get_json()['code'] == 'INVALID_TOKEN'


def test_me_returns_profile(client, user):
    r = client.get('/api/auth/me', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['username'] == user['username']


def test_update_me_changes_real_name(client, user):
    r = client.put('/api/auth/me', headers=user['headers'], json={'real_name': '변경된이름'})
    assert r.status_code == 200

    r = client.get('/api/auth/me', headers=user['headers'])
    assert r.get_json()['data']['real_name'] == '변경된이름'


def test_update_me_duplicate_username_rejected(client, user, other_user):
    r = client.put('/api/auth/me', headers=other_user['headers'], json={'username': user['username']})
    assert r.status_code == 409
    assert r.get_json()['code'] == 'DUPLICATE'

    # 거부됐으니 other_user의 닉네임은 그대로여야 함
    r = client.get('/api/auth/me', headers=other_user['headers'])
    assert r.get_json()['data']['username'] == other_user['username']


def test_update_me_same_username_as_self_allowed(client, user):
    r = client.put('/api/auth/me', headers=user['headers'], json={'username': user['username']})
    assert r.status_code == 200


def test_update_me_nothing_to_update(client, user):
    r = client.put('/api/auth/me', headers=user['headers'], json={})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'NOTHING_TO_UPDATE'


def test_my_posts_empty_initially(client, user):
    r = client.get('/api/auth/me/posts', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['total'] == 0


def test_verify_invalid_code_format_rejected(client, user):
    r = client.post('/api/auth/verify', headers=user['headers'], json={
        'real_name': '테스터', 'code': '12'
    })
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_CODE'


def test_verify_success_then_already_verified(client, user):
    r = client.post('/api/auth/verify', headers=user['headers'], json={
        'real_name': '통합테스터', 'code': '123456'
    })
    assert r.status_code == 200

    r = client.post('/api/auth/verify', headers=user['headers'], json={
        'real_name': '통합테스터', 'code': '123456'
    })
    assert r.status_code == 409
    assert r.get_json()['code'] == 'ALREADY_VERIFIED'


def test_delete_me_soft_deletes_account(client, user):
    r = client.delete('/api/auth/me', headers=user['headers'])
    assert r.status_code == 200

    r = client.post('/api/auth/login', json={'email': user['email'], 'password': '1234'})
    assert r.status_code == 401
