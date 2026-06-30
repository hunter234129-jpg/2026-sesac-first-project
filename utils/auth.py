import jwt
import datetime
from functools import wraps
from flask import request, jsonify, g
from config import JWT_SECRET, JWT_EXPIRE_HOURS


def create_token(user_id, username, is_admin=False):
    payload = {
        'user_id':  user_id,
        'username': username,
        'is_admin': is_admin,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def decode_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': '인증이 필요합니다', 'code': 'UNAUTHORIZED'}), 401
        try:
            payload    = decode_token(auth[7:])
            g.user_id  = payload['user_id']
            g.username = payload['username']
            g.is_admin = payload.get('is_admin', False)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': '토큰이 만료됐습니다', 'code': 'TOKEN_EXPIRED'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': '유효하지 않은 토큰입니다', 'code': 'INVALID_TOKEN'}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not g.is_admin:
            return jsonify({'error': '관리자 권한이 필요합니다', 'code': 'FORBIDDEN'}), 403
        return f(*args, **kwargs)
    return wrapper
