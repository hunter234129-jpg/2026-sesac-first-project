import json

from flask import Blueprint, jsonify, g
from db.connection import get_db
from utils.auth import login_required
from routes.ai import call_gemini, _guard
from routes.quiz import _level_label

wrongnote_bp = Blueprint('wrongnote', __name__)

ANALYSIS_SYSTEM = (
    "너는 학생의 오답노트를 분석해서 약점을 짚어주는 AI 학습 코치야. "
    "한국어로, 학생이 3분 안에 읽고 바로 실천할 수 있을 만큼 명확하고 구체적으로 답해."
)
MIN_NOTES_FOR_ANALYSIS = 3   # 이보다 적으면 패턴을 뽑기엔 데이터가 부족하다고 판단
ANALYSIS_SAMPLE_SIZE = 30    # 프롬프트가 지나치게 길어지지 않도록 최근 오답만 사용


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def _analysis_prompt(notes):
    lines = [
        f"- [{n['subject_query']}] (난이도 {_level_label(n['level'])}) "
        f"문제: {n['question']} / 정답: {n['choices'][n['answer_index']]} / "
        f"선택한 오답: {n['choices'][n['chosen_index']]}"
        for n in notes
    ]
    return (
        f"아래는 한 학생이 AI 문제풀기에서 틀린 문제 목록이야 (총 {len(notes)}개, 최신순):\n\n"
        + '\n'.join(lines) +
        "\n\n위 오답들을 분석해서 다음 구성으로 마크다운 정리해줘:\n"
        "## 약점 요약\n자주 틀리는 주제/개념을 2~4개로 묶어서 설명\n\n"
        "## 원인 분석\n왜 틀렸을지 패턴(특정 개념 혼동, 특정 난이도에서 집중 오답 등)\n\n"
        "## 학습 추천\n다음에 무엇을 어떻게 공부하면 좋을지 구체적인 실천 방법 2~4가지\n\n"
        "너무 길게 쓰지 말고 핵심만 짚어줘."
    )


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


@wrongnote_bp.route('/api/wrongnotes/analysis', methods=['GET'])
@login_required
def analyze_weakness():
    """오답노트를 모아 기존 문제풀기 AI(Gemini)로 약점 분석을 요청한다."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT subject_query, level, question, choices, answer_index, chosen_index
               FROM ai_quiz_wrong_notes
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s''',
            (g.user_id, ANALYSIS_SAMPLE_SIZE)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if len(rows) < MIN_NOTES_FOR_ANALYSIS:
        return err(
            f'분석하려면 오답노트가 최소 {MIN_NOTES_FOR_ANALYSIS}개 필요해요 (현재 {len(rows)}개)',
            'NOT_ENOUGH_DATA', 409
        )

    for r in rows:
        r['choices'] = json.loads(r['choices'])

    def run():
        text = call_gemini(
            [{'role': 'user', 'content': _analysis_prompt(rows)}],
            system=ANALYSIS_SYSTEM, max_tokens=2048, temperature=0.4,
        )
        return ok({'analysis': text, 'note_count': len(rows)})

    return _guard(run)


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
