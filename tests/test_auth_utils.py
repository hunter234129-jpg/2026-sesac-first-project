"""utils/auth.py의 토큰 생성/검증 로직에 대한 순수 단위테스트.
DB나 Flask 서버 없이 순수 함수만 검증한다.
실행: venv\\Scripts\\python.exe -m pytest tests/test_auth_utils.py -v
"""
import datetime

import jwt
import pytest

from config import JWT_SECRET
from utils.auth import create_token, decode_token


def test_create_token_roundtrip():
    token = create_token(user_id=1, username='tester', is_admin=False)
    payload = decode_token(token)

    assert payload['user_id'] == 1
    assert payload['username'] == 'tester'
    assert payload['is_admin'] is False


def test_create_token_default_is_admin_false():
    token = create_token(user_id=2, username='nodefault')
    payload = decode_token(token)

    assert payload['is_admin'] is False


def test_create_token_admin_true():
    token = create_token(user_id=3, username='admin', is_admin=True)
    payload = decode_token(token)

    assert payload['is_admin'] is True


def test_decode_token_expired_raises():
    expired_payload = {
        'user_id': 1,
        'username': 'tester',
        'is_admin': False,
        'exp': datetime.datetime.utcnow() - datetime.timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm='HS256')

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)


def test_decode_token_wrong_secret_raises():
    token = jwt.encode(
        {'user_id': 1, 'username': 'tester', 'is_admin': False,
         'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
        'wrong-secret',
        algorithm='HS256',
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)


def test_decode_token_garbage_string_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token('not-a-real-token')
