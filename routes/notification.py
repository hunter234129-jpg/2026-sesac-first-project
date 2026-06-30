from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required

notification_bp = Blueprint('notification', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


# ── 키워드 구독 ──────────────────────────────────────────────────────

@notification_bp.route('/api/keywords', methods=['GET'])
@login_required
def get_keywords():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, keyword, created_at FROM keyword_subscriptions WHERE user_id = %s ORDER BY created_at DESC',
            (g.user_id,)
        )
        keywords = cursor.fetchall()
    finally:
        conn.close()

    return ok(keywords)


@notification_bp.route('/api/keywords', methods=['POST'])
@login_required
def add_keyword():
    data    = request.get_json() or {}
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return err('keyword는 필수입니다', 'MISSING_FIELDS')
    if len(keyword) > 100:
        return err('키워드는 100자 이하여야 합니다', 'TOO_LONG')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM keyword_subscriptions WHERE user_id = %s AND keyword = %s',
            (g.user_id, keyword)
        )
        if cursor.fetchone():
            return err('이미 등록된 키워드입니다', 'DUPLICATE', 409)

        cursor.execute(
            'INSERT INTO keyword_subscriptions (user_id, keyword) VALUES (%s, %s)',
            (g.user_id, keyword)
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({'id': new_id, 'keyword': keyword}, '키워드 등록 완료'), 201


@notification_bp.route('/api/keywords/<keyword>', methods=['DELETE'])
@login_required
def delete_keyword(keyword):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'DELETE FROM keyword_subscriptions WHERE user_id = %s AND keyword = %s',
            (g.user_id, keyword)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return err('등록된 키워드가 아닙니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok({}, '키워드 삭제 완료')


# ── 알림 ─────────────────────────────────────────────────────────────

@notification_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    page   = max(1, int(request.args.get('page', 1)))
    size   = max(1, min(50, int(request.args.get('size', 20))))
    offset = (page - 1) * size

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = %s',
            (g.user_id,)
        )
        total = cursor.fetchone()['cnt']

        cursor.execute(
            'SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = %s AND is_read = 0',
            (g.user_id,)
        )
        unread = cursor.fetchone()['cnt']

        cursor.execute(
            '''SELECT id, type, content, ref_type, ref_id, is_read, created_at
               FROM notifications
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s OFFSET %s''',
            (g.user_id, size, offset)
        )
        notifications = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'notifications': notifications,
        'unread':        unread,
        'total':         total,
        'page':          page,
        'total_pages':   (total + size - 1) // size
    })


@notification_bp.route('/api/notifications/<int:nid>/read', methods=['PATCH'])
@login_required
def mark_read(nid):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s',
            (nid, g.user_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return err('알림을 찾을 수 없습니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok({}, '읽음 처리 완료')


@notification_bp.route('/api/notifications/read-all', methods=['PATCH'])
@login_required
def mark_all_read():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE notifications SET is_read = 1 WHERE user_id = %s AND is_read = 0',
            (g.user_id,)
        )
        conn.commit()
        updated = cursor.rowcount
    finally:
        conn.close()

    return ok({'updated': updated}, '전체 읽음 처리 완료')
