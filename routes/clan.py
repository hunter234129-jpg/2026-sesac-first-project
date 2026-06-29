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
