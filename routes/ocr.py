from flask import Blueprint, jsonify, request
from utils.auth import login_required
from config import GEMINI_API_KEY, GEMINI_MODEL

ocr_bp = Blueprint('ocr', __name__)

MIME_BY_EXT = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png',  '.gif':  'image/gif',
    '.webp': 'image/webp', '.bmp': 'image/bmp',
    '.pdf': 'application/pdf',
}

OCR_PROMPT = (
    '이미지에 보이는 텍스트만 정확히 옮겨줘.\n'
    '절대 규칙:\n'
    '1. 이미지에 없는 글자는 한 글자도 추가하지 마.\n'
    '2. 각 줄의 시작 위치(들여쓰기 칸 수)를 이미지와 똑같이 맞춰줘.\n'
    '3. 같은 열에 정렬된 텍스트는 공백으로 열을 맞춰줘.\n'
    '4. 줄바꿈은 이미지의 행 구분 그대로 따라줘.\n'
    '5. 설명·요약 없이 텍스트만 출력해.'
)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def _detect_mime(filename, content_type, data):
    import os
    ext = os.path.splitext(filename or '')[1].lower()
    if ext in MIME_BY_EXT:
        return MIME_BY_EXT[ext]
    if content_type:
        base = content_type.split(';')[0].strip()
        if base and base != 'application/octet-stream':
            return base
    # 매직 바이트로 판별
    if data[:4] == b'%PDF':
        return 'application/pdf'
    try:
        import io
        from PIL import Image
        fmt = Image.open(io.BytesIO(data)).format or 'JPEG'
        return {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif',
                'WEBP': 'image/webp', 'BMP': 'image/bmp'}.get(fmt.upper(), 'image/jpeg')
    except Exception:
        return 'application/octet-stream'


def _fetch_url(url):
    import requests as req
    resp = req.get(url, timeout=15)
    resp.raise_for_status()
    return resp.content, resp.headers.get('Content-Type', '')


@ocr_bp.route('/api/ocr', methods=['POST'])
@login_required
def ocr_image():
    if not GEMINI_API_KEY:
        return err('.env에 GEMINI_API_KEY가 설정되지 않았습니다', 'NO_API_KEY', 500)

    url = request.form.get('url', '').strip()
    has_file = 'file' in request.files and request.files['file'].filename != ''

    if not has_file and not url:
        return err('file 또는 url 필드가 필요합니다', 'NO_INPUT')

    # 데이터 수집
    if has_file:
        file = request.files['file']
        try:
            data = file.stream.read()
        except Exception:
            return err('파일을 읽을 수 없습니다', 'READ_FAILED')
        mime_type = _detect_mime(file.filename, file.content_type, data)
    else:
        try:
            data, content_type = _fetch_url(url)
            mime_type = _detect_mime(url, content_type, data)
        except Exception as e:
            return err(f'URL에서 파일을 가져올 수 없습니다: {e}', 'URL_FETCH_FAILED')

    if mime_type not in set(MIME_BY_EXT.values()):
        return err(f'지원하지 않는 파일 형식입니다 ({mime_type}). '
                   '지원 형식: jpg, png, gif, webp, bmp, pdf', 'UNSUPPORTED_TYPE')

    # Gemini OCR
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime_type),
                OCR_PROMPT,
            ]
        )
        text = (response.text or '').strip()
    except Exception as e:
        return err(f'OCR 처리 실패: {e}', 'OCR_FAILED', 500)

    return ok({'text': text, 'length': len(text)},
              '텍스트를 추출했어요' if text else '추출된 텍스트가 없어요')
