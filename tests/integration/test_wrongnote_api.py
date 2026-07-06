"""오답노트(wrongnote) API 통합테스트.

목록/삭제는 DB만 다루므로 그대로 테스트하고, AI 약점분석(/api/wrongnotes/analysis)은
routes.wrongnote.call_gemini를 monkeypatch로 바꿔치기해 실제 Gemini 호출 없이
배선(데이터 부족 가드·프롬프트 조립·에러 처리)만 검증한다.
"""
import pytest

from .conftest import seed_wrong_note

pytestmark = pytest.mark.integration


def test_list_wrongnotes_requires_auth(client):
    r = client.get('/api/wrongnotes')
    assert r.status_code == 401


def test_list_wrongnotes_empty_initially(client, user):
    r = client.get('/api/wrongnotes', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data'] == []


def test_list_wrongnotes_returns_seeded_note_with_parsed_choices(client, user):
    seed_wrong_note(user['id'], question='이 문제 정답은?', choices=['1', '2', '3', '4'])

    r = client.get('/api/wrongnotes', headers=user['headers'])
    notes = r.get_json()['data']
    assert len(notes) == 1
    assert notes[0]['question'] == '이 문제 정답은?'
    assert notes[0]['choices'] == ['1', '2', '3', '4']   # JSON 문자열이 파싱돼서 나와야 함


def test_list_wrongnotes_only_returns_own_notes(client, user, other_user):
    seed_wrong_note(other_user['id'], question='다른 사람 오답')

    r = client.get('/api/wrongnotes', headers=user['headers'])
    assert r.get_json()['data'] == []


def test_delete_wrongnote_not_found(client, user):
    r = client.delete('/api/wrongnotes/999999999', headers=user['headers'])
    assert r.status_code == 404


def test_delete_wrongnote_success(client, user):
    note_id = seed_wrong_note(user['id'])

    r = client.delete(f'/api/wrongnotes/{note_id}', headers=user['headers'])
    assert r.status_code == 200

    r = client.get('/api/wrongnotes', headers=user['headers'])
    assert r.get_json()['data'] == []


def test_delete_wrongnote_forbidden_for_other_user(client, user, other_user):
    note_id = seed_wrong_note(user['id'])

    r = client.delete(f'/api/wrongnotes/{note_id}', headers=other_user['headers'])
    assert r.status_code == 404   # user_id 조건에 안 걸려서 "본인 것만" 삭제 가능 → 남의 건 NOT_FOUND

    r = client.get('/api/wrongnotes', headers=user['headers'])
    assert len(r.get_json()['data']) == 1   # 삭제되지 않고 그대로 남아있어야 함


def test_analysis_requires_auth(client):
    r = client.get('/api/wrongnotes/analysis')
    assert r.status_code == 401


def test_analysis_not_enough_data_rejected(client, user):
    seed_wrong_note(user['id'])
    seed_wrong_note(user['id'])   # 2개뿐 — MIN_NOTES_FOR_ANALYSIS=3 미달

    r = client.get('/api/wrongnotes/analysis', headers=user['headers'])
    assert r.status_code == 409
    assert r.get_json()['code'] == 'NOT_ENOUGH_DATA'


def test_analysis_success_with_mocked_gemini(client, user, monkeypatch):
    for _ in range(3):
        seed_wrong_note(user['id'])

    monkeypatch.setattr('routes.wrongnote.call_gemini', lambda *a, **k: '## 약점 요약\n테스트 분석 결과')
    r = client.get('/api/wrongnotes/analysis', headers=user['headers'])
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data['analysis'] == '## 약점 요약\n테스트 분석 결과'
    assert data['note_count'] == 3


def test_analysis_no_api_key_returns_503(client, user, monkeypatch):
    for _ in range(3):
        seed_wrong_note(user['id'])

    monkeypatch.setattr('routes.ai.GEMINI_API_KEY', '')
    r = client.get('/api/wrongnotes/analysis', headers=user['headers'])
    assert r.status_code == 503
    assert r.get_json()['code'] == 'NO_API_KEY'


def test_analysis_overloaded_gemini_returns_friendly_error(client, user, monkeypatch):
    for _ in range(3):
        seed_wrong_note(user['id'])

    class _FakeOverload(Exception):
        code = 503

    def _raise(*a, **k):
        raise _FakeOverload('model overloaded')

    monkeypatch.setattr('routes.wrongnote.call_gemini', _raise)
    r = client.get('/api/wrongnotes/analysis', headers=user['headers'])
    assert r.status_code == 503
    assert r.get_json()['code'] == 'AI_OVERLOADED'
