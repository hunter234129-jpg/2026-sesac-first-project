"""통합테스트 공용 fixture.

app.test_client()로 실제 서버 프로세스 없이 Flask 앱에 직접 요청을 보내지만,
라우트가 db.connection.get_db()로 실제 MySQL에 붙기 때문에 config.py가 가리키는
DB는 반드시 켜져 있어야 한다. 회원가입/게시글 작성 등으로 실제 DB에 데이터가
쌓이니, 운영 데이터가 있는 DB가 아니라 테스트 전용 DB를 쓰는 걸 권장한다.
"""
import json
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


def seed_exam(name, round_=1, exam_start=None, category='IT자격증', source='qnet'):
    """exams 테이블에 직접 행을 넣는다 — 실제 시험 데이터는 크롤러로만 채워지고
    생성용 API가 없어서, exams/posts 연동 테스트는 DB에 직접 시드해야 한다."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO exams (name, round, category, source, exam_start)
               VALUES (%s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE exam_start = VALUES(exam_start)''',
            (name, round_, category, source, exam_start)
        )
        conn.commit()
    finally:
        conn.close()


def seed_wrong_note(user_id, subject_query='통합테스트과목', level=3, question='문제?',
                     choices=None, answer_index=0, chosen_index=1, explanation='설명'):
    """ai_quiz_wrong_notes에 직접 행을 넣는다 — 오답노트는 정상적으로는 문제풀기
    제출 흐름에서만 쌓이는데, 오답노트 자체(목록/삭제/약점분석) 테스트는 그 흐름과
    분리해서 독립적으로 시드하는 게 더 단순하다."""
    choices = choices or ['A', 'B', 'C', 'D']
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO ai_quiz_wrong_notes
                 (user_id, subject_query, level, question, choices, answer_index, chosen_index, explanation)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (user_id, subject_query, level, question,
             json.dumps(choices, ensure_ascii=False), answer_index, chosen_index, explanation)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


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
