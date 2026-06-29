from flask import Blueprint, jsonify, request
from utils.auth import login_required
from config import OCR_LANG

ocr_bp = Blueprint('ocr', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


@ocr_bp.route('/api/ocr', methods=['POST'])
@login_required
def ocr_image():
    if 'file' not in request.files:
        return err('file 필드(이미지)가 필요합니다', 'NO_FILE')
    file = request.files['file']
    if not file or file.filename == '':
        return err('선택된 이미지가 없습니다', 'NO_FILE')

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return err('pytesseract / Pillow 패키지가 필요합니다 (pip install pytesseract pillow)',
                   'MISSING_DEPENDENCY', 500)

    try:
        img = Image.open(file.stream)
    except Exception:
        return err('이미지를 열 수 없습니다. 올바른 이미지 파일인지 확인하세요', 'INVALID_IMAGE')

    try:
        text = pytesseract.image_to_string(img, lang=OCR_LANG)
    except pytesseract.TesseractNotFoundError:
        return err('Tesseract 엔진이 설치되지 않았습니다. '
                   'Windows: https://github.com/UB-Mannheim/tesseract/wiki 에서 설치 후 PATH 등록',
                   'TESSERACT_NOT_FOUND', 500)
    except Exception as e:
        # 언어 데이터(kor) 미설치 등 → 영어로 폴백 재시도
        try:
            text = pytesseract.image_to_string(img, lang='eng')
        except Exception:
            return err(f'OCR 처리 실패: {e}', 'OCR_FAILED', 500)

    text = (text or '').strip()
    return ok({'text': text, 'length': len(text)},
              '텍스트를 추출했어요' if text else '추출된 텍스트가 없어요')
