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
                       p.view_count, p.recruit_count, p.field, p.linked_exam_name,
                       p.recruit_deadline, p.created_at,
                       u.username AS author,
                       (SELECT COUNT(*) FROM post_members pm
                         WHERE pm.post_id = p.id AND pm.left_at IS NULL) AS member_count
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

    # 스터디 모집글(=모임)이 특정 시험과 연동되는 경우(선택) — 작성 화면에서 후보를
    # 검색해 보여주고 작성자가 직접 고른 이름을 그대로 받는다. exams에 실제로
    # 존재하는 이름인지만 확인해서 오타나 조작된 값으로 엉뚱하게 연결되는 걸 막는다.
    linked_exam_name = (data.get('linked_exam_name') or '').strip() or None

    if not title:
        return err('제목은 필수입니다', 'MISSING_TITLE')
    if type_ not in ('post', 'study'):
        return err('type은 post 또는 study여야 합니다', 'INVALID_TYPE')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if linked_exam_name is not None:
            cursor.execute('SELECT 1 FROM exams WHERE name = %s LIMIT 1', (linked_exam_name,))
            if not cursor.fetchone():
                return err('연결하려는 시험 정보를 찾을 수 없습니다', 'EXAM_NOT_FOUND', 404)

        cursor.execute(
            '''INSERT INTO posts
               (user_id, title, content, type, category, recruit_count, recruit_deadline,
                field, linked_exam_name)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (g.user_id, title, content, type_, category,
             recruit_count, recruit_deadline, field, linked_exam_name)
        )
        new_id = cursor.lastrowid

        # 스터디 모집글은 곧 모임이므로, 작성자는 자동으로 첫 멤버로 등록된다.
        if type_ == 'study':
            cursor.execute(
                'INSERT INTO post_members (post_id, user_id) VALUES (%s, %s)',
                (new_id, g.user_id)
            )
        conn.commit()
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
            '''SELECT p.*, u.username AS author,
                      (SELECT COUNT(*) FROM post_members pm
                        WHERE pm.post_id = p.id AND pm.left_at IS NULL) AS member_count
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
        if 'linked_exam_name' in data:
            linked_exam_name = (data.get('linked_exam_name') or '').strip() or None
            if linked_exam_name is not None:
                cursor.execute('SELECT 1 FROM exams WHERE name = %s LIMIT 1', (linked_exam_name,))
                if not cursor.fetchone():
                    return err('연결하려는 시험 정보를 찾을 수 없습니다', 'EXAM_NOT_FOUND', 404)
            updates.append('linked_exam_name = %s')
            params.append(linked_exam_name)

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


# ---- 모임(구 클랜) 멤버십 + 그룹 채팅 -------------------------------------
# 스터디 모집글(type='study')이 성사되면 그 자체가 모임이 된다. 별도의
# "성사됨" 상태 플래그 없이, 글쓴이 외 첫 멤버가 들어오는 순간부터 채팅이
# 열리는 방식으로 단순화했다(클랜 기능 통합 이전에는 클랜 따로/모집글 따로였음).

@post_bp.route('/api/posts/<int:id>/members', methods=['GET'])
def get_post_members(id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, type FROM posts WHERE id = %s AND deleted_at IS NULL', (id,))
        post = cursor.fetchone()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if post['type'] != 'study':
            return err('스터디 모집글에만 사용 가능합니다', 'INVALID_TYPE')

        cursor.execute(
            '''SELECT u.id, u.username, pm.contribution_score, pm.joined_at
               FROM post_members pm
               JOIN users u ON pm.user_id = u.id
               WHERE pm.post_id = %s AND pm.left_at IS NULL AND u.is_deleted = 0
               ORDER BY pm.contribution_score DESC''',
            (id,)
        )
        members = cursor.fetchall()
    finally:
        conn.close()

    return ok(members)


@post_bp.route('/api/posts/<int:id>/chat', methods=['GET'])
@login_required
def get_post_chat(id):
    """모임 그룹 채팅 기록(영구 보존, 페이지네이션). 한 번이라도 멤버였던 사람만
    조회 가능하고, 탈퇴한 사람은 자기가 나간 시점까지만 보인다(그 이후는 비공개)."""
    before = request.args.get('before', type=int)   # 이 메시지 id보다 이전 것만(더 불러오기)
    size   = max(1, min(100, request.args.get('size', 50, type=int)))

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT left_at FROM post_members WHERE post_id = %s AND user_id = %s',
            (id, g.user_id)
        )
        member = cursor.fetchone()
        if not member:
            return err('모임 멤버만 채팅 기록을 볼 수 있습니다', 'NOT_MEMBER', 403)

        # pm.id/pm.created_at처럼 테이블 별칭을 꼭 붙여야 한다 — users에도 id/created_at이
        # 있어서 별칭 없이 쓰면 "Ambiguous column" SQL 에러가 난다.
        wheres, params = ['pm.post_id = %s'], [id]
        if member['left_at']:
            wheres.append('pm.created_at <= %s')
            params.append(member['left_at'])
        if before:
            wheres.append('pm.id < %s')
            params.append(before)

        cursor.execute(
            f'''SELECT pm.id, pm.sender_id, u.username, u.avatar_id, pm.msg_type, pm.content,
                       pm.file_url, pm.file_name, pm.file_size, pm.mime_type, pm.created_at
                FROM post_chat_messages pm
                LEFT JOIN users u ON pm.sender_id = u.id
                WHERE {" AND ".join(wheres)}
                ORDER BY pm.id DESC LIMIT %s''',
            params + [size]
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    rows = list(reversed(rows))  # cursor.fetchall()은 튜플을 반환해서 in-place reverse()가 안 됨. 오래된 순으로 정렬
    return ok({'messages': rows, 'is_active_member': member['left_at'] is None,
               'has_more': len(rows) == size})


@post_bp.route('/api/posts/<int:id>/join', methods=['POST'])
@login_required
def join_post(id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, type FROM posts WHERE id = %s AND deleted_at IS NULL', (id,))
        post = cursor.fetchone()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if post['type'] != 'study':
            return err('스터디 모집글에만 사용 가능합니다', 'INVALID_TYPE')

        # 탈퇴는 소프트 삭제(left_at)라, 과거에 가입했다 나간 적 있는 유저는
        # post_members 행이 이미 남아 있다 — 재가입이면 UPDATE, 처음이면 INSERT.
        cursor.execute(
            'SELECT left_at FROM post_members WHERE post_id = %s AND user_id = %s',
            (id, g.user_id)
        )
        existing = cursor.fetchone()
        if existing and existing['left_at'] is None:
            return err('이미 가입된 모임입니다', 'ALREADY_JOINED', 409)

        if existing:
            cursor.execute(
                'UPDATE post_members SET left_at = NULL, joined_at = NOW() '
                'WHERE post_id = %s AND user_id = %s',
                (id, g.user_id)
            )
        else:
            cursor.execute(
                'INSERT INTO post_members (post_id, user_id) VALUES (%s, %s)',
                (id, g.user_id)
            )
        conn.commit()
    finally:
        conn.close()

    from sockets.post_chat_events import post_system_message
    post_system_message(id, f'{g.username}님이 들어왔습니다.')

    return ok({}, '모임 가입 완료'), 201


@post_bp.route('/api/posts/<int:id>/leave', methods=['DELETE'])
@login_required
def leave_post(id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id FROM posts WHERE id = %s', (id,))
        post = cursor.fetchone()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if post['user_id'] == g.user_id:
            return err('모임장은 탈퇴할 수 없습니다. 게시글을 삭제해주세요', 'LEADER_CANNOT_LEAVE', 400)

        # 하드 삭제 대신 left_at만 기록(소프트 삭제) — 탈퇴 시점 이전 채팅 기록은
        # 계속 볼 수 있게 하고, 그 이후 메시지만 안 보이게 하기 위한 기준점.
        cursor.execute(
            'UPDATE post_members SET left_at = NOW() '
            'WHERE post_id = %s AND user_id = %s AND left_at IS NULL',
            (id, g.user_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return err('가입된 모임이 아닙니다', 'NOT_MEMBER', 404)
    finally:
        conn.close()

    from sockets.post_chat_events import post_system_message
    from extensions import socketio
    post_system_message(id, f'{g.username}님이 나갔습니다.')
    # 탈퇴한 순간부터는 실시간 메시지를 더 받으면 안 되므로 강제로 소켓 room에서 내보낸다
    # (본인이 열어둔 다른 탭까지 전부 — user_{id} room은 chat_events.py가 접속 시 join해둠).
    socketio.emit('post_kicked', {'post_id': id}, room=f'user_{g.user_id}')

    return ok({}, '모임 탈퇴 완료')
