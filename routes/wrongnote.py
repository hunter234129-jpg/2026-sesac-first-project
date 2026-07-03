import json

from flask import Blueprint, jsonify, g
from db.connection import get_db
from utils.auth import login_required

wrongnote_bp = Blueprint('wrongnote', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@wrongnote_bp.route('/api/wrongnotes', methods=['GET'])
@login_required
def list_wrong_notes():
    """AI 문제풀기에서 틀린 문제가 자동으로 쌓이는 오답노트."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT id, subject_query, level, question, choices, answer_index,
                      chosen_index, explanation, created_at
               FROM ai_quiz_wrong_notes
               WHERE user_id = %s
               ORDER BY created_at DESC''',
            (g.user_id,)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    for r in rows:
        r['choices'] = json.loads(r['choices'])

    return ok(rows)


@wrongnote_bp.route('/api/wrongnotes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_wrong_note(note_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'DELETE FROM ai_quiz_wrong_notes WHERE id = %s AND user_id = %s',
            (note_id, g.user_id)
        )
        if cursor.rowcount == 0:
            return err('오답노트를 찾을 수 없습니다', 'NOT_FOUND', 404)
        conn.commit()
    finally:
        conn.close()

    return ok({'deleted': True})
