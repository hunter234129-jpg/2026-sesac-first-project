import os
<<<<<<< HEAD
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
=======
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATHS = [BASE_DIR / '.env', BASE_DIR / '.env copy']

for env_path in ENV_PATHS:
    if env_path.exists():
        load_dotenv(env_path, override=True)
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed

DB_CONFIG = {
    'host':         os.getenv('DB_HOST',     '192.168.56.101'),
    'port':         int(os.getenv('DB_PORT', '3306')),
<<<<<<< HEAD
    'user':         os.getenv('DB_USER',     'scott'),
    'password':     os.getenv('DB_PASSWORD', 'tiger'),
=======
    'user':         os.getenv('DB_USER',     'yongkyu'),
    'password':     os.getenv('DB_PASSWORD', 'yongkyu'),
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed
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

<<<<<<< HEAD
# AI 챗봇 (Gemini API)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL   = os.getenv('GEMINI_MODEL', 'models/gemini-2.5-flash')
=======
# AI 챗봇 (Claude API)
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL   = os.getenv('ANTHROPIC_MODEL', 'claude-opus-4-8')
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed
