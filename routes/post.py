from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required
from utils.notify import notify_keyword_match

post_bp = Blueprint('post', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@post_bp.route('/api/posts', methods=['GET'])
def get_posts():
    page     = max(1, int(request.args.get('page', 1)))
    size     = max(1, min(50, int(request.args.get('size', 10))))
    category = request.args.get('category', '')
    q        = request.args.get('q', '')
    sort     = request.args.get('sort', 'latest')   # latest | views
    type_    = request.args.get('type', '')          # post | study
    offset   = (page - 1) * size

    wheres, params = ['p.deleted_at IS NULL'], []
    if category:
        wheres.append('p.category = %s')
        params.append(category)
    if q:
        wheres.append('(p.title LIKE %s OR p.content LIKE %s)')
        params += [f'%{q}%', f'%{q}%']
    if type_:
        wheres.append('p.type = %s')
        params.append(type_)

    where_sql = 'WHERE ' + ' AND '.join(wheres)
    order_sql = 'ORDER BY p.view_count DESC' if sort == 'views' else 'ORDER BY p.created_at DESC'

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f'SELECT COUNT(*) AS cnt FROM posts p {where_sql}',
            params
        )
        total = cursor.fetchone()['cnt']

        cursor.execute(
            f'''SELECT p.id, p.title, p.type, p.category, p.status,
                       p.view_count, p.recruit_count, p.field,
                       p.recruit_deadline, p.created_at,
                       u.username AS author
                FROM posts p
                JOIN users u ON p.user_id = u.id
                {where_sql} {order_sql}
                LIMIT %s OFFSET %s''',
            params + [size, offset]
        )
        posts = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'posts':       posts,
        'total':       total,
        'page':        page,
        'size':        size,
        'total_pages': (total + size - 1) // size
    })


@post_bp.route('/api/posts', methods=['POST'])
@login_required
def create_post():
    data             = request.get_json() or {}
    title            = data.get('title', '').strip()
    content          = data.get('content', '')
    type_            = data.get('type', 'post')
    category         = data.get('category', '')
    recruit_count    = data.get('recruit_count', 0)
    recruit_deadline = data.get('recruit_deadline')
    field            = data.get('field', '')

    if not title:
        return err('제목은 필수입니다', 'MISSING_TITLE')
    if type_ not in ('post', 'study'):
        return err('type은 post 또는 study여야 합니다', 'INVALID_TYPE')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''INSERT INTO posts
               (user_id, title, content, type, category, recruit_count, recruit_deadline, field)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (g.user_id, title, content, type_, category,
             recruit_count, recruit_deadline, field)
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    notify_keyword_match(get_db, new_id, title, content or '')
    return ok({'id': new_id}, '등록 완료'), 201


@post_bp.route('/api/posts/<int:id>', methods=['GET'])
def get_post(id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE posts SET view_count = view_count + 1 WHERE id = %s', (id,)
        )
        conn.commit()
        cursor.execute(
            '''SELECT p.*, u.username AS author
               FROM posts p
               JOIN users u ON p.user_id = u.id
               WHERE p.id = %s AND p.deleted_at IS NULL''',
            (id,)
        )
        post = cursor.fetchone()
    finally:
        conn.close()

    if not post:
        return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
    return ok(post)


@post_bp.route('/api/posts/<int:id>', methods=['PUT'])
@login_required
def update_post(id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id FROM posts WHERE id = %s', (id,))
        post = cursor.fetchone()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if post['user_id'] != g.user_id:
            return err('본인 글만 수정할 수 있습니다', 'FORBIDDEN', 403)

        data             = request.get_json() or {}
        updates, params  = [], []

        if data.get('title'):
            updates.append('title = %s')
            params.append(data['title'])
        if 'content' in data:
            updates.append('content = %s')
            params.append(data['content'])
        if data.get('category') is not None:
            updates.append('category = %s')
            params.append(data['category'])
        if 'recruit_count' in data:
            updates.append('recruit_count = %s')
            params.append(int(data['recruit_count'] or 0))
        if 'recruit_deadline' in data:
            updates.append('recruit_deadline = %s')
            params.append(data['recruit_deadline'] or None)
        if 'field' in data:
            updates.append('field = %s')
            params.append(data['field'] or None)

        if updates:
            params.append(id)
            cursor.execute(
                f'UPDATE posts SET {", ".join(updates)} WHERE id = %s',
                params
            )
            conn.commit()
    finally:
        conn.close()

    return ok({}, '수정 완료')


@post_bp.route('/api/posts/<int:id>', methods=['DELETE'])
@login_required
def delete_post(id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id FROM posts WHERE id = %s', (id,))
        post = cursor.fetchone()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if post['user_id'] != g.user_id:
            return err('본인 글만 삭제할 수 있습니다', 'FORBIDDEN', 403)
        cursor.execute('UPDATE posts SET deleted_at = NOW() WHERE id = %s', (id,))
        conn.commit()
    finally:
        conn.close()

    return ok({}, '삭제 완료')


@post_bp.route('/api/posts/<int:id>/status', methods=['PATCH'])
@login_required
def update_study_status(id):
    data   = request.get_json() or {}
    status = data.get('status')

    if status not in ('open', 'closed'):
        return err('status는 open 또는 closed여야 합니다', 'INVALID_STATUS')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, type FROM posts WHERE id = %s', (id,))
        post = cursor.fetchone()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if post['user_id'] != g.user_id:
            return err('본인 글만 수정할 수 있습니다', 'FORBIDDEN', 403)
        if post['type'] != 'study':
            return err('스터디 모집글에만 사용 가능합니다', 'INVALID_TYPE')
        cursor.execute('UPDATE posts SET status = %s WHERE id = %s', (status, id))
        conn.commit()
    finally:
        conn.close()

    return ok({}, '상태 변경 완료')
