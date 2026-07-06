from flask import Blueprint, jsonify, request, g
from werkzeug.security import generate_password_hash, check_password_hash
from db.connection import get_db
from utils.auth import create_token, login_required

auth_bp = Blueprint('auth', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data              = request.get_json() or {}
    username          = data.get('username', '').strip()
    email             = data.get('email', '').strip()
    password          = data.get('password', '')
    real_name         = data.get('real_name', '').strip()
    interest_keywords = data.get('interest_keywords', '').strip()

    if not username or not email or not password:
        return err('username, email, password는 필수입니다', 'MISSING_FIELDS')

    pw_hash = generate_password_hash(password)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM users WHERE email = %s OR username = %s',
            (email, username)
        )
        if cursor.fetchone():
            return err('이미 사용 중인 이메일 또는 닉네임입니다', 'DUPLICATE', 409)
        cursor.execute(
            '''INSERT INTO users
               (username, email, password_hash, real_name, interest_keywords)
               VALUES (%s, %s, %s, %s, %s)''',
            (username, email, pw_hash,
             real_name or None, interest_keywords or None)
        )
        new_id = cursor.lastrowid

        # 가입 시 입력한 관심 키워드를 알림 구독 테이블에도 등록
        if interest_keywords:
            seen = set()
            for kw in interest_keywords.split(','):
                kw = kw.strip()
                if kw and kw not in seen:
                    seen.add(kw)
                    cursor.execute(
                        'INSERT INTO keyword_subscriptions (user_id, keyword) VALUES (%s, %s)',
                        (new_id, kw)
                    )
        conn.commit()
    finally:
        conn.close()

    return ok({'id': new_id, 'username': username}, '회원가입 완료'), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data     = request.get_json() or {}
    email    = data.get('email', '')
    password = data.get('password', '')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT id, username, password_hash, is_admin
               FROM users
               WHERE email = %s AND is_deleted = 0''',
            (email,)
        )
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return err('이메일 또는 비밀번호가 올바르지 않습니다', 'INVALID_CREDENTIALS', 401)

    token = create_token(user['id'], user['username'], bool(user['is_admin']))
    return ok({'access_token': token, 'username': user['username']})


@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def get_me():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT id, username, email, real_name, interest_keywords,
                      avatar_id, is_verified, is_admin, created_at
               FROM users
               WHERE id = %s AND is_deleted = 0''',
            (g.user_id,)
        )
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user:
        return err('사용자를 찾을 수 없습니다', 'NOT_FOUND', 404)
    return ok(user)


@auth_bp.route('/api/auth/me', methods=['PUT'])
@login_required
def update_me():
    data              = request.get_json() or {}
    username          = data.get('username', '').strip()
    password          = data.get('password', '')
    real_name         = data.get('real_name', '').strip()
    interest_keywords = data.get('interest_keywords')

    if not username and not password and not real_name and interest_keywords is None:
        return err('수정할 내용이 없습니다', 'NOTHING_TO_UPDATE')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if username:
            cursor.execute(
                'SELECT id FROM users WHERE username = %s AND id != %s',
                (username, g.user_id)
            )
            if cursor.fetchone():
                return err('이미 사용 중인 닉네임입니다', 'DUPLICATE', 409)

        updates, params = [], []
        if username:
            updates.append('username = %s')
            params.append(username)
        if password:
            updates.append('password_hash = %s')
            params.append(generate_password_hash(password))
        if real_name:
            updates.append('real_name = %s')
            params.append(real_name)
        if interest_keywords is not None:
            updates.append('interest_keywords = %s')
            params.append(interest_keywords)

        params.append(g.user_id)
        cursor.execute(
            f'UPDATE users SET {", ".join(updates)} WHERE id = %s AND is_deleted = 0',
            params
        )
        conn.commit()
    finally:
        conn.close()

    return ok({}, '수정 완료')


@auth_bp.route('/api/auth/me', methods=['DELETE'])
@login_required
def delete_me():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE users SET is_deleted = 1, deleted_at = NOW() WHERE id = %s',
            (g.user_id,)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({}, '탈퇴 완료')


@auth_bp.route('/api/auth/me/posts', methods=['GET'])
@login_required
def get_my_posts():
    page   = max(1, int(request.args.get('page', 1)))
    size   = max(1, min(50, int(request.args.get('size', 10))))
    offset = (page - 1) * size

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT COUNT(*) AS cnt FROM posts WHERE user_id = %s AND deleted_at IS NULL',
            (g.user_id,)
        )
        total = cursor.fetchone()['cnt']

        cursor.execute(
            '''SELECT id, title, type, category, status, view_count, created_at
               FROM posts
               WHERE user_id = %s AND deleted_at IS NULL
               ORDER BY created_at DESC
               LIMIT %s OFFSET %s''',
            (g.user_id, size, offset)
        )
        posts = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'posts':       posts,
        'total':       total,
        'page':        page,
        'total_pages': (total + size - 1) // size
    })


@auth_bp.route('/api/auth/me/wiki', methods=['GET'])
@login_required
def get_my_wiki():
    page   = max(1, int(request.args.get('page', 1)))
    size   = max(1, min(50, int(request.args.get('size', 10))))
    offset = (page - 1) * size

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT COUNT(DISTINCT wiki_id) AS cnt FROM wiki_revisions WHERE author_id = %s',
            (g.user_id,)
        )
        total = cursor.fetchone()['cnt']

        cursor.execute(
            '''SELECT w.id, w.title, w.slug, w.view_count,
                      MAX(r.created_at) AS last_edited,
                      COUNT(r.id)       AS contribution_count
               FROM wiki_revisions r
               JOIN wiki_pages w ON r.wiki_id = w.id
               WHERE r.author_id = %s
               GROUP BY w.id
               ORDER BY last_edited DESC
               LIMIT %s OFFSET %s''',
            (g.user_id, size, offset)
        )
        wikis = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'wikis':       wikis,
        'total':       total,
        'page':        page,
        'total_pages': (total + size - 1) // size
    })


@auth_bp.route('/api/auth/verify', methods=['POST'])
@login_required
def verify_identity():
    data      = request.get_json() or {}
    real_name = data.get('real_name', '').strip()
    code      = data.get('code', '').strip()

    if not real_name or not code:
        return err('real_name과 code는 필수입니다', 'MISSING_FIELDS')
    if not code.isdigit() or len(code) != 6:
        return err('인증번호는 6자리 숫자여야 합니다', 'INVALID_CODE')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT real_name, is_verified FROM users WHERE id = %s AND is_deleted = 0',
            (g.user_id,)
        )
        user = cursor.fetchone()
        if not user:
            return err('사용자를 찾을 수 없습니다', 'NOT_FOUND', 404)
        if user['is_verified']:
            return err('이미 인증된 계정입니다', 'ALREADY_VERIFIED', 409)

        # 기존 real_name이 있으면 일치 여부 확인
        if user['real_name'] and user['real_name'] != real_name:
            return err('입력한 이름이 등록된 정보와 일치하지 않습니다', 'NAME_MISMATCH', 400)

        cursor.execute(
            'UPDATE users SET is_verified = 1, real_name = %s WHERE id = %s',
            (real_name, g.user_id)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({}, '인증 완료')
