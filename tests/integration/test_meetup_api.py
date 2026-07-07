"""스터디 모집글(=모임) 멤버십 + 그룹채팅 API 통합테스트."""
import pytest

pytestmark = pytest.mark.integration


def create_meetup(client, user, title='모임테스트'):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': title, 'content': '', 'type': 'study'
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def test_creator_auto_joined_as_member(client, user):
    post_id = create_meetup(client, user)
    r = client.get(f'/api/posts/{post_id}/members')
    assert r.status_code == 200
    members = r.get_json()['data']
    assert len(members) == 1
    assert members[0]['username'] == user['username']


def test_members_endpoint_requires_study_type(client, user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '일반글', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.get(f'/api/posts/{post_id}/members')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_TYPE'


def test_leader_cannot_leave(client, user):
    post_id = create_meetup(client, user)
    r = client.delete(f'/api/posts/{post_id}/leave', headers=user['headers'])
    assert r.status_code == 400
    assert r.get_json()['code'] == 'LEADER_CANNOT_LEAVE'


def test_join_then_duplicate_join_rejected(client, user, other_user):
    post_id = create_meetup(client, user)

    r = client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])
    assert r.status_code == 201

    r = client.get(f'/api/posts/{post_id}/members')
    assert len(r.get_json()['data']) == 2

    r = client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])
    assert r.status_code == 409
    assert r.get_json()['code'] == 'ALREADY_JOINED'


def test_leave_then_rejoin(client, user, other_user):
    post_id = create_meetup(client, user)
    client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])

    r = client.delete(f'/api/posts/{post_id}/leave', headers=other_user['headers'])
    assert r.status_code == 200

    r = client.get(f'/api/posts/{post_id}/members')
    assert len(r.get_json()['data']) == 1

    r = client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])
    assert r.status_code == 201

    r = client.get(f'/api/posts/{post_id}/members')
    assert len(r.get_json()['data']) == 2


def test_leave_without_membership_rejected(client, user, other_user):
    post_id = create_meetup(client, user)
    r = client.delete(f'/api/posts/{post_id}/leave', headers=other_user['headers'])
    assert r.status_code == 404
    assert r.get_json()['code'] == 'NOT_MEMBER'


def test_join_requires_study_type(client, user, other_user):
    r = client.post('/api/posts', headers=user['headers'], json={
        'title': '일반글', 'content': '', 'type': 'post'
    })
    post_id = r.get_json()['data']['id']

    r = client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_TYPE'


def test_chat_history_requires_membership(client, user, other_user):
    post_id = create_meetup(client, user)
    r = client.get(f'/api/posts/{post_id}/chat', headers=other_user['headers'])
    assert r.status_code == 403
    assert r.get_json()['code'] == 'NOT_MEMBER'


def test_chat_history_visible_to_active_member(client, user):
    post_id = create_meetup(client, user)
    r = client.get(f'/api/posts/{post_id}/chat', headers=user['headers'])
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['is_active_member'] is True
    assert body['messages'] == []


def test_chat_history_inaccessible_after_leaving_non_leader(client, user, other_user):
    post_id = create_meetup(client, user)
    client.post(f'/api/posts/{post_id}/join', headers=other_user['headers'])
    client.delete(f'/api/posts/{post_id}/leave', headers=other_user['headers'])

    r = client.get(f'/api/posts/{post_id}/chat', headers=other_user['headers'])
    assert r.status_code == 200
    assert r.get_json()['data']['is_active_member'] is False
