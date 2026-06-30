from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required

clan_bp = Blueprint('clan', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@clan_bp.route('/api/clans', methods=['GET'])
def get_clans():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT c.id, c.name, c.description, c.created_at,
                      u.username AS leader,
                      COUNT(cm.user_id)              AS member_count,
                      COALESCE(SUM(cm.contribution_score), 0) AS total_score
               FROM clans c
               JOIN users u ON c.leader_id = u.id
               LEFT JOIN clan_members cm ON c.id = cm.clan_id
               GROUP BY c.id
               ORDER BY total_score DESC''',
        )
        clans = cursor.fetchall()
    finally:
        conn.close()

    return ok(clans)


@clan_bp.route('/api/clans', methods=['POST'])
@login_required
def create_clan():
    data        = request.get_json() or {}
    name        = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return err('클랜 이름은 필수입니다', 'MISSING_FIELDS')
    if len(name) > 100:
        return err('클랜 이름은 100자 이하여야 합니다', 'TOO_LONG')

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM clans WHERE name = %s', (name,))
        if cursor.fetchone():
            return err('이미 존재하는 클랜 이름입니다', 'DUPLICATE', 409)

        cursor.execute(
            'INSERT INTO clans (name, description, leader_id) VALUES (%s, %s, %s)',
            (name, description or None, g.user_id)
        )
        clan_id = cursor.lastrowid

        # 생성자는 자동으로 멤버 등록
        cursor.execute(
            'INSERT INTO clan_members (clan_id, user_id) VALUES (%s, %s)',
            (clan_id, g.user_id)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({'id': clan_id, 'name': name}, '클랜 생성 완료'), 201


@clan_bp.route('/api/clans/<int:clan_id>', methods=['GET'])
def get_clan(clan_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT c.id, c.name, c.description, c.created_at,
                      u.username AS leader,
                      COUNT(cm.user_id)                       AS member_count,
                      COALESCE(SUM(cm.contribution_score), 0) AS total_score
               FROM clans c
               JOIN users u ON c.leader_id = u.id
               LEFT JOIN clan_members cm ON c.id = cm.clan_id
               WHERE c.id = %s
               GROUP BY c.id''',
            (clan_id,)
        )
        clan = cursor.fetchone()
        if not clan:
            return err('클랜을 찾을 수 없습니다', 'NOT_FOUND', 404)
    finally:
        conn.close()

    return ok(clan)


@clan_bp.route('/api/clans/<int:clan_id>/members', methods=['GET'])
def get_clan_members(clan_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM clans WHERE id = %s', (clan_id,))
        if not cursor.fetchone():
            return err('클랜을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            '''SELECT u.id, u.username, cm.contribution_score, cm.joined_at
               FROM clan_members cm
               JOIN users u ON cm.user_id = u.id
               WHERE cm.clan_id = %s AND u.is_deleted = 0
               ORDER BY cm.contribution_score DESC''',
            (clan_id,)
        )
        members = cursor.fetchall()
    finally:
        conn.close()

    return ok(members)


@clan_bp.route('/api/clans/<int:clan_id>/join', methods=['POST'])
@login_required
def join_clan(clan_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM clans WHERE id = %s', (clan_id,))
        if not cursor.fetchone():
            return err('클랜을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            'SELECT clan_id FROM clan_members WHERE clan_id = %s AND user_id = %s',
            (clan_id, g.user_id)
        )
        if cursor.fetchone():
            return err('이미 가입된 클랜입니다', 'ALREADY_JOINED', 409)

        cursor.execute(
            'INSERT INTO clan_members (clan_id, user_id) VALUES (%s, %s)',
            (clan_id, g.user_id)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({}, '클랜 가입 완료'), 201


@clan_bp.route('/api/clans/<int:clan_id>/leave', methods=['DELETE'])
@login_required
def leave_clan(clan_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT leader_id FROM clans WHERE id = %s', (clan_id,)
        )
        clan = cursor.fetchone()
        if not clan:
            return err('클랜을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if clan['leader_id'] == g.user_id:
            return err('클랜장은 탈퇴할 수 없습니다. 클랜을 해산하거나 리더를 양도해주세요', 'LEADER_CANNOT_LEAVE', 400)

        cursor.execute(
            'DELETE FROM clan_members WHERE clan_id = %s AND user_id = %s',
            (clan_id, g.user_id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            return err('가입된 클랜이 아닙니다', 'NOT_MEMBER', 404)
    finally:
        conn.close()

    return ok({}, '클랜 탈퇴 완료')


# 이번 주 합산 공부시간(초) 식 — 클랜전 공통
_WEEK_SEC = '''COALESCE(SUM(CASE WHEN s.ended_at IS NOT NULL
                                  AND YEARWEEK(s.started_at, 1) = YEARWEEK(CURDATE(), 1)
                                 THEN s.duration_sec ELSE 0 END), 0)'''


@clan_bp.route('/api/clans/ranking', methods=['GET'])
def clan_ranking():
    """클랜전 — 이번 주 멤버 합산 공부시간 랭킹 + 목표 달성률."""
    limit = min(50, int(request.args.get('limit', 20)))

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f'''SELECT c.id, c.name, c.weekly_goal_min,
                       COUNT(DISTINCT cm.user_id) AS member_count,
                       {_WEEK_SEC} AS week_sec
                FROM clans c
                LEFT JOIN clan_members cm ON c.id = cm.clan_id
                LEFT JOIN study_sessions s ON s.user_id = cm.user_id
                GROUP BY c.id
                ORDER BY week_sec DESC, member_count DESC
                LIMIT %s''',
            (limit,)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    ranking = []
    for i, r in enumerate(rows):
        week_min = int(r['week_sec'] or 0) // 60
        goal     = r['weekly_goal_min'] or 0
        ranking.append({
            'rank':         i + 1,
            'id':           r['id'],
            'name':         r['name'],
            'member_count': r['member_count'],
            'week_min':     week_min,
            'goal_min':     goal,
            'progress':     min(1.0, week_min / goal) if goal else 0,
        })
    return ok({'ranking': ranking, 'period': 'week'})


@clan_bp.route('/api/clans/<int:clan_id>/battle', methods=['GET'])
def clan_battle(clan_id):
    """특정 클랜의 이번 주 클랜전 현황 — 목표 진행률·순위·멤버별 기여."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, name, weekly_goal_min FROM clans WHERE id = %s', (clan_id,))
        clan = cursor.fetchone()
        if not clan:
            return err('클랜을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            f'''SELECT u.id, u.username, {_WEEK_SEC} AS week_sec
                FROM clan_members cm
                JOIN users u ON cm.user_id = u.id AND u.is_deleted = 0
                LEFT JOIN study_sessions s ON s.user_id = cm.user_id
                WHERE cm.clan_id = %s
                GROUP BY u.id
                ORDER BY week_sec DESC''',
            (clan_id,)
        )
        members = cursor.fetchall()

        cursor.execute(
            f'''SELECT c.id, {_WEEK_SEC} AS week_sec
                FROM clans c
                LEFT JOIN clan_members cm ON c.id = cm.clan_id
                LEFT JOIN study_sessions s ON s.user_id = cm.user_id
                GROUP BY c.id
                ORDER BY week_sec DESC'''
        )
        all_clans = cursor.fetchall()
    finally:
        conn.close()

    total_min = sum(int(m['week_sec'] or 0) for m in members) // 60
    goal      = clan['weekly_goal_min'] or 0
    rank      = next((i + 1 for i, c in enumerate(all_clans) if c['id'] == clan_id), None)

    return ok({
        'clan_id':     clan_id,
        'name':        clan['name'],
        'week_min':    total_min,
        'goal_min':    goal,
        'progress':    min(1.0, total_min / goal) if goal else 0,
        'rank':        rank,
        'clan_count':  len(all_clans),
        'members':     [{'id': m['id'], 'username': m['username'],
                         'week_min': int(m['week_sec'] or 0) // 60} for m in members],
    })


@clan_bp.route('/api/clans/<int:clan_id>/goal', methods=['PUT'])
@login_required
def set_clan_goal(clan_id):
    """클랜장이 주간 공동 목표(분)를 설정."""
    data = request.get_json() or {}
    try:
        goal = int(data.get('weekly_goal_min'))
    except (TypeError, ValueError):
        return err('목표 시간을 올바르게 입력해주세요', 'INVALID', 400)
    if goal < 60 or goal > 100000:
        return err('주간 목표는 1시간 이상이어야 합니다', 'OUT_OF_RANGE', 400)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT leader_id FROM clans WHERE id = %s', (clan_id,))
        clan = cursor.fetchone()
        if not clan:
            return err('클랜을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if clan['leader_id'] != g.user_id:
            return err('클랜장만 목표를 설정할 수 있습니다', 'FORBIDDEN', 403)

        cursor.execute('UPDATE clans SET weekly_goal_min = %s WHERE id = %s', (goal, clan_id))
        conn.commit()
    finally:
        conn.close()

    return ok({'weekly_goal_min': goal}, '주간 목표가 설정됐어요')
