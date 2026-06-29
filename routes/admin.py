from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import admin_required

admin_bp = Blueprint('admin', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


# ── 회원 관리 ────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def list_users():
    page    = max(1, int(request.args.get('page', 1)))
    size    = max(1, min(100, int(request.args.get('size', 20))))
    q       = request.args.get('q', '').strip()
    include_deleted = request.args.get('include_deleted') == '1'
    offset  = (page - 1) * size

    wheres, params = [], []
    if not include_deleted:
        wheres.append('is_deleted = 0')
    if q:
        wheres.append('(username LIKE %s OR email LIKE %s)')
        params += [f'%{q}%', f'%{q}%']
    where_sql = ('WHERE ' + ' AND '.join(wheres)) if wheres else ''

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(f'SELECT COUNT(*) AS cnt FROM users {where_sql}', params)
        total = cursor.fetchone()['cnt']

        cursor.execute(
            f'''SELECT id, username, email, real_name, is_admin,
                       is_verified, is_deleted, created_at
                FROM users {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s''',
            params + [size, offset]
        )
        users = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'users':       users,
        'total':       total,
        'page':        page,
        'total_pages': (total + size - 1) // size
    })


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == g.user_id:
        return err('본인 계정은 여기서 삭제할 수 없습니다', 'CANNOT_SELF_DELETE')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE users SET is_deleted = 1, deleted_at = NOW() WHERE id = %s',
            (user_id,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return err('사용자를 찾을 수 없습니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok({}, '회원 탈퇴 처리 완료')


@admin_bp.route('/api/admin/users/<int:user_id>/admin', methods=['PATCH'])
@admin_required
def toggle_admin(user_id):
    data     = request.get_json() or {}
    is_admin = 1 if data.get('is_admin') else 0

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET is_admin = %s WHERE id = %s', (is_admin, user_id))
        conn.commit()
        if cursor.rowcount == 0:
            return err('사용자를 찾을 수 없습니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok({'is_admin': bool(is_admin)}, '권한 변경 완료')


# ── 게시글 관리 ──────────────────────────────────────────────────────

@admin_bp.route('/api/admin/posts', methods=['GET'])
@admin_required
def list_posts():
    page   = max(1, int(request.args.get('page', 1)))
    size   = max(1, min(100, int(request.args.get('size', 20))))
    offset = (page - 1) * size

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) AS cnt FROM posts')
        total = cursor.fetchone()['cnt']

        cursor.execute(
            '''SELECT p.id, p.title, p.type, p.view_count,
                      p.deleted_at, p.created_at,
                      u.username AS author
               FROM posts p
               JOIN users u ON p.user_id = u.id
               ORDER BY p.created_at DESC
               LIMIT %s OFFSET %s''',
            (size, offset)
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


@admin_bp.route('/api/admin/posts/<int:post_id>', methods=['DELETE'])
@admin_required
def admin_delete_post(post_id):
    hard = request.args.get('hard') == '1'

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if hard:
            cursor.execute('DELETE FROM posts WHERE id = %s', (post_id,))
        else:
            cursor.execute('UPDATE posts SET deleted_at = NOW() WHERE id = %s', (post_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok({}, '게시글 삭제 완료')


@admin_bp.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) AS cnt FROM users WHERE is_deleted = 0')
        user_count = cursor.fetchone()['cnt']
        cursor.execute('SELECT COUNT(*) AS cnt FROM posts WHERE deleted_at IS NULL')
        post_count = cursor.fetchone()['cnt']
        cursor.execute('SELECT COUNT(*) AS cnt FROM wiki_pages')
        wiki_count = cursor.fetchone()['cnt']
        cursor.execute('SELECT COUNT(*) AS cnt FROM clans')
        clan_count = cursor.fetchone()['cnt']
    finally:
        conn.close()

    return ok({
        'users': user_count,
        'posts': post_count,
        'wiki':  wiki_count,
        'clans': clan_count
    })
