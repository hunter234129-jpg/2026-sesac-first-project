"""파일 업로드 API 통합테스트."""
import io

import pytest

pytestmark = pytest.mark.integration


def test_upload_requires_auth(client):
    data = {'file': (io.BytesIO(b'hello'), 'test.txt')}
    r = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert r.status_code == 401


def test_upload_and_download_roundtrip(client, user):
    data = {'file': (io.BytesIO(b'hello upload'), 'test.txt')}
    r = client.post('/api/upload', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 201
    body = r.get_json()['data']
    assert body['url']

    r = client.get(body['url'])
    assert r.status_code == 200
    assert r.data == b'hello upload'


def test_upload_rejects_disallowed_extension(client, user):
    data = {'file': (io.BytesIO(b'binary'), 'malware.exe')}
    r = client.post('/api/upload', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'INVALID_EXTENSION'


def test_upload_missing_file_field_rejected(client, user):
    r = client.post('/api/upload', headers=user['headers'], data={}, content_type='multipart/form-data')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'NO_FILE'


def test_download_unknown_file_returns_404(client):
    r = client.get('/api/files/does-not-exist.txt')
    assert r.status_code == 404


def test_delete_file_forbidden_for_non_owner(client, user, other_user):
    data = {'file': (io.BytesIO(b'x'), 'a.txt')}
    r = client.post('/api/upload', headers=user['headers'], data=data, content_type='multipart/form-data')
    file_id = r.get_json()['data']['id']

    r = client.delete(f'/api/files/{file_id}', headers=other_user['headers'])
    assert r.status_code == 403
    assert r.get_json()['code'] == 'FORBIDDEN'


def test_delete_file_by_owner_succeeds(client, user):
    data = {'file': (io.BytesIO(b'y'), 'b.txt')}
    r = client.post('/api/upload', headers=user['headers'], data=data, content_type='multipart/form-data')
    file_id = r.get_json()['data']['id']

    r = client.delete(f'/api/files/{file_id}', headers=user['headers'])
    assert r.status_code == 200


def test_delete_unknown_file_returns_404(client, user):
    r = client.delete('/api/files/999999999', headers=user['headers'])
    assert r.status_code == 404
