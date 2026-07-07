from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required

mission_bp = Blueprint('mission', __name__)


# 랜덤 미션 풀 (날짜 기반으로 결정론적 선택 → 매일 1개 자동 생성)
MISSION_POOL = [
    ('오늘 목표 시간 채우기',   '계획한 공부 시간을 끝까지 채워보세요.'),
    ('게시글 1개 작성하기',     '학습 내용을 정리해 게시판에 공유해보세요.'),
    ('위키 문서 기여하기',      '위키 문서를 하나 만들거나 수정해보세요.'),
    ('오답 노트 정리하기',      '틀린 문제를 다시 풀고 정리해보세요.'),
    ('25분 집중 + 5분 휴식',    '뽀모도로 1세트를 완수해보세요.'),
    ('새 키워드 등록하기',      '관심 분야 키워드를 등록해 알림을 받아보세요.'),
    ('모임원과 함께 공부하기',  '가입한 모임 멤버와 같은 시간에 공부해보세요.'),
]


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def ensure_today_mission(cursor):
    """오늘의 미션이 없으면 풀에서 결정론적으로 1개 생성하고 id 반환"""
    cursor.execute('SELECT id FROM missions WHERE date = CURDATE() AND is_random = 1')
    row = cursor.fetchone()
    if row:
        return row['id']

    # CURDATE() 기반 인덱스 → 같은 날 항상 동일 미션
    cursor.execute('SELECT TO_DAYS(CURDATE()) AS d')
    idx     = cursor.fetchone()['d'] % len(MISSION_POOL)
    title, content = MISSION_POOL[idx]

    cursor.execute(
        'INSERT INTO missions (title, content, date, is_random) VALUES (%s, %s, CURDATE(), 1)',
        (title, content)
    )
    return cursor.lastrowid


@mission_bp.route('/api/missions/today', methods=['GET'])
@login_required
def get_today_mission():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        mission_id = ensure_today_mission(cursor)
        conn.commit()

        cursor.execute(
            '''SELECT m.id, m.title, m.content, m.date,
                      COALESCE(um.is_done, 0) AS is_done,
                      um.done_at
               FROM missions m
               LEFT JOIN user_missions um
                 ON m.id = um.mission_id AND um.user_id = %s
               WHERE m.id = %s''',
            (g.user_id, mission_id)
        )
        mission = cursor.fetchone()
    finally:
        conn.close()

    return ok(mission)


@mission_bp.route('/api/missions/<int:mission_id>/done', methods=['POST'])
@login_required
def complete_mission(mission_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM missions WHERE id = %s', (mission_id,))
        if not cursor.fetchone():
            return err('미션을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            '''INSERT INTO user_missions (user_id, mission_id, is_done, done_at)
               VALUES (%s, %s, 1, NOW())
               ON DUPLICATE KEY UPDATE is_done = 1, done_at = NOW()''',
            (g.user_id, mission_id)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({}, '미션 완료')


@mission_bp.route('/api/missions/history', methods=['GET'])
@login_required
def mission_history():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT m.id, m.title, m.date, um.is_done, um.done_at
               FROM user_missions um
               JOIN missions m ON um.mission_id = m.id
               WHERE um.user_id = %s AND um.is_done = 1
               ORDER BY um.done_at DESC
               LIMIT 30''',
            (g.user_id,)
        )
        history = cursor.fetchall()
    finally:
        conn.close()

    return ok(history)
