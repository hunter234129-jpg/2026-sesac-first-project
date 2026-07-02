import json

from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required

roadmap_bp = Blueprint('roadmap', __name__)

SUBJECTS = ['국어', '영어', '수학']
GRADES   = ['중1', '중2', '중3', '고1', '고2', '고3']
WEAK_THRESHOLD = 3      # 이해도(1~5)가 이 값 이하이면 '약점' 단원으로 간주
QUIZ_CORRECT_LEVEL = 5  # 문제를 맞히면 부여되는 이해도
QUIZ_WRONG_LEVEL   = 2  # 문제를 틀리면 부여되는 이해도


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def _set_understanding(cursor, user_id, topic_id, level):
    """단원을 완료 처리하고 이해도(1~5)를 기록한다. commit은 호출부 책임."""
    cursor.execute(
        '''INSERT INTO user_topic_progress (user_id, topic_id, is_done, understanding, done_at)
           VALUES (%s, %s, 1, %s, NOW())
           ON DUPLICATE KEY UPDATE
             understanding = VALUES(understanding),
             is_done = 1,
             done_at = IF(is_done = 1, done_at, NOW())''',
        (user_id, topic_id, level)
    )


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
                      COALESCE(p.is_done, 0) AS is_done, p.understanding, p.done_at
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
    weak_count = sum(1 for t in topics if t['is_done'] and t['understanding'] and t['understanding'] <= WEAK_THRESHOLD)
    return ok({
        'subject': subject,
        'grades': grades,
        'total': len(topics),
        'done_count': done_count,
        'weak_count': weak_count,
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
                      SUM(COALESCE(p.is_done, 0)) AS done_count,
                      SUM(CASE WHEN p.is_done = 1 AND p.understanding <= %s THEN 1 ELSE 0 END) AS weak_count
               FROM curriculum_topics t
               LEFT JOIN user_topic_progress p
                 ON t.id = p.topic_id AND p.user_id = %s
               GROUP BY t.subject''',
            (WEAK_THRESHOLD, g.user_id)
        )
        rows = {r['subject']: r for r in cursor.fetchall()}
    finally:
        conn.close()

    summary = [
        {
            'subject': s,
            'total': int(rows.get(s, {}).get('total', 0) or 0),
            'done_count': int(rows.get(s, {}).get('done_count', 0) or 0),
            'weak_count': int(rows.get(s, {}).get('weak_count', 0) or 0),
        }
        for s in SUBJECTS
    ]
    return ok(summary)


@roadmap_bp.route('/api/roadmap/weak', methods=['GET'])
@login_required
def get_weak_topics():
    """완료했지만 이해도가 낮게 자가진단된 단원을 복습 추천 목록으로 반환."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT t.id, t.subject, t.grade, t.unit_name, t.description, p.understanding
               FROM user_topic_progress p
               JOIN curriculum_topics t ON t.id = p.topic_id
               WHERE p.user_id = %s AND p.is_done = 1 AND p.understanding IS NOT NULL AND p.understanding <= %s
               ORDER BY p.understanding ASC, p.done_at DESC
               LIMIT 10''',
            (g.user_id, WEAK_THRESHOLD)
        )
        weak = cursor.fetchall()
    finally:
        conn.close()

    return ok(weak)


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


@roadmap_bp.route('/api/roadmap/topics/<int:topic_id>/rate', methods=['POST'])
@login_required
def rate_topic(topic_id):
    """단원 이해도 자가진단(1~5). 평가하면 해당 단원은 완료 처리된다."""
    data  = request.get_json(silent=True) or {}
    level = data.get('level')
    if not isinstance(level, int) or not (1 <= level <= 5):
        return err('이해도는 1~5 사이의 정수여야 합니다', 'INVALID_LEVEL', 400)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM curriculum_topics WHERE id = %s', (topic_id,))
        if not cursor.fetchone():
            return err('단원을 찾을 수 없습니다', 'NOT_FOUND', 404)

        _set_understanding(cursor, g.user_id, topic_id, level)
        conn.commit()
    finally:
        conn.close()

    return ok({'is_done': True, 'understanding': level})


@roadmap_bp.route('/api/roadmap/topics/<int:topic_id>/quiz', methods=['GET'])
@login_required
def get_topic_quiz(topic_id):
    """단원 확인 문제(질문+보기만 반환, 정답은 제출 후에 공개)."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT question, choices FROM curriculum_quiz WHERE topic_id = %s',
            (topic_id,)
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return err('이 단원에는 아직 확인 문제가 없습니다', 'QUIZ_NOT_FOUND', 404)

    return ok({'question': row['question'], 'choices': json.loads(row['choices'])})


@roadmap_bp.route('/api/roadmap/topics/<int:topic_id>/quiz/submit', methods=['POST'])
@login_required
def submit_topic_quiz(topic_id):
    """단원 확인 문제 채점. 맞히면 이해도 5, 틀리면 이해도 2로 자동 기록(완료 처리 포함)."""
    data         = request.get_json(silent=True) or {}
    choice_index = data.get('choice_index')
    if not isinstance(choice_index, int) or not (0 <= choice_index <= 3):
        return err('선택한 보기가 올바르지 않습니다', 'INVALID_CHOICE', 400)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT answer_index, explanation FROM curriculum_quiz WHERE topic_id = %s',
            (topic_id,)
        )
        quiz = cursor.fetchone()
        if not quiz:
            return err('이 단원에는 아직 확인 문제가 없습니다', 'QUIZ_NOT_FOUND', 404)

        correct = (choice_index == quiz['answer_index'])
        level = QUIZ_CORRECT_LEVEL if correct else QUIZ_WRONG_LEVEL
        _set_understanding(cursor, g.user_id, topic_id, level)

        if correct:
            # 다시 풀어서 맞혔으면 오답노트에서 자동으로 제거
            cursor.execute(
                'DELETE FROM wrong_notes WHERE user_id = %s AND topic_id = %s',
                (g.user_id, topic_id)
            )
        else:
            # 틀렸으면 오답노트에 자동으로 쌓임(다시 틀리면 횟수만 누적)
            cursor.execute(
                '''INSERT INTO wrong_notes (user_id, topic_id, chosen_index, wrong_count, last_wrong_at)
                   VALUES (%s, %s, %s, 1, NOW())
                   ON DUPLICATE KEY UPDATE
                     chosen_index = VALUES(chosen_index),
                     wrong_count = wrong_count + 1,
                     last_wrong_at = NOW()''',
                (g.user_id, topic_id, choice_index)
            )
        conn.commit()
    finally:
        conn.close()

    return ok({
        'correct': correct,
        'answer_index': quiz['answer_index'],
        'explanation': quiz['explanation'],
        'understanding': level,
    })
