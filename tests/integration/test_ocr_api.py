"""OCR(routes/ocr.py) API 통합테스트.

실제로는 google.genai.Client로 Gemini에 이미지를 보내 텍스트를 추출한다. 실제
호출 대신 google.genai.Client 자체를 가짜로 바꿔치기해서, 파일/URL 입력 처리와
MIME 판별·에러 분기만 검증한다(진짜 이미지 바이트는 필요 없음 — 확장자만으로
MIME이 결정되는 경로를 이용).
"""
import io

import pytest

pytestmark = pytest.mark.integration


def _make_fake_genai_client(text=None, raise_error=None):
    """google.genai.Client를 대체할 가짜 클래스를 만든다."""
    class _FakeResponse:
        pass

    class _FakeModels:
        def generate_content(self, model, contents):
            if raise_error:
                raise raise_error
            resp = _FakeResponse()
            resp.text = text
            return resp

    class _FakeClient:
        def __init__(self, api_key=None):
            self.models = _FakeModels()

    return _FakeClient


def test_ocr_requires_auth(client):
    r = client.post('/api/ocr', data={}, content_type='multipart/form-data')
    assert r.status_code == 401


def test_ocr_no_input_rejected(client, user):
    r = client.post('/api/ocr', headers=user['headers'], data={}, content_type='multipart/form-data')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'NO_INPUT'


def test_ocr_no_api_key_returns_500(client, user, monkeypatch):
    monkeypatch.setattr('routes.ocr.GEMINI_API_KEY', '')
    data = {'file': (io.BytesIO(b'fake image bytes'), 'test.png')}
    r = client.post('/api/ocr', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 500
    assert r.get_json()['code'] == 'NO_API_KEY'


def test_ocr_unsupported_file_type_rejected(client, user):
    # 확장자가 없어서 MIME_BY_EXT로도 못 찾고, 내용도 PDF 매직바이트/유효한 이미지가 아니라
    # 결국 application/octet-stream으로 판별돼 지원 형식 밖으로 걸러진다.
    data = {'file': (io.BytesIO(b'not a real image at all'), 'note')}
    r = client.post('/api/ocr', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'UNSUPPORTED_TYPE'


def test_ocr_image_file_success(client, user, monkeypatch):
    monkeypatch.setattr('google.genai.Client', _make_fake_genai_client(text='추출된 텍스트입니다'))
    data = {'file': (io.BytesIO(b'fake image bytes'), 'test.png')}
    r = client.post('/api/ocr', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['text'] == '추출된 텍스트입니다'
    assert body['length'] == len('추출된 텍스트입니다')


def test_ocr_empty_extracted_text_message(client, user, monkeypatch):
    monkeypatch.setattr('google.genai.Client', _make_fake_genai_client(text=''))
    data = {'file': (io.BytesIO(b'fake image bytes'), 'test.png')}
    r = client.post('/api/ocr', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 200
    assert r.get_json()['message'] == '추출된 텍스트가 없어요'


def test_ocr_url_input_success(client, user, monkeypatch):
    monkeypatch.setattr('routes.ocr._fetch_url', lambda url: (b'fake image bytes', 'image/png'))
    monkeypatch.setattr('google.genai.Client', _make_fake_genai_client(text='URL에서 추출한 텍스트'))

    r = client.post('/api/ocr', headers=user['headers'],
                     data={'url': 'https://example.com/fake.png'}, content_type='multipart/form-data')
    assert r.status_code == 200
    assert r.get_json()['data']['text'] == 'URL에서 추출한 텍스트'


def test_ocr_url_fetch_failure_rejected(client, user, monkeypatch):
    def _raise(url):
        raise RuntimeError('연결 실패')

    monkeypatch.setattr('routes.ocr._fetch_url', _raise)
    r = client.post('/api/ocr', headers=user['headers'],
                     data={'url': 'https://example.com/broken.png'}, content_type='multipart/form-data')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'URL_FETCH_FAILED'


def test_ocr_processing_failure_returns_500(client, user, monkeypatch):
    monkeypatch.setattr('google.genai.Client', _make_fake_genai_client(raise_error=RuntimeError('모델 오류')))
    data = {'file': (io.BytesIO(b'fake image bytes'), 'test.png')}
    r = client.post('/api/ocr', headers=user['headers'], data=data, content_type='multipart/form-data')
    assert r.status_code == 500
    assert r.get_json()['code'] == 'OCR_FAILED'
