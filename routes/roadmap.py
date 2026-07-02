from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required

roadmap_bp = Blueprint('roadmap', __name__)

SUBJECTS = ['국어', '영어', '수학']
GRADES   = ['중1', '중2', '중3', '고1', '고2', '고3']


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@roadmap_bp.route('/api/roadmap/subjects', methods=['GET'])
def get_subjects():
    return ok(SUBJECTS)


@roadmap_bp.route('/api/roadmap', methods=['GET'])
@login_required
def get_roadmap():
    subject = request.args.get('subject', '수학')
    if subject not in SUBJECTS:
        return err('지원하지 않는 과목입니다', 'INVALID_SUBJECT', 400)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT t.id, t.grade, t.step_order, t.unit_name, t.description,
                      COALESCE(p.is_done, 0) AS is_done, p.done_at
               FROM curriculum_topics t
               LEFT JOIN user_topic_progress p
                 ON t.id = p.topic_id AND p.user_id = %s
               WHERE t.subject = %s
               ORDER BY t.step_order''',
            (g.user_id, subject)
        )
        topics = cursor.fetchall()
    finally:
        conn.close()

    grades = []
    by_grade = {}
    for t in topics:
        grade = t['grade']
        if grade not in by_grade:
            by_grade[grade] = {'grade': grade, 'topics': []}
            grades.append(by_grade[grade])
        by_grade[grade]['topics'].append(t)

    done_count = sum(1 for t in topics if t['is_done'])
    return ok({
        'subject': subject,
        'grades': grades,
        'total': len(topics),
        'done_count': done_count,
    })


@roadmap_bp.route('/api/roadmap/summary', methods=['GET'])
@login_required
def get_summary():
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT t.subject,
                      COUNT(*) AS total,
                      SUM(COALESCE(p.is_done, 0)) AS done_count
               FROM curriculum_topics t
               LEFT JOIN user_topic_progress p
                 ON t.id = p.topic_id AND p.user_id = %s
               GROUP BY t.subject''',
            (g.user_id,)
        )
        rows = {r['subject']: r for r in cursor.fetchall()}
    finally:
        conn.close()

    summary = [
        {'subject': s, 'total': int(rows.get(s, {}).get('total', 0) or 0), 'done_count': int(rows.get(s, {}).get('done_count', 0) or 0)}
        for s in SUBJECTS
    ]
    return ok(summary)


@roadmap_bp.route('/api/roadmap/topics/<int:topic_id>/toggle', methods=['POST'])
@login_required
def toggle_topic(topic_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM curriculum_topics WHERE id = %s', (topic_id,))
        if not cursor.fetchone():
            return err('단원을 찾을 수 없습니다', 'NOT_FOUND', 404)

        cursor.execute(
            'SELECT is_done FROM user_topic_progress WHERE user_id = %s AND topic_id = %s',
            (g.user_id, topic_id)
        )
        row = cursor.fetchone()
        new_done = 0 if (row and row['is_done']) else 1

        cursor.execute(
            '''INSERT INTO user_topic_progress (user_id, topic_id, is_done, done_at)
               VALUES (%s, %s, %s, IF(%s, NOW(), NULL))
               ON DUPLICATE KEY UPDATE is_done = %s, done_at = IF(%s, NOW(), NULL)''',
            (g.user_id, topic_id, new_done, new_done, new_done, new_done)
        )
        conn.commit()
    finally:
        conn.close()

    return ok({'is_done': bool(new_done)})
