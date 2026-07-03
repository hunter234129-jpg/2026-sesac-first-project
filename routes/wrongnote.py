import json

from flask import Blueprint, jsonify, g
from db.connection import get_db
from utils.auth import login_required

wrongnote_bp = Blueprint('wrongnote', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})


@wrongnote_bp.route('/api/wrongnotes', methods=['GET'])
@login_required
def list_wrong_notes():
    """단원 확인 문제를 틀리면 자동으로 쌓이는 오답노트. 다시 풀어서 맞히면 자동으로 사라진다."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT w.topic_id, w.chosen_index, w.wrong_count, w.last_wrong_at,
                      t.subject, t.grade, t.unit_name,
                      q.question, q.choices, q.answer_index, q.explanation
               FROM wrong_notes w
               JOIN curriculum_topics t ON t.id = w.topic_id
               JOIN curriculum_quiz q   ON q.topic_id = w.topic_id
               WHERE w.user_id = %s
               ORDER BY w.last_wrong_at DESC''',
            (g.user_id,)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    for r in rows:
        r['choices'] = json.loads(r['choices'])

    return ok(rows)
