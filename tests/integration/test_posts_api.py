"""게시판(posts) API 통합테스트."""
import pytest

pytestmark = pytest.mark.integration


def test_create_post_requires_title(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={'content': '내용만 있음'})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_TITLE'


def test_create_post_invalid_type_rejected(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '제목', 'type': 'invalid'
    })
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_TYPE'


def test_create_and_get_post(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '통합테스트 게시글', 'content': '본문', 'type': 'post'
    })
    assert r.status_code == 201
    post_id = r.get_json()['data']['id']

    r = client.get(f'/api/posts/{post_id}')
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['title'] == '통합테스트 게시글'
    assert body['view_count'] >= 1


def test_get_post_not_found(client):
    r = client.get('/api/posts/999999999')
    assert r.status_code == 404


def test_list_posts_returns_pagination_shape(client, user):
    client.post('/api/posts', headers=user['headers'], json={
        'title': '목록테스트', 'content': '', 'type': 'post'
    })
    r = client.get('/api/posts?page=1&size=5')
    assert r.status_code == 200
    data = r.get_json()['data']
    assert set(['posts', 'total', 'page', 'size', 'total_pages']).issubset(data.keys())


def test_list_posts_filter_by_type(client, user):
    client.post('/api/posts', headers=user['headers'], json={
        'title': '필터테스트_모임', 'content': '', 'type': 'study'
    })
    r = client.get('/api/posts?type=study&size=50')
    assert r.status_code == 200
    assert all(p['type'] == 'study' for p in r.get_json()['data']['posts'])


def test_update_post_forbidden_for_non_owner(client, user, other_user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '수정테스트', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.put(f'/api/posts/{post_id}', headers=other_user['headers'], json={'title': '해킹시도'})
    assert r.status_code == 403
    assert r.get_json()['code'] == 'FORBIDDEN'


def test_update_post_owner_succeeds(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '원제목', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.put(f'/api/posts/{post_id}', headers=user['headers'], json={'title': '수정된제목'})
    assert r.status_code == 200

    r = client.get(f'/api/posts/{post_id}')
    assert r.get_json()['data']['title'] == '수정된제목'


def test_delete_post_owner_succeeds(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '삭제될글', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.delete(f'/api/posts/{post_id}', headers=user['headers'])
    assert r.status_code == 200

    r = client.get(f'/api/posts/{post_id}')
    assert r.status_code == 404  # deleted_at IS NULL 조건에서 제외됨


def test_delete_post_forbidden_for_non_owner(client, user, other_user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '삭제방어테스트', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.delete(f'/api/posts/{post_id}', headers=other_user['headers'])
    assert r.status_code == 403


def test_create_study_post_rejects_unknown_linked_exam(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '시험연동테스트', 'content': '', 'type': 'study',
        'linked_exam_name': '존재하지않는시험이름_xyz'
    })
    assert r.status_code == 404
    assert r.get_json()['code'] == 'EXAM_NOT_FOUND'


def test_update_study_status_only_by_owner_and_only_for_study_type(client, user, other_user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '일반글', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.patch(f'/api/posts/{post_id}/status', headers=user['headers'], json={'status': 'closed'})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_TYPE'

    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '모집글', 'content': '', 'type': 'study'
    })
    study_id = r.get_json()['data']['id']

    r = client.patch(f'/api/posts/{study_id}/status', headers=other_user['headers'], json={'status': 'closed'})
    assert r.status_code == 403

    r = client.patch(f'/api/posts/{study_id}/status', headers=user['headers'], json={'status': 'invalid'})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_STATUS'

    r = client.patch(f'/api/posts/{study_id}/status', headers=user['headers'], json={'status': 'closed'})
    assert r.status_code == 200
