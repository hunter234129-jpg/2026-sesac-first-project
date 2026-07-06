"""AI 도우미(routes/ai.py) API 통합테스트.

실제 Gemini 호출은 비용·지연·비결정성이 있어서, routes.ai.call_gemini를
monkeypatch로 바꿔치기해 라우트의 입력 검증·에러 처리·응답 조립만 검증한다.
_guard()의 재시도/과부하 처리 로직 자체는 순수 로직이라 여기서 예외를 강제로
발생시켜 확인한다.
"""
import pytest

pytestmark = pytest.mark.integration


# ── /api/ai/chat ─────────────────────────────────────────────────────

def test_chat_requires_auth(client):
    r = client.post('/api/ai/chat', json={'message': '안녕'})
    assert r.status_code == 401


def test_chat_empty_message_rejected(client, user):
    r = client.post('/api/ai/chat', headers=user['headers'], json={})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'EMPTY_MESSAGE'


def test_chat_success_with_mocked_gemini(client, user, monkeypatch):
    monkeypatch.setattr('routes.ai.call_gemini', lambda *a, **k: '안녕하세요! 무엇을 도와드릴까요?')
    r = client.post('/api/ai/chat', headers=user['headers'], json={'message': '안녕'})
    assert r.status_code == 200
    assert r.get_json()['data']['reply'] == '안녕하세요! 무엇을 도와드릴까요?'


def test_chat_with_message_history_requires_last_message_from_user(client, user):
    r = client.post('/api/ai/chat', headers=user['headers'], json={
        'messages': [{'role': 'user', 'content': '안녕'}, {'role': 'assistant', 'content': '네!'}]
    })
    assert r.status_code == 400
    assert r.get_json()['code'] == 'EMPTY_MESSAGE'


def test_chat_no_api_key_returns_503(client, user, monkeypatch):
    monkeypatch.setattr('routes.ai.GEMINI_API_KEY', '')
    r = client.post('/api/ai/chat', headers=user['headers'], json={'message': '안녕'})
    assert r.status_code == 503
    assert r.get_json()['code'] == 'NO_API_KEY'


def test_chat_overloaded_gemini_returns_friendly_error(client, user, monkeypatch):
    class _FakeOverload(Exception):
        code = 503

    def _raise(*a, **k):
        raise _FakeOverload('model overloaded')

    monkeypatch.setattr('routes.ai.call_gemini', _raise)
    r = client.post('/api/ai/chat', headers=user['headers'], json={'message': '안녕'})
    assert r.status_code == 503
    assert r.get_json()['code'] == 'AI_OVERLOADED'


def test_chat_unexpected_error_returns_502(client, user, monkeypatch):
    def _raise(*a, **k):
        raise ValueError('boom')

    monkeypatch.setattr('routes.ai.call_gemini', _raise)
    r = client.post('/api/ai/chat', headers=user['headers'], json={'message': '안녕'})
    assert r.status_code == 502
    assert r.get_json()['code'] == 'AI_FAILED'


# ── /api/ai/summarize ────────────────────────────────────────────────

def test_summarize_requires_text_or_post_id(client, user):
    r = client.post('/api/ai/summarize', headers=user['headers'], json={})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'EMPTY'


def test_summarize_unknown_post_id_returns_404(client, user):
    r = client.post('/api/ai/summarize', headers=user['headers'], json={'post_id': 999999999})
    assert r.status_code == 404


def test_summarize_with_raw_text_success(client, user, monkeypatch):
    monkeypatch.setattr('routes.ai.call_gemini', lambda *a, **k: '- 핵심 요약 1\n- 핵심 요약 2')
    r = client.post('/api/ai/summarize', headers=user['headers'], json={'text': '긴 글입니다...'})
    assert r.status_code == 200
    assert r.get_json()['data']['summary'] == '- 핵심 요약 1\n- 핵심 요약 2'


def test_summarize_with_post_id_success(client, user, monkeypatch):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '요약테스트글', 'content': '본문 내용입니다', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    monkeypatch.setattr('routes.ai.call_gemini', lambda *a, **k: '요약된 내용')
    r = client.post('/api/ai/summarize', headers=user['headers'], json={'post_id': post_id})
    assert r.status_code == 200
    assert r.get_json()['data']['summary'] == '요약된 내용'


# ── /api/ai/plan ──────────────────────────────────────────────────────

def test_plan_missing_goal_rejected(client, user):
    r = client.post('/api/ai/plan', headers=user['headers'], json={})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'EMPTY_GOAL'


def test_plan_success_with_mocked_gemini(client, user, monkeypatch):
    monkeypatch.setattr('routes.ai.call_gemini', lambda *a, **k: '1주차: 기초\n2주차: 실전')
    r = client.post('/api/ai/plan', headers=user['headers'], json={'goal': '토익 900점'})
    assert r.status_code == 200
    assert r.get_json()['data']['plan'] == '1주차: 기초\n2주차: 실전'


# ── /api/ai/wiki-draft ────────────────────────────────────────────────

def test_wiki_draft_missing_title_rejected(client, user):
    r = client.post('/api/ai/wiki-draft', headers=user['headers'], json={})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'EMPTY_TITLE'


def test_wiki_draft_success_with_mocked_gemini(client, user, monkeypatch):
    monkeypatch.setattr('routes.ai.call_gemini', lambda *a, **k: '## 개요\n테스트 초안')
    r = client.post('/api/ai/wiki-draft', headers=user['headers'], json={'title': '이차방정식'})
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data['title'] == '이차방정식'
    assert data['draft'] == '## 개요\n테스트 초안'
