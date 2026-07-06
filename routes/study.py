from flask import Blueprint, jsonify, request, g
from datetime import timedelta
from db.connection import get_db
from utils.auth import login_required

study_bp = Blueprint('study', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@study_bp.route('/api/study/start', methods=['POST'])
@login_required
def start_study():
    data    = request.get_json(silent=True) or {}
    post_id = data.get('post_id')  # 이 세션 공부 시간을 기여도로 반영할 모임(선택, 없으면 개인 공부)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM study_sessions WHERE user_id = %s AND ended_at IS NULL',
            (g.user_id,)
        )
        if cursor.fetchone():
            return err('이미 공부 중인 세션이 있습니다', 'SESSION_ACTIVE', 409)

        if post_id is not None:
            cursor.execute(
                "SELECT 1 FROM post_members WHERE post_id = %s AND user_id = %s "
                "AND status = 'active' AND left_at IS NULL",
                (post_id, g.user_id)
            )
            if not cursor.fetchone():
                return err('가입된 모임이 아닙니다', 'NOT_MEMBER', 404)

        cursor.execute(
            'INSERT INTO study_sessions (user_id, post_id) VALUES (%s, %s)',
            (g.user_id, post_id)
        )
        conn.commit()
        session_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({'session_id': session_id, 'post_id': post_id}, '공부 시작'), 201


@study_bp.route('/api/study/end', methods=['POST'])
@login_required
def end_study():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, started_at, post_id FROM study_sessions WHERE user_id = %s AND ended_at IS NULL',
            (g.user_id,)
        )
        session = cursor.fetchone()
        if not session:
            return err('진행 중인 세션이 없습니다', 'NO_ACTIVE_SESSION', 404)

        cursor.execute(
            '''UPDATE study_sessions
               SET ended_at     = NOW(),
                   duration_sec = TIMESTAMPDIFF(SECOND, started_at, NOW())
               WHERE id = %s''',
            (session['id'],)
        )
        conn.commit()

        cursor.execute('SELECT duration_sec FROM study_sessions WHERE id = %s', (session['id'],))
        duration = cursor.fetchone()['duration_sec']

        # 모임 기여도 누적 (분 단위) — 공부 시작 시 선택한 모임에만 반영(선택 안 했으면 개인 기록만 남음)
        mins = (duration or 0) // 60
        if mins > 0 and session['post_id'] is not None:
            cursor.execute(
                "UPDATE post_members SET contribution_score = contribution_score + %s "
                "WHERE post_id = %s AND user_id = %s AND status = 'active' AND left_at IS NULL",
                (mins, session['post_id'], g.user_id)
            )
            conn.commit()
    finally:
        conn.close()

    return ok({'duration_sec': duration}, '공부 종료')


@study_bp.route('/api/study/status', methods=['GET'])
@login_required
def study_status():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT s.id, s.started_at, s.post_id, p.title AS post_title,
                      TIMESTAMPDIFF(SECOND, s.started_at, NOW()) AS elapsed_sec
               FROM study_sessions s
               LEFT JOIN posts p ON s.post_id = p.id
               WHERE s.user_id = %s AND s.ended_at IS NULL''',
            (g.user_id,)
        )
        session = cursor.fetchone()
    finally:
        conn.close()

    return ok({'active': session is not None, 'session': session})


@study_bp.route('/api/study/stats', methods=['GET'])
@login_required
def study_stats():
    period = request.args.get('period', 'day')   # day | week

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if period == 'week':
            cursor.execute(
                '''SELECT YEARWEEK(started_at, 1)      AS period_key,
                          MIN(DATE(started_at))         AS week_start,
                          SUM(duration_sec)             AS total_sec,
                          COUNT(*)                      AS session_count
                   FROM study_sessions
                   WHERE user_id = %s
                     AND ended_at IS NOT NULL
                     AND started_at >= DATE_SUB(NOW(), INTERVAL 8 WEEK)
                   GROUP BY period_key
                   ORDER BY period_key DESC
                   LIMIT 8''',
                (g.user_id,)
            )
        else:
            cursor.execute(
                '''SELECT DATE(started_at)  AS period_key,
                          SUM(duration_sec) AS total_sec,
                          COUNT(*)          AS session_count
                   FROM study_sessions
                   WHERE user_id = %s
                     AND ended_at IS NOT NULL
                     AND started_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                   GROUP BY period_key
                   ORDER BY period_key DESC''',
                (g.user_id,)
            )
        stats = cursor.fetchall()

        cursor.execute(
            '''SELECT SUM(duration_sec) AS total_sec, COUNT(*) AS session_count
               FROM study_sessions
               WHERE user_id = %s AND ended_at IS NOT NULL''',
            (g.user_id,)
        )
        total = cursor.fetchone()
    finally:
        conn.close()

    return ok({'stats': stats, 'total': total, 'period': period})


@study_bp.route('/api/study/ranking', methods=['GET'])
def study_ranking():
    period = request.args.get('period', 'today')   # today | week | all
    limit  = min(50, int(request.args.get('limit', 10)))

    if period == 'today':
        date_cond = 'AND DATE(s.started_at) = CURDATE()'
    elif period == 'week':
        date_cond = 'AND s.started_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)'
    else:
        date_cond = ''

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f'''SELECT u.id, u.username,
                       SUM(s.duration_sec)  AS total_sec,
                       COUNT(s.id)          AS session_count
                FROM study_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.ended_at IS NOT NULL
                  AND u.is_deleted = 0
                  {date_cond}
                GROUP BY u.id
                ORDER BY total_sec DESC
                LIMIT %s''',
            (limit,)
        )
        ranking = cursor.fetchall()
    finally:
        conn.close()

    return ok({'ranking': ranking, 'period': period})


# ── 연속 공부(스트릭) ──────────────────────────────────────────────
@study_bp.route('/api/study/streak', methods=['GET'])
@login_required
def study_streak():
    """현재 연속일·최장 연속일·오늘 공부 여부를 계산해서 반환."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT CURDATE() AS today')
        today = cursor.fetchone()['today']            # datetime.date (서버 기준)

        # 진행 중인 세션도 '오늘 공부'로 인정 (스트릭이 공부 중에 끊겨 보이지 않도록)
        cursor.execute(
            'SELECT COUNT(*) AS c FROM study_sessions WHERE user_id = %s AND ended_at IS NULL',
            (g.user_id,)
        )
        active_now = cursor.fetchone()['c'] > 0

        cursor.execute(
            '''SELECT DISTINCT DATE(started_at) AS d
               FROM study_sessions
               WHERE user_id = %s AND ended_at IS NOT NULL AND duration_sec > 0''',
            (g.user_id,)
        )
        dayset = {row['d'] for row in cursor.fetchall()}
    finally:
        conn.close()

    if active_now:
        dayset.add(today)

    one           = timedelta(days=1)
    studied_today = today in dayset

    # 현재 연속: 오늘 했으면 오늘부터, 아니면 어제부터(아직 오늘이 안 지났으므로 유지) 거슬러 카운트
    if today in dayset:
        anchor = today
    elif (today - one) in dayset:
        anchor = today - one
    else:
        anchor = None

    current = 0
    cur_day = anchor
    while cur_day is not None and cur_day in dayset:
        current += 1
        cur_day -= one

    # 최장 연속
    longest = 0
    if dayset:
        ordered = sorted(dayset)
        run = longest = 1
        for i in range(1, len(ordered)):
            run = run + 1 if ordered[i] - ordered[i - 1] == one else 1
            longest = max(longest, run)

    return ok({
        'current_streak': current,
        'longest_streak': longest,
        'studied_today':  studied_today,
        'total_days':     len(dayset),
    })


# ── 하루 목표 공부 시간(잔디/타이머 링 기준) ────────────────────────
MIN_GOAL_MIN = 10     # 10분
MAX_GOAL_MIN = 720    # 12시간


@study_bp.route('/api/study/goal', methods=['GET'])
@login_required
def get_goal():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT daily_goal_min FROM users WHERE id = %s', (g.user_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    return ok({'daily_goal_min': row['daily_goal_min'] if row else 240})


@study_bp.route('/api/study/goal', methods=['PUT'])
@login_required
def set_goal():
    data    = request.get_json(silent=True) or {}
    minutes = data.get('daily_goal_min')
    if not isinstance(minutes, int) or not (MIN_GOAL_MIN <= minutes <= MAX_GOAL_MIN):
        return err(f'목표 시간은 {MIN_GOAL_MIN}~{MAX_GOAL_MIN}분 사이여야 합니다', 'INVALID_GOAL')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET daily_goal_min = %s WHERE id = %s', (minutes, g.user_id))
        conn.commit()
    finally:
        conn.close()

    return ok({'daily_goal_min': minutes})


# ── 공부 잔디(히트맵) ──────────────────────────────────────────────
@study_bp.route('/api/study/heatmap', methods=['GET'])
@login_required
def study_heatmap():
    """최근 N일간 날짜별 공부 시간 합계 (기본 119일 ≒ 17주)."""
    days = min(371, max(7, int(request.args.get('days', 119))))

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT daily_goal_min FROM users WHERE id = %s', (g.user_id,))
        goal_row = cursor.fetchone()

        cursor.execute(
            '''SELECT DATE(started_at) AS d,
                      SUM(duration_sec) AS total_sec,
                      COUNT(*)          AS sessions
               FROM study_sessions
               WHERE user_id = %s
                 AND ended_at IS NOT NULL
                 AND started_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
               GROUP BY d''',
            (g.user_id, days)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    daily_goal_min = goal_row['daily_goal_min'] if goal_row else 240
    data = [{
        'date':      str(r['d']),
        'total_sec': int(r['total_sec'] or 0),
        'sessions':  r['sessions'],
    } for r in rows]
    return ok({'days': data, 'range_days': days, 'daily_goal_min': daily_goal_min})


# ── 실시간 공부 인원 ───────────────────────────────────────────────
@study_bp.route('/api/study/live', methods=['GET'])
def study_live():
    """지금 공부 중(진행 세션 보유)인 사람 수와 일부 명단. 비회원도 조회 가능."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT u.username,
                      TIMESTAMPDIFF(SECOND, s.started_at, NOW()) AS elapsed_sec
               FROM study_sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.ended_at IS NULL
                 AND s.started_at >= DATE_SUB(NOW(), INTERVAL 12 HOUR)
                 AND u.is_deleted = 0
               ORDER BY s.started_at ASC'''
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return ok({
        'count': len(rows),
        'users': [{'username': r['username'], 'elapsed_sec': r['elapsed_sec']} for r in rows[:12]],
    })


# ── 내 행성(공부 시간 기반 성장 단계) ──────────────────────────────
PLANET_STAGES = [
    {'level': 0, 'name': '성운',       'emoji': '🌫️', 'min_hours': 0,    'desc': '먼지와 가스가 모이기 시작했어요.'},
    {'level': 1, 'name': '소행성',     'emoji': '☄️', 'min_hours': 5,    'desc': '작은 바위 덩어리가 됐어요.'},
    {'level': 2, 'name': '위성',       'emoji': '🌑', 'min_hours': 20,   'desc': '중력이 생겨 둥글어졌어요.'},
    {'level': 3, 'name': '행성',       'emoji': '🪐', 'min_hours': 50,   'desc': '어엿한 행성으로 자랐어요.'},
    {'level': 4, 'name': '생명의 행성', 'emoji': '🌍', 'min_hours': 100,  'desc': '바다와 대기가 생겼어요.'},
    {'level': 5, 'name': '고리 행성',   'emoji': '🪐', 'min_hours': 200,  'desc': '아름다운 고리를 둘렀어요.'},
    {'level': 6, 'name': '항성',       'emoji': '☀️', 'min_hours': 400,  'desc': '스스로 빛나기 시작했어요.'},
    {'level': 7, 'name': '초신성',     'emoji': '🌟', 'min_hours': 700,  'desc': '폭발적인 에너지를 내뿜어요.'},
    {'level': 8, 'name': '은하',       'emoji': '🌌', 'min_hours': 1000, 'desc': '하나의 은하가 됐어요. 전설!'},
]


@study_bp.route('/api/study/planet', methods=['GET'])
@login_required
def study_planet():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT COALESCE(SUM(duration_sec), 0) AS total_sec
               FROM study_sessions
               WHERE user_id = %s AND ended_at IS NOT NULL''',
            (g.user_id,)
        )
        total_sec = int(cursor.fetchone()['total_sec'] or 0)
    finally:
        conn.close()

    hours = total_sec / 3600
    cur, nxt = PLANET_STAGES[0], None
    for i, st in enumerate(PLANET_STAGES):
        if hours >= st['min_hours']:
            cur = st
            nxt = PLANET_STAGES[i + 1] if i + 1 < len(PLANET_STAGES) else None

    if nxt is None:
        progress, hours_to_next = 1.0, 0
    else:
        span          = nxt['min_hours'] - cur['min_hours']
        progress      = min(1.0, (hours - cur['min_hours']) / span) if span else 1.0
        hours_to_next = max(0, nxt['min_hours'] - hours)

    return ok({
        'total_sec':      total_sec,
        'total_hours':    round(hours, 1),
        'level':          cur['level'],
        'name':           cur['name'],
        'emoji':          cur['emoji'],
        'desc':           cur['desc'],
        'is_max':         nxt is None,
        'next_name':      nxt['name'] if nxt else None,
        'next_min_hours': nxt['min_hours'] if nxt else None,
        'hours_to_next':  round(hours_to_next, 1),
        'progress':       round(progress, 3),
        'stages':         PLANET_STAGES,
    })
