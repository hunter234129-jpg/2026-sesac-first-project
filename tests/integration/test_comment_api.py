"""게시글 댓글(routes/comment.py) API 통합테스트."""
import pytest

pytestmark = pytest.mark.integration


def create_post(client, user, title='댓글테스트글'):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': title, 'content': '', 'type': 'post'
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def test_get_comments_empty_initially(client, user):
    post_id = create_post(client, user)
    r = client.get(f'/api/posts/{post_id}/comments')
    assert r.status_code == 200
    assert r.get_json()['data'] == []


def test_create_comment_requires_auth(client, user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', json={'content': '댓글'})
    assert r.status_code == 401


def test_create_comment_requires_content(client, user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': ''})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_CONTENT'


def test_create_comment_on_unknown_post_returns_404(client, user):
    r = client.post('/api/posts/999999999/comments', headers=user['headers'], json={'content': '댓글'})
    assert r.status_code == 404


def test_create_and_list_top_level_comment(client, user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '첫 댓글'})
    assert r.status_code == 201

    r = client.get(f'/api/posts/{post_id}/comments')
    comments = r.get_json()['data']
    assert len(comments) == 1
    assert comments[0]['content'] == '첫 댓글'
    assert comments[0]['replies'] == []


def test_reply_comment_nests_under_parent(client, user, other_user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '부모 댓글'})
    parent_id = r.get_json()['data']['id']

    r = client.post(f'/api/posts/{post_id}/comments', headers=other_user['headers'], json={
        'content': '답글', 'parent_id': parent_id
    })
    assert r.status_code == 201

    r = client.get(f'/api/posts/{post_id}/comments')
    comments = r.get_json()['data']
    assert len(comments) == 1   # 최상위엔 부모 댓글 하나만
    assert len(comments[0]['replies']) == 1
    assert comments[0]['replies'][0]['content'] == '답글'


def test_update_comment_requires_content(client, user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '원본'})
    cid = r.get_json()['data']['id']

    r = client.put(f'/api/posts/{post_id}/comments/{cid}', headers=user['headers'], json={'content': ''})
    assert r.status_code == 400
    assert r.get_json()['code'] == 'MISSING_CONTENT'


def test_update_comment_forbidden_for_non_owner(client, user, other_user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '원본'})
    cid = r.get_json()['data']['id']

    r = client.put(f'/api/posts/{post_id}/comments/{cid}', headers=other_user['headers'], json={'content': '수정시도'})
    assert r.status_code == 403


def test_update_comment_owner_succeeds(client, user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '원본'})
    cid = r.get_json()['data']['id']

    r = client.put(f'/api/posts/{post_id}/comments/{cid}', headers=user['headers'], json={'content': '수정됨'})
    assert r.status_code == 200

    r = client.get(f'/api/posts/{post_id}/comments')
    assert r.get_json()['data'][0]['content'] == '수정됨'


def test_delete_comment_forbidden_for_non_owner(client, user, other_user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '원본'})
    cid = r.get_json()['data']['id']

    r = client.delete(f'/api/posts/{post_id}/comments/{cid}', headers=other_user['headers'])
    assert r.status_code == 403


def test_delete_comment_owner_succeeds(client, user):
    post_id = create_post(client, user)
    r = client.post(f'/api/posts/{post_id}/comments', headers=user['headers'], json={'content': '원본'})
    cid = r.get_json()['data']['id']

    r = client.delete(f'/api/posts/{post_id}/comments/{cid}', headers=user['headers'])
    assert r.status_code == 200

    r = client.get(f'/api/posts/{post_id}/comments')
    assert r.get_json()['data'] == []


def test_delete_unknown_comment_returns_404(client, user):
    post_id = create_post(client, user)
    r = client.delete(f'/api/posts/{post_id}/comments/999999999', headers=user['headers'])
    assert r.status_code == 404
