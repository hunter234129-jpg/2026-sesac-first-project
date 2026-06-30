import re
import hashlib
from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required, decode_token

wiki_bp = Blueprint('wiki', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def make_slug(title):
    slug = re.sub(r'[^\w가-힣]+', '-', title.strip())
    return re.sub(r'-+', '-', slug).strip('-').lower()


def get_optional_user_id():
    """토큰이 있으면 user_id 반환, 없으면 None (공개 라우트 선택적 인증)"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        return decode_token(auth[7:])['user_id']
    except Exception:
        return None


@wiki_bp.route('/api/wiki', methods=['GET'])
def get_wiki_ranking():
    period = request.args.get('period', 'today')   # today | week
    limit  = min(50, int(request.args.get('limit', 10)))

    date_cond = 'DATE(v.viewed_at) = CURDATE()' if period == 'today' \
                else 'v.viewed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)'

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f'''SELECT w.id, w.title, w.slug, w.view_count, w.created_at,
                       COUNT(v.id) AS period_views
                FROM wiki_pages w
                LEFT JOIN wiki_view_logs v ON w.id = v.wiki_id AND {date_cond}
                GROUP BY w.id
                ORDER BY period_views DESC, w.view_count DESC
                LIMIT %s''',
            (limit,)
        )
        ranking = cursor.fetchall()

        cursor.execute(
            'SELECT id, title, slug, created_at FROM wiki_pages ORDER BY created_at DESC LIMIT 5'
        )
        recent = cursor.fetchall()
    finally:
        conn.close()

    return ok({'ranking': ranking, 'recent': recent})


@wiki_bp.route('/api/wiki/search', methods=['GET'])
def search_wiki():
    q = request.args.get('q', '').strip()
    if not q:
        return err('검색어를 입력해주세요', 'MISSING_QUERY')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, title, slug, view_count FROM wiki_pages WHERE title LIKE %s LIMIT 20',
            (f'%{q}%',)
        )
        results = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'results':    results,
        'can_create': not any(r['title'] == q for r in results)
    })


@wiki_bp.route('/api/wiki', methods=['POST'])
@login_required
def create_wiki():
    data    = request.get_json() or {}
    title   = data.get('title', '').strip()
    content = data.get('content', '')
    summary = data.get('summary', '최초 생성')

    if not title:
        return err('제목은 필수입니다', 'MISSING_TITLE')

    slug = make_slug(title)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM wiki_pages WHERE title = %s OR slug = %s',
            (title, slug)
        )
        if cursor.fetchone():
            return err('이미 존재하는 주제입니다', 'DUPLICATE', 409)

        cursor.execute(
            'INSERT INTO wiki_pages (title, slug, created_by) VALUES (%s, %s, %s)',
            (title, slug, g.user_id)
        )
        wiki_id = cursor.lastrowid

        cursor.execute(
            '''INSERT INTO wiki_revisions (wiki_id, author_id, content, summary, version)
               VALUES (%s, %s, %s, %s, 1)''',
            (wiki_id, g.user_id, content, summary)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({'id': wiki_id, 'slug': slug}, '위키 생성 완료'), 201


@wiki_bp.route('/api/wiki/<slug>', methods=['GET'])
def get_wiki(slug):
    user_id = get_optional_user_id()
    ip_hash = hashlib.md5((request.remote_addr or '').encode()).hexdigest()

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT w.id, w.title, w.slug, w.view_count, w.created_at,
                      u.username AS created_by,
                      r.id AS revision_id, r.content, r.version,
                      r.created_at AS last_updated,
                      ra.username  AS last_editor
               FROM wiki_pages w
               JOIN users u   ON w.created_by  = u.id
               JOIN wiki_revisions r  ON w.id  = r.wiki_id
               JOIN users ra  ON r.author_id   = ra.id
               WHERE w.slug = %s
               ORDER BY r.version DESC
               LIMIT 1''',
            (slug,)
        )
        wiki = cursor.fetchone()
        if not wiki:
            return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)

        wiki_id = wiki['id']

        # 1시간 이내 재방문 미집계
        if user_id:
            cursor.execute(
                '''SELECT id FROM wiki_view_logs
                   WHERE wiki_id = %s AND user_id = %s
                     AND viewed_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)''',
                (wiki_id, user_id)
            )
        else:
            cursor.execute(
                '''SELECT id FROM wiki_view_logs
                   WHERE wiki_id = %s AND ip_hash = %s
                     AND viewed_at > DATE_SUB(NOW(), INTERVAL 1 HOUR)''',
                (wiki_id, ip_hash)
            )

        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO wiki_view_logs (wiki_id, user_id, ip_hash) VALUES (%s, %s, %s)',
                (wiki_id, user_id, None if user_id else ip_hash)
            )
            cursor.execute(
                'UPDATE wiki_pages SET view_count = view_count + 1 WHERE id = %s',
                (wiki_id,)
            )
            conn.commit()
    finally:
        conn.close()

    return ok(wiki)


@wiki_bp.route('/api/wiki/<slug>', methods=['PUT'])
@login_required
def update_wiki(slug):
    data    = request.get_json() or {}
    content = data.get('content', '')
    summary = data.get('summary', '내용 수정')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM wiki_pages WHERE slug = %s', (slug,))
        wiki = cursor.fetchone()
        if not wiki:
            return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)

        wiki_id = wiki['id']
        cursor.execute(
            'SELECT MAX(version) AS max_ver FROM wiki_revisions WHERE wiki_id = %s',
            (wiki_id,)
        )
        next_ver = (cursor.fetchone()['max_ver'] or 0) + 1

        cursor.execute(
            '''INSERT INTO wiki_revisions (wiki_id, author_id, content, summary, version)
               VALUES (%s, %s, %s, %s, %s)''',
            (wiki_id, g.user_id, content, summary, next_ver)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({'version': next_ver}, '수정 완료')


@wiki_bp.route('/api/wiki/<slug>/history', methods=['GET'])
def get_wiki_history(slug):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM wiki_pages WHERE slug = %s', (slug,))
        wiki = cursor.fetchone()
        if not wiki:
            return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            '''SELECT r.id, r.version, r.summary, r.created_at,
                      u.username AS author
               FROM wiki_revisions r
               JOIN users u ON r.author_id = u.id
               WHERE r.wiki_id = %s
               ORDER BY r.version DESC''',
            (wiki['id'],)
        )
        history = cursor.fetchall()
    finally:
        conn.close()

    return ok(history)


@wiki_bp.route('/api/wiki/<slug>/rollback/<int:rev_id>', methods=['POST'])
@login_required
def rollback_wiki(slug, rev_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM wiki_pages WHERE slug = %s', (slug,))
        wiki = cursor.fetchone()
        if not wiki:
            return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)

        wiki_id = wiki['id']
        cursor.execute(
            'SELECT content, version FROM wiki_revisions WHERE id = %s AND wiki_id = %s',
            (rev_id, wiki_id)
        )
        rev = cursor.fetchone()
        if not rev:
            return err('해당 버전을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            'SELECT MAX(version) AS max_ver FROM wiki_revisions WHERE wiki_id = %s',
            (wiki_id,)
        )
        next_ver = (cursor.fetchone()['max_ver'] or 0) + 1

        cursor.execute(
            '''INSERT INTO wiki_revisions (wiki_id, author_id, content, summary, version)
               VALUES (%s, %s, %s, %s, %s)''',
            (wiki_id, g.user_id, rev['content'],
             f'v{rev["version"]}으로 롤백', next_ver)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({'version': next_ver}, f'v{rev["version"]}으로 롤백 완료')


@wiki_bp.route('/api/wiki/<slug>/drawing', methods=['GET'])
def get_wiki_drawing(slug):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT drawing_data FROM wiki_pages WHERE slug = %s', (slug,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)
    return ok({'drawing': row['drawing_data']})


@wiki_bp.route('/api/wiki/<slug>/drawing', methods=['PUT'])
@login_required
def save_wiki_drawing(slug):
    data    = request.get_json() or {}
    drawing = data.get('drawing')   # base64 data URL 또는 None(지우기)

    # 과도한 용량 방지 (~3MB)
    if drawing and len(drawing) > 3_000_000:
        return err('드로잉 데이터가 너무 큽니다', 'TOO_LARGE', 413)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM wiki_pages WHERE slug = %s', (slug,))
        if not cursor.fetchone():
            return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)
        cursor.execute(
            'UPDATE wiki_pages SET drawing_data = %s WHERE slug = %s',
            (drawing, slug)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({}, '드로잉 저장 완료')


@wiki_bp.route('/api/wiki/<slug>', methods=['DELETE'])
@login_required
def delete_wiki(slug):
    if not g.is_admin:
        return err('관리자만 삭제할 수 있습니다', 'FORBIDDEN', 403)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM wiki_pages WHERE slug = %s', (slug,))
        conn.commit()
        if cursor.rowcount == 0:
            return err('위키를 찾을 수 없습니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok({}, '삭제 완료')
