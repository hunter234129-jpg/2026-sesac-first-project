"""통합테스트 공용 fixture.

app.test_client()로 실제 서버 프로세스 없이 Flask 앱에 직접 요청을 보내지만,
라우트가 db.connection.get_db()로 실제 MySQL에 붙기 때문에 config.py가 가리키는
DB는 반드시 켜져 있어야 한다. 회원가입/게시글 작성 등으로 실제 DB에 데이터가
쌓이니, 운영 데이터가 있는 DB가 아니라 테스트 전용 DB를 쓰는 걸 권장한다.
"""
import time
import uuid

import pytest

from app import app as flask_app
from db.connection import get_db


@pytest.fixture(scope='session')
def app():
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _unique_suffix():
    return f'{int(time.time() * 1000)}{uuid.uuid4().hex[:6]}'


def register_and_login(client, suffix=None):
    """새 유저를 회원가입 + 로그인시키고 토큰/헤더를 리턴한다. 매 호출마다 고유한 계정."""
    suffix = suffix or _unique_suffix()
    email = f'itest_{suffix}@test.com'
    username = f'itest_{suffix}'

    r = client.post('/api/auth/register', json={
        'username': username, 'email': email, 'password': '1234',
        'real_name': '통합테스터', 'interest_keywords': ''
    })
    assert r.status_code == 201, r.get_json()
    user_id = r.get_json()['data']['id']

    r = client.post('/api/auth/login', json={'email': email, 'password': '1234'})
    assert r.status_code == 200, r.get_json()
    token = r.get_json()['data']['access_token']

    return {
        'id':       user_id,
        'email':    email,
        'username': username,
        'token':    token,
        'headers':  {'Authorization': f'Bearer {token}'},
    }


@pytest.fixture
def user(client):
    """새로 회원가입 + 로그인된 유저 1명. 매 테스트마다 고유한 계정이라 서로 격리된다."""
    return register_and_login(client)


@pytest.fixture
def other_user(client):
    """모임 가입/탈퇴, 게시글 권한 검사처럼 2명이 필요한 테스트용 유저."""
    return register_and_login(client)


@pytest.fixture
def admin_user(client):
    """관리자 권한 유저. DB에서 직접 is_admin=1로 승격시킨 뒤 재로그인해 토큰에 반영한다
    (is_admin은 로그인 시점에 JWT에 박히므로, 승격 후 다시 로그인해야 반영됨)."""
    u = register_and_login(client)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 1 WHERE id = %s', (u['id'],))
        conn.commit()
    finally:
        conn.close()

    r = client.post('/api/auth/login', json={'email': u['email'], 'password': '1234'})
    assert r.status_code == 200, r.get_json()
    token = r.get_json()['data']['access_token']
    u['token'] = token
    u['headers'] = {'Authorization': f'Bearer {token}'}
    return u
