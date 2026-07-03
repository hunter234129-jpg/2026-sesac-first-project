import json
import re

from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required
from routes.ai import call_gemini, _guard

quiz_bp = Blueprint('quiz', __name__)

LEVEL_LABELS = ['하', '중하', '중', '중상', '상']   # index 0~4 ↔ DB level 1~5
DIAGNOSTIC_SIZE = 5
LEVEL_UP_STREAK = 3     # 연속 정답 N번이면 난이도 상향
LEVEL_DOWN_STREAK = 2   # 연속 오답 N번이면 난이도 하향
MAX_SUBJECT_LEN = 100

DIAGNOSTIC_SYSTEM = (
    "너는 대한민국 교육과정(중1~고3)을 완벽히 숙지한 AI 출제위원이야. "
    "사용자의 현재 실력을 측정하기 위한 진단 테스트 문제를 출제해야 해. "
    "반드시 순수 JSON 배열만 출력하고, 다른 설명이나 마크다운, 코드블록 표시는 절대 포함하지 마."
)

ADAPTIVE_SYSTEM = (
    "너는 학생의 실력에 맞춰 문제 난이도를 조절하는 AI 출제위원이야. "
    "반드시 순수 JSON 객체 하나만 출력하고, 다른 설명이나 마크다운, 코드블록 표시는 절대 포함하지 마."
)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def _level_label(level):
    if not level or not (1 <= level <= len(LEVEL_LABELS)):
        return LEVEL_LABELS[2]
    return LEVEL_LABELS[level - 1]


def _level_from_label(label):
    try:
        return LEVEL_LABELS.index((label or '').strip()) + 1
    except ValueError:
        return 3   # 알 수 없는 라벨이면 '중'으로 취급


def _strip_json_fence(text):
    text = text.strip()
    m = re.match(r'^```(?:json)?\s*(.*?)\s*```$', text, re.DOTALL)
    return m.group(1) if m else text


def _validate_question(item):
    question = (item.get('question') or '').strip()
    choices = item.get('choices')
    answer_index = item.get('answer_index')
    explanation = (item.get('explanation') or '').strip()
    level = _level_from_label(item.get('level'))

    if not question or not isinstance(choices, list) or len(choices) != 4:
        raise ValueError('malformed question')
    choices = [str(c).strip() for c in choices]
    if not all(choices):
        raise ValueError('malformed choices')
    if not isinstance(answer_index, int) or not (0 <= answer_index <= 3):
        raise ValueError('malformed answer_index')

    return {
        'level': level,
        'question': question,
        'choices': choices,
        'answer_index': answer_index,
        'explanation': explanation,
    }


def _parse_diagnostic(text):
    data = json.loads(_strip_json_fence(text))
    if not isinstance(data, list) or not data:
        raise ValueError('expected a JSON array')
    return [_validate_question(item) for item in data[:DIAGNOSTIC_SIZE]]


def _parse_single(text):
    data = json.loads(_strip_json_fence(text))
    if isinstance(data, list):
        data = data[0]
    return _validate_question(data)


def _diagnostic_prompt(subject_query):
    return (
        f'사용자 요청: "{subject_query}"\n\n'
        f'위 요청에 맞는 진단 테스트 문제 {DIAGNOSTIC_SIZE}개를 만들어줘.\n'
        '- 난이도를 하, 중하, 중, 중상, 상 순서로 하나씩 고르게 배치해줘.\n'
        '- 각 문제는 4지선다형이야.\n'
        '- 반드시 아래 JSON 배열 형식으로만 응답해:\n'
        '[{"level": "하", "question": "...", "choices": ["...", "...", "...", "..."], '
        '"answer_index": 0, "explanation": "..."}, ...]\n'
        '- answer_index는 정답 보기의 0부터 시작하는 인덱스(0~3)야.\n'
        '- JSON 이외의 다른 텍스트는 절대 출력하지 마.'
    )


def _adaptive_prompt(subject_query, level_label, history_text):
    return (
        f'사용자 요청 주제: "{subject_query}"\n'
        f'현재 학생 레벨: {level_label} (하/중하/중/중상/상 중 하나)\n'
        f'최근 상황: {history_text}\n\n'
        '위 정보를 바탕으로 학생이 성취감을 느끼면서도 적당히 도전할 수 있는 다음 문제 1개를 만들어줘.\n'
        '- 4지선다형 문제 1개만 만들어.\n'
        '- 반드시 아래 JSON 객체 형식으로만 응답해:\n'
        f'{{"level": "{level_label}", "question": "...", "choices": ["...", "...", "...", "..."], '
        '"answer_index": 0, "explanation": "..."}\n'
        '- answer_index는 정답 보기의 0부터 시작하는 인덱스(0~3)야.\n'
        '- JSON 이외의 다른 텍스트는 절대 출력하지 마.'
    )


def _get_state(cursor, user_id):
    cursor.execute('SELECT * FROM ai_quiz_state WHERE user_id = %s', (user_id,))
    return cursor.fetchone()


def _insert_question(cursor, user_id, subject_query, phase, q):
    cursor.execute(
        '''INSERT INTO ai_quiz_questions
             (user_id, subject_query, phase, level, question, choices, answer_index, explanation)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
        (user_id, subject_query, phase, q['level'], q['question'],
         json.dumps(q['choices'], ensure_ascii=False), q['answer_index'], q['explanation'])
    )
    return cursor.lastrowid


@quiz_bp.route('/api/quiz/start', methods=['POST'])
@login_required
def start_quiz():
    data = request.get_json(silent=True) or {}
    subject_query = (data.get('subject_query') or '').strip()
    if not subject_query:
        return err('어떤 문제를 원하는지 입력해주세요', 'EMPTY_SUBJECT')
    if len(subject_query) > MAX_SUBJECT_LEN:
        return err(f'요청은 {MAX_SUBJECT_LEN}자 이내로 입력해주세요', 'SUBJECT_TOO_LONG')

    def run():
        text = call_gemini(
            [{'role': 'user', 'content': _diagnostic_prompt(subject_query)}],
            system=DIAGNOSTIC_SYSTEM, max_tokens=4096, json_mode=True, temperature=0.6,
        )
        try:
            questions = _parse_diagnostic(text)
        except (ValueError, json.JSONDecodeError):
            return err('AI가 문제를 올바른 형식으로 만들지 못했어요. 다시 시도해주세요', 'AI_BAD_FORMAT', 502)

        conn = get_db(); cursor = conn.cursor()
        try:
            cursor.execute(
                '''INSERT INTO ai_quiz_state
                     (user_id, subject_query, phase, level, correct_streak, wrong_streak,
                      question_count, correct_count, diagnostic_total)
                   VALUES (%s, %s, 'diagnostic', NULL, 0, 0, 0, 0, %s)
                   ON DUPLICATE KEY UPDATE
                     subject_query = VALUES(subject_query), phase = 'diagnostic', level = NULL,
                     correct_streak = 0, wrong_streak = 0, question_count = 0, correct_count = 0,
                     diagnostic_total = VALUES(diagnostic_total)''',
                (g.user_id, subject_query, len(questions))
            )
            ids = [_insert_question(cursor, g.user_id, subject_query, 'diagnostic', q) for q in questions]
            conn.commit()
        finally:
            conn.close()

        return ok({
            'subject_query': subject_query,
            'phase': 'diagnostic',
            'questions': [
                {'id': qid, 'level': _level_label(q['level']), 'question': q['question'], 'choices': q['choices']}
                for qid, q in zip(ids, questions)
            ],
        })

    return _guard(run)


@quiz_bp.route('/api/quiz/next', methods=['POST'])
@login_required
def next_question():
    conn = get_db(); cursor = conn.cursor()
    try:
        state = _get_state(cursor, g.user_id)
    finally:
        conn.close()

    if not state or state['phase'] != 'adaptive':
        return err('먼저 진단 테스트를 완료해주세요', 'DIAGNOSTIC_NOT_DONE', 409)

    level_label = _level_label(state['level'])
    if state['correct_streak'] > 0:
        history_text = f"최근 {state['correct_streak']}문제 연속 정답"
    elif state['wrong_streak'] > 0:
        history_text = f"최근 {state['wrong_streak']}문제 연속 오답"
    else:
        history_text = '특이사항 없음'

    def run():
        text = call_gemini(
            [{'role': 'user', 'content': _adaptive_prompt(state['subject_query'], level_label, history_text)}],
            system=ADAPTIVE_SYSTEM, max_tokens=2048, json_mode=True, temperature=0.7,
        )
        try:
            q = _parse_single(text)
        except (ValueError, json.JSONDecodeError):
            return err('AI가 문제를 올바른 형식으로 만들지 못했어요. 다시 시도해주세요', 'AI_BAD_FORMAT', 502)

        conn = get_db(); cursor = conn.cursor()
        try:
            qid = _insert_question(cursor, g.user_id, state['subject_query'], 'adaptive', q)
            conn.commit()
        finally:
            conn.close()

        return ok({'id': qid, 'level': _level_label(q['level']), 'question': q['question'], 'choices': q['choices']})

    return _guard(run)


@quiz_bp.route('/api/quiz/questions/<int:question_id>/submit', methods=['POST'])
@login_required
def submit_answer(question_id):
    data = request.get_json(silent=True) or {}
    choice_index = data.get('choice_index')
    if not isinstance(choice_index, int) or not (0 <= choice_index <= 3):
        return err('선택한 보기가 올바르지 않습니다', 'INVALID_CHOICE')

    conn = get_db(); cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT * FROM ai_quiz_questions WHERE id = %s AND user_id = %s',
            (question_id, g.user_id)
        )
        question = cursor.fetchone()
        if not question:
            return err('문제를 찾을 수 없습니다', 'NOT_FOUND', 404)
        if question['answered']:
            return err('이미 제출한 문제입니다', 'ALREADY_ANSWERED', 409)

        correct = (choice_index == question['answer_index'])
        cursor.execute(
            'UPDATE ai_quiz_questions SET answered = 1, correct = %s, chosen_index = %s WHERE id = %s',
            (correct, choice_index, question_id)
        )

        if not correct:
            cursor.execute(
                '''INSERT INTO ai_quiz_wrong_notes
                     (user_id, subject_query, level, question, choices, answer_index, chosen_index, explanation)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (g.user_id, question['subject_query'], question['level'], question['question'],
                 question['choices'], question['answer_index'], choice_index, question['explanation'])
            )

        state = _get_state(cursor, g.user_id)
        result = {
            'correct': correct,
            'answer_index': question['answer_index'],
            'explanation': question['explanation'],
        }

        if state and question['phase'] == 'diagnostic' and state['phase'] == 'diagnostic':
            question_count = state['question_count'] + 1
            correct_count = state['correct_count'] + (1 if correct else 0)
            result['diagnostic_progress'] = {'done': question_count, 'total': state['diagnostic_total']}

            if question_count >= state['diagnostic_total']:
                # 5문제 중 맞은 개수로 초기 레벨 산정 (0~1개→하, 2개→중하, ... 5개→상)
                level = max(1, min(len(LEVEL_LABELS), correct_count))
                cursor.execute(
                    '''UPDATE ai_quiz_state
                       SET phase = 'adaptive', level = %s, question_count = %s, correct_count = %s,
                           correct_streak = 0, wrong_streak = 0
                       WHERE user_id = %s''',
                    (level, question_count, correct_count, g.user_id)
                )
                result['phase'] = 'adaptive'
                result['level'] = _level_label(level)
            else:
                cursor.execute(
                    'UPDATE ai_quiz_state SET question_count = %s, correct_count = %s WHERE user_id = %s',
                    (question_count, correct_count, g.user_id)
                )
                result['phase'] = 'diagnostic'

        elif state and state['phase'] == 'adaptive':
            level = state['level']
            correct_streak = state['correct_streak'] + 1 if correct else 0
            wrong_streak = 0 if correct else state['wrong_streak'] + 1
            level_changed = False

            if correct_streak >= LEVEL_UP_STREAK and level < len(LEVEL_LABELS):
                level += 1
                correct_streak = 0
                level_changed = True
            elif wrong_streak >= LEVEL_DOWN_STREAK and level > 1:
                level -= 1
                wrong_streak = 0
                level_changed = True

            cursor.execute(
                '''UPDATE ai_quiz_state
                   SET level = %s, correct_streak = %s, wrong_streak = %s, question_count = question_count + 1
                   WHERE user_id = %s''',
                (level, correct_streak, wrong_streak, g.user_id)
            )
            result['phase'] = 'adaptive'
            result['level'] = _level_label(level)
            result['level_changed'] = level_changed

        conn.commit()
    finally:
        conn.close()

    return ok(result)


@quiz_bp.route('/api/quiz/state', methods=['GET'])
@login_required
def get_state():
    conn = get_db(); cursor = conn.cursor()
    try:
        state = _get_state(cursor, g.user_id)
    finally:
        conn.close()

    if not state:
        return ok({'active': False})

    return ok({
        'active': True,
        'subject_query': state['subject_query'],
        'phase': state['phase'],
        'level': _level_label(state['level']) if state['level'] else None,
        'question_count': state['question_count'],
        'diagnostic_total': state['diagnostic_total'],
    })
