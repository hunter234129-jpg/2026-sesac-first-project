"""AI 문제풀기(quiz) API 통합테스트.

routes/quiz.py는 routes/ai.py의 call_gemini()로 실제 Gemini API를 호출한다. 실제
호출은 비용·지연·비결정성이 있어서, monkeypatch로 routes.quiz.call_gemini를
가짜 함수로 바꿔치기해 API 배선(파싱·상태 전이·오답노트 적재)만 검증한다.
"""
import json

import pytest

pytestmark = pytest.mark.integration

LEVELS = ['하', '중하', '중', '중상', '상']


def _question(level_label='중', question='문제?', choices=None, answer_index=0, explanation='설명'):
    return {
        'level': level_label, 'question': question,
        'choices': choices or ['A', 'B', 'C', 'D'],
        'answer_index': answer_index, 'explanation': explanation,
    }


def _diagnostic_json(answer_index=0):
    return json.dumps(
        [_question(level_label=lv, question=f'{lv} 문제', answer_index=answer_index) for lv in LEVELS],
        ensure_ascii=False
    )


def _single_json(level_label='중', answer_index=0):
    return json.dumps(_question(level_label=level_label, answer_index=answer_index), ensure_ascii=False)


def test_start_quiz_requires_auth(client):
    r = client.post('/api/quiz/start', json={'subject_query': '파이썬'})
    assert r.status_code == 401


def test_start_quiz_empty_subject_rejected(client, user):
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': ''})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'EMPTY_SUBJECT'


def test_start_quiz_subject_too_long_rejected(client, user):
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': 'x' * 101})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'SUBJECT_TOO_LONG'


def test_start_quiz_creates_diagnostic_questions(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json())
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '파이썬 기초'})
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data['phase'] == 'diagnostic'
    assert len(data['questions']) == 5
    q = data['questions'][0]
    assert set(q.keys()) == {'id', 'level', 'question', 'choices'}   # 정답/설명은 클라이언트에 노출 안 됨


def test_start_quiz_bad_ai_json_returns_502(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: '이건 JSON이 아니에요')
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '파이썬'})
    assert r.status_code == 502
    assert r.get_json()['code'] == 'AI_BAD_FORMAT'


def test_next_question_requires_diagnostic_done(client, user):
    r = client.post('/api/quiz/next', headers=user['headers'])
    assert r.status_code == 409
    assert r.get_json()['code'] == 'DIAGNOSTIC_NOT_DONE'


def test_get_state_before_and_after_start(client, user, monkeypatch):
    r = client.get('/api/quiz/state', headers=user['headers'])
    assert r.get_json()['data']['active'] is False

    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json())
    client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '국어'})

    r = client.get('/api/quiz/state', headers=user['headers'])
    data = r.get_json()['data']
    assert data['active'] is True
    assert data['phase'] == 'diagnostic'
    assert data['diagnostic_total'] == 5


def test_submit_unknown_question_returns_404(client, user):
    r = client.post('/api/quiz/questions/999999999/submit', headers=user['headers'], json={'choice_index': 0})
    assert r.status_code == 404


def test_submit_invalid_choice_index_rejected(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json())
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '역사'})
    qid = r.get_json()['data']['questions'][0]['id']

    r = client.post(f'/api/quiz/questions/{qid}/submit', headers=user['headers'], json={'choice_index': 9})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_CHOICE'


def test_submit_already_answered_rejected(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json(answer_index=0))
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '과학'})
    qid = r.get_json()['data']['questions'][0]['id']
    client.post(f'/api/quiz/questions/{qid}/submit', headers=user['headers'], json={'choice_index': 0})

    r = client.post(f'/api/quiz/questions/{qid}/submit', headers=user['headers'], json={'choice_index': 0})
    assert r.status_code == 409
    assert r.get_json()['code'] == 'ALREADY_ANSWERED'


def test_submit_wrong_answer_creates_wrong_note(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json(answer_index=0))
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '영어'})
    q = r.get_json()['data']['questions'][0]

    r = client.post(f"/api/quiz/questions/{q['id']}/submit", headers=user['headers'], json={'choice_index': 1})
    assert r.status_code == 200
    assert r.get_json()['data']['correct'] is False

    r = client.get('/api/wrongnotes', headers=user['headers'])
    assert any(n['question'] == q['question'] for n in r.get_json()['data'])


def test_diagnostic_flow_all_correct_reaches_top_adaptive_level(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json(answer_index=0))
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '수학'})
    questions = r.get_json()['data']['questions']
    assert len(questions) == 5

    result = None
    for q in questions:
        r = client.post(f"/api/quiz/questions/{q['id']}/submit", headers=user['headers'], json={'choice_index': 0})
        assert r.status_code == 200
        result = r.get_json()['data']
        assert result['correct'] is True

    # 5문제 모두 정답 → correct_count=5 → level = min(5, 5) = 5 ('상')
    assert result['phase'] == 'adaptive'
    assert result['level'] == '상'


def test_adaptive_level_up_after_correct_streak(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json(answer_index=0))
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '체육'})
    questions = r.get_json()['data']['questions']

    result = None
    for i, q in enumerate(questions):
        choice = 0 if i < 2 else 1   # 2개만 정답 → correct_count=2 → level=2('중하')로 시작
        r = client.post(f"/api/quiz/questions/{q['id']}/submit", headers=user['headers'], json={'choice_index': choice})
        result = r.get_json()['data']
    assert result['phase'] == 'adaptive'
    assert result['level'] == '중하'

    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _single_json(answer_index=0))
    level_changed_seen = False
    for _ in range(3):   # LEVEL_UP_STREAK=3 → 연속 3정답째에 레벨업
        r = client.post('/api/quiz/next', headers=user['headers'])
        qid = r.get_json()['data']['id']
        r = client.post(f'/api/quiz/questions/{qid}/submit', headers=user['headers'], json={'choice_index': 0})
        result = r.get_json()['data']
        level_changed_seen = level_changed_seen or result.get('level_changed')

    assert level_changed_seen is True
    assert result['level'] == '중'   # 중하(2) → 중(3)


def test_next_question_bad_ai_json_returns_502(client, user, monkeypatch):
    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: _diagnostic_json(answer_index=0))
    r = client.post('/api/quiz/start', headers=user['headers'], json={'subject_query': '지리'})
    for q in r.get_json()['data']['questions']:
        client.post(f"/api/quiz/questions/{q['id']}/submit", headers=user['headers'], json={'choice_index': 0})

    monkeypatch.setattr('routes.quiz.call_gemini', lambda *a, **k: '깨진 응답')
    r = client.post('/api/quiz/next', headers=user['headers'])
    assert r.status_code == 502
    assert r.get_json()['code'] == 'AI_BAD_FORMAT'
