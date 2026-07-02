"""신규 마이그레이션을 config.py의 DB 접속 정보로 실행하는 1회용 스크립트.
실행: venv\\Scripts\\python.exe run_schema.py
완료 후 삭제해도 무방합니다.
"""
import pymysql
from config import DB_CONFIG

MIGRATIONS = [
    "ALTER TABLE chat_messages ADD COLUMN msg_type ENUM('text','file') DEFAULT 'text' AFTER content",
    "ALTER TABLE chat_messages ADD COLUMN file_url VARCHAR(255) DEFAULT NULL AFTER msg_type",
    "ALTER TABLE chat_messages ADD COLUMN file_name VARCHAR(255) DEFAULT NULL AFTER file_url",
    "ALTER TABLE chat_messages ADD COLUMN mime_type VARCHAR(100) DEFAULT NULL AFTER file_name",
]

conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
try:
    for sql in MIGRATIONS:
        with conn.cursor() as cursor:
            try:
                cursor.execute(sql)
                conn.commit()
                print('적용:', sql)
            except pymysql.err.OperationalError as e:
                if e.args[0] == 1060:  # Duplicate column
                    print('건너뜀 (이미 존재):', sql)
                else:
                    raise

    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM chat_messages")
        print('\n확인:')
        for row in cursor.fetchall():
            print(' ', row)
finally:
    conn.close()
