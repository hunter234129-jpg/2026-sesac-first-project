from datetime import date
from flask import Blueprint, jsonify, request
from db.connection import get_db

exams_bp = Blueprint('exams', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})


@exams_bp.route('/api/exams/search', methods=['GET'])
def search_exams():
    """모임 이름에 시험명이 포함되는지 확인하는 용도 — 부분 일치로 후보를 찾고,
    같은 이름이 여러 회차로 쌓여 있으면(정보처리기사 1회/2회/3회 등) 대표로
    '가장 가까운 다음 회차' 하나만 골라서 돌려준다(없으면 가장 최근 회차).
    """
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return ok({'results': []})

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT * FROM exams WHERE name LIKE %s ORDER BY exam_start IS NULL, exam_start ASC',
            (f'%{q}%',)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    today = date.today()
    best_by_name = {}
    for r in rows:
        name = r['name']
        upcoming = bool(r['exam_start']) and r['exam_start'] >= today
        cur = best_by_name.get(name)
        if cur is None:
            best_by_name[name] = r
            continue
        cur_upcoming = bool(cur['exam_start']) and cur['exam_start'] >= today
        if upcoming and (not cur_upcoming or r['exam_start'] < cur['exam_start']):
            best_by_name[name] = r  # 더 가까운 미래 회차로 교체
        elif not upcoming and not cur_upcoming and (cur['exam_start'] is None or
                                                     (r['exam_start'] and r['exam_start'] > cur['exam_start'])):
            best_by_name[name] = r  # 둘 다 지난 회차면 더 최근 것으로

    results = sorted(
        best_by_name.values(),
        key=lambda r: (r['exam_start'] is None, r['exam_start'] or date.max)
    )[:20]

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
