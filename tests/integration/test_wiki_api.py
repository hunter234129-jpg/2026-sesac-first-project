"""위키 API 통합테스트."""
import pytest

from .conftest import _unique_suffix

pytestmark = pytest.mark.integration


def unique_title():
    return f'통합위키_{_unique_suffix()}'


def test_create_and_get_wiki(client, user):
    title = unique_title()
    r = client.post('/api/wiki', headers=user['headers'], json={
        'title': title, 'content': '# 제목\n내용'
    })
    assert r.status_code == 201
    slug = r.get_json()['data']['slug']

    r = client.get(f'/api/wiki/{slug}')
    assert r.status_code == 200
    assert r.get_json()['data']['title'] == title


def test_create_wiki_missing_title_rejected(client, user):
    r = client.post('/api/wiki', headers=user['headers'], json={'content': '내용만'})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_TITLE'


def test_create_wiki_duplicate_title_rejected(client, user):
    title = unique_title()
    client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': ''})

    r = client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': ''})
    assert r.status_code == 409
    assert r.get_json()['code'] == 'DUPLICATE'


def test_get_wiki_not_found(client):
    r = client.get('/api/wiki/no-such-slug-xyz')
    assert r.status_code == 404


def test_update_wiki_creates_new_version_and_history_entry(client, user):
    title = unique_title()
    r = client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': 'v1'})
    slug = r.get_json()['data']['slug']

    r = client.put(f'/api/wiki/{slug}', headers=user['headers'], json={'content': 'v2', 'summary': '수정'})
    assert r.status_code == 200
    assert r.get_json()['data']['version'] == 2

    r = client.get(f'/api/wiki/{slug}/history')
    assert r.status_code == 200
    assert len(r.get_json()['data']) == 2


def test_rollback_to_previous_version(client, user):
    title = unique_title()
    r = client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': 'v1-content'})
    slug = r.get_json()['data']['slug']

    r = client.get(f'/api/wiki/{slug}/history')
    v1_rev_id = r.get_json()['data'][0]['id']

    client.put(f'/api/wiki/{slug}', headers=user['headers'], json={'content': 'v2-content'})

    r = client.post(f'/api/wiki/{slug}/rollback/{v1_rev_id}', headers=user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['version'] == 3

    r = client.get(f'/api/wiki/{slug}')
    assert r.get_json()['data']['content'] == 'v1-content'


def test_autosave_overwrites_latest_revision_without_new_version(client, user):
    title = unique_title()
    r = client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': 'draft-1'})
    slug = r.get_json()['data']['slug']

    r = client.patch(f'/api/wiki/{slug}/autosave', headers=user['headers'], json={'content': 'draft-2'})
    assert r.status_code == 200

    r = client.get(f'/api/wiki/{slug}')
    assert r.get_json()['data']['content'] == 'draft-2'
    assert r.get_json()['data']['version'] == 1

    r = client.get(f'/api/wiki/{slug}/history')
    assert len(r.get_json()['data']) == 1


def test_search_wiki_finds_matching_title(client, user):
    title = unique_title()
    client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': ''})

    r = client.get(f'/api/wiki/search?q={title}')
    assert r.status_code == 200
    results = r.get_json()['data']['results']
    assert any(item['title'] == title for item in results)
    assert r.get_json()['data']['can_create'] is False


def test_search_wiki_missing_query_rejected(client):
    r = client.get('/api/wiki/search')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_QUERY'


def test_delete_wiki_requires_admin(client, user):
    title = unique_title()
    r = client.post('/api/wiki', headers=user['headers'], json={'title': title, 'content': ''})
    slug = r.get_json()['data']['slug']

    r = client.delete(f'/api/wiki/{slug}', headers=user['headers'])
    assert r.status_code == 403
    assert r.get_json()['code'] == 'FORBIDDEN'
