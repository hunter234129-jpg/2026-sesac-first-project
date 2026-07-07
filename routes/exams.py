from datetime import date
from flask import Blueprint, jsonify, request
from db.connection import get_db

exams_bp = Blueprint('exams', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})


def pick_best_round(rows):
    """같은 시험명으로 여러 회차가 쌓여 있을 때(정보처리기사 1회/2회/3회 등) 대표로
    '가장 가까운 다음 회차' 하나를 고른다(없으면 가장 최근에 지난 회차)."""
    today = date.today()
    best = None
    for r in rows:
        upcoming = bool(r['exam_start']) and r['exam_start'] >= today
        if best is None:
            best = r
            continue
        best_upcoming = bool(best['exam_start']) and best['exam_start'] >= today
        if upcoming and (not best_upcoming or r['exam_start'] < best['exam_start']):
            best = r  # 더 가까운 미래 회차로 교체
        elif not upcoming and not best_upcoming and (best['exam_start'] is None or
                                                      (r['exam_start'] and r['exam_start'] > best['exam_start'])):
            best = r  # 둘 다 지난 회차면 더 최근 것으로
    return best


def get_best_exam_by_name(cursor, name):
    """정확한 시험명으로 exams를 조회해서 대표 회차 한 건을 돌려준다(없으면 None).
    모임(posts.linked_exam_name)에 연결된 시험의 D-day 계산 등에 사용."""
    cursor.execute('SELECT * FROM exams WHERE name = %s', (name,))
    return pick_best_round(cursor.fetchall())


@exams_bp.route('/api/exams/search', methods=['GET'])
def search_exams():
    """모임 분야(자격증) 선택용 — 부분 일치로 후보를 찾고, 같은 이름이 여러 회차로
    쌓여 있으면 대표 회차 하나만 골라서 돌려준다. q가 없으면(드롭다운을 처음 열 때)
    등록된 전체 자격증 목록을 분류·이름순으로 돌려준다(현재 20종 내외라 페이지네이션 불필요).
    """
    q = request.args.get('q', '').strip()

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if q:
            cursor.execute(
                'SELECT * FROM exams WHERE name LIKE %s ORDER BY exam_start IS NULL, exam_start ASC',
                (f'%{q}%',)
            )
        else:
            cursor.execute('SELECT * FROM exams ORDER BY exam_start IS NULL, exam_start ASC')
        rows = cursor.fetchall()
    finally:
        conn.close()

    by_name = {}
    for r in rows:
        by_name.setdefault(r['name'], []).append(r)
    best_by_name = {name: pick_best_round(group) for name, group in by_name.items()}

    today = date.today()
    if q:
        results = sorted(
            best_by_name.values(),
            key=lambda r: (r['exam_start'] is None, r['exam_start'] or date.max)
        )[:20]
    else:
        results = sorted(best_by_name.values(), key=lambda r: (r['category'] or '', r['name']))

    return ok({'results': [{
        'name':        r['name'],
        'round':       r['round'],
        'category':    r['category'],
        'source':      r['source'],
        'apply_start': r['apply_start'],
        'apply_end':   r['apply_end'],
        'exam_start':  r['exam_start'],
        'exam_end':    r['exam_end'],
        'result_date': r['result_date'],
        'is_upcoming': bool(r['exam_start']) and r['exam_start'] >= today,
    } for r in results]})
