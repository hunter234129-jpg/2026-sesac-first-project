from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required

comment_bp = Blueprint('comment', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@comment_bp.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT c.id, c.content, c.parent_id, c.created_at, c.updated_at,
                      u.id AS user_id, u.username
               FROM comments c
               JOIN users u ON c.user_id = u.id
               WHERE c.post_id = %s
               ORDER BY c.created_at ASC''',
            (post_id,)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    # 부모-자식 트리 구조 변환
    by_id     = {r['id']: {**r, 'replies': []} for r in rows}
    top_level = []
    for c in by_id.values():
        if c['parent_id'] and c['parent_id'] in by_id:
            by_id[c['parent_id']]['replies'].append(c)
        else:
            top_level.append(c)

    return ok(top_level)


@comment_bp.route('/api/posts/<int:post_id>/comments', methods=['POST'])
@login_required
def create_comment(post_id):
    data      = request.get_json() or {}
    content   = data.get('content', '').strip()
    parent_id = data.get('parent_id')

    if not content:
        return err('내용은 필수입니다', 'MISSING_CONTENT')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM posts WHERE id = %s', (post_id,))
        if not cursor.fetchone():
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            'INSERT INTO comments (post_id, user_id, content, parent_id) VALUES (%s, %s, %s, %s)',
            (post_id, g.user_id, content, parent_id)
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({'id': new_id}, '등록 완료'), 201


@comment_bp.route('/api/posts/<int:post_id>/comments/<int:cid>', methods=['PUT'])
@login_required
def update_comment(post_id, cid):
    data    = request.get_json() or {}
    content = data.get('content', '').strip()

    if not content:
        return err('내용은 필수입니다', 'MISSING_CONTENT')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT user_id FROM comments WHERE id = %s AND post_id = %s',
            (cid, post_id)
        )
        comment = cursor.fetchone()
        if not comment:
            return err('댓글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if comment['user_id'] != g.user_id:
            return err('본인 댓글만 수정할 수 있습니다', 'FORBIDDEN', 403)

        cursor.execute('UPDATE comments SET content = %s WHERE id = %s', (content, cid))
        conn.commit()
    finally:
        conn.close()

    return ok({}, '수정 완료')


@comment_bp.route('/api/posts/<int:post_id>/comments/<int:cid>', methods=['DELETE'])
@login_required
def delete_comment(post_id, cid):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT user_id FROM comments WHERE id = %s AND post_id = %s',
            (cid, post_id)
        )
        comment = cursor.fetchone()
        if not comment:
            return err('댓글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if comment['user_id'] != g.user_id:
            return err('본인 댓글만 삭제할 수 있습니다', 'FORBIDDEN', 403)

        cursor.execute('DELETE FROM comments WHERE id = %s', (cid,))
        conn.commit()
    finally:
        conn.close()

    return ok({}, '삭제 완료')
