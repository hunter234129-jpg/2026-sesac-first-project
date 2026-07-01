import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

DB_CONFIG = {
    'host':         os.getenv('DB_HOST',     '192.168.56.101'),
    'port':         int(os.getenv('DB_PORT', '3306')),
    'user':         os.getenv('DB_USER',     'scott'),
    'password':     os.getenv('DB_PASSWORD', 'tiger'),
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
OCR_LANG = os.getenv('OCR_LANG', 'korean')   # PaddleOCR 언어코드: korean, en, ch 등

# AI 챗봇 (Gemini API)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL   = os.getenv('GEMINI_MODEL', 'models/gemini-2.5-flash')
