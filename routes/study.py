from flask import Blueprint, jsonify, request, g
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
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id FROM study_sessions WHERE user_id = %s AND ended_at IS NULL',
            (g.user_id,)
        )
        if cursor.fetchone():
            return err('이미 공부 중인 세션이 있습니다', 'SESSION_ACTIVE', 409)

        cursor.execute(
            'INSERT INTO study_sessions (user_id) VALUES (%s)',
            (g.user_id,)
        )
        conn.commit()
        session_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({'session_id': session_id}, '공부 시작'), 201


@study_bp.route('/api/study/end', methods=['POST'])
@login_required
def end_study():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, started_at FROM study_sessions WHERE user_id = %s AND ended_at IS NULL',
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
            '''SELECT id, started_at,
                      TIMESTAMPDIFF(SECOND, started_at, NOW()) AS elapsed_sec
               FROM study_sessions
               WHERE user_id = %s AND ended_at IS NULL''',
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
