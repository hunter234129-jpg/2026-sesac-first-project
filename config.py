import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host':         os.getenv('DB_HOST',     'localhost'),
    'user':         os.getenv('DB_USER',     'root'),
    'password':     os.getenv('DB_PASSWORD', ''),
    'database':     os.getenv('DB_NAME',     'studyboard'),
    'charset':      'utf8mb4',
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
}

JWT_SECRET       = os.getenv('JWT_SECRET', 'change-this-secret')
JWT_EXPIRE_HOURS = 24

# 파일 업로드
UPLOAD_DIR         = os.getenv('UPLOAD_DIR', os.path.join(os.path.dirname(__file__), 'uploads'))
MAX_UPLOAD_BYTES   = 10 * 1024 * 1024   # 10MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'txt', 'docx', 'xlsx', 'pptx', 'zip'}

# OCR (Tesseract)
OCR_LANG = os.getenv('OCR_LANG', 'kor+eng')   # kor 데이터 미설치 시 자동으로 eng로 폴백

# AI 챗봇 (Claude API)
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL   = os.getenv('ANTHROPIC_MODEL', 'claude-opus-4-8')
