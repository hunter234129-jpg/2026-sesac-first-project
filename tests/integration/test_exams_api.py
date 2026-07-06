"""시험 정보 검색(exams) API 통합테스트.

exams 테이블은 크롤러(크론)로만 채워지고 생성용 API가 없어서, 각 테스트는
conftest.seed_exam()으로 DB에 직접 행을 넣어 검증한다. 실제 크롤러(routes/crawl.py,
crawlers/*)는 외부 사이트(q-net 등)에 실제 요청을 보내므로 통합테스트 대상에서 제외했다.
"""
from datetime import date, timedelta

import pytest

from .conftest import _unique_suffix, seed_exam

pytestmark = pytest.mark.integration


def test_search_query_too_short_returns_empty(client):
    r = client.get('/api/exams/search?q=a')
    assert r.status_code == 200
    assert r.get_json()['data']['results'] == []


def test_search_missing_query_returns_empty(client):
    r = client.get('/api/exams/search')
    assert r.status_code == 200
    assert r.get_json()['data']['results'] == []


def test_search_finds_seeded_exam(client):
    name = f'통합시험_{_unique_suffix()}'
    seed_exam(name, round_=1, exam_start=date.today() + timedelta(days=30))

    r = client.get(f'/api/exams/search?q={name}')
    assert r.status_code == 200
    results = r.get_json()['data']['results']
    assert any(item['name'] == name for item in results)
    match = next(item for item in results if item['name'] == name)
    assert match['is_upcoming'] is True


def test_search_partial_match(client):
    name = f'부분일치테스트_{_unique_suffix()}'
    seed_exam(name, round_=1, exam_start=date.today() + timedelta(days=10))

    r = client.get(f'/api/exams/search?q={name[:8]}')
    assert r.status_code == 200
    assert any(item['name'] == name for item in r.get_json()['data']['results'])


def test_search_dedups_multiple_rounds_to_nearest_upcoming(client):
    """같은 이름으로 여러 회차가 쌓여 있으면 대표로 하나만(가장 가까운 다음 회차) 나와야 한다."""
    name = f'회차중복테스트_{_unique_suffix()}'
    seed_exam(name, round_=1, exam_start=date.today() - timedelta(days=100))   # 지난 회차
    seed_exam(name, round_=2, exam_start=date.today() + timedelta(days=5))    # 가장 가까운 다음 회차
    seed_exam(name, round_=3, exam_start=date.today() + timedelta(days=90))   # 더 먼 미래 회차

    r = client.get(f'/api/exams/search?q={name}')
    assert r.status_code == 200
    matches = [item for item in r.get_json()['data']['results'] if item['name'] == name]
    assert len(matches) == 1
    assert matches[0]['round'] == 2
    assert matches[0]['is_upcoming'] is True


def test_search_no_upcoming_rounds_picks_most_recent_past(client):
    name = f'전부지남테스트_{_unique_suffix()}'
    seed_exam(name, round_=1, exam_start=date.today() - timedelta(days=200))
    seed_exam(name, round_=2, exam_start=date.today() - timedelta(days=20))

    r = client.get(f'/api/exams/search?q={name}')
    matches = [item for item in r.get_json()['data']['results'] if item['name'] == name]
    assert len(matches) == 1
    assert matches[0]['round'] == 2
    assert matches[0]['is_upcoming'] is False
