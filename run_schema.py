"""신규 마이그레이션을 config.py의 DB 접속 정보로 실행하는 스크립트.

schema.sql의 CREATE TABLE IF NOT EXISTS는 테이블이 "이미 있으면" 아무것도 안 하기 때문에,
예전에 studyboard DB를 먼저 만들어 쓰던 사람이 최신 schema.sql을 다시 실행해도
기존 테이블에 새로 추가된 컬럼(avatar_id 등)은 반영되지 않는다. 이 스크립트가 그 차이를 메운다.

실행: venv\\Scripts\\python.exe run_schema.py
여러 번 실행해도 안전함(이미 적용된 컬럼은 건너뜀).
"""
import pymysql
from config import DB_CONFIG

MIGRATIONS = [
    # users
    "ALTER TABLE users ADD COLUMN real_name VARCHAR(50) DEFAULT NULL AFTER password_hash",
    "ALTER TABLE users ADD COLUMN interest_keywords TEXT DEFAULT NULL AFTER real_name",
    "ALTER TABLE users ADD COLUMN avatar_id SMALLINT NOT NULL DEFAULT 0 AFTER interest_keywords",
    "ALTER TABLE users ADD COLUMN is_verified TINYINT(1) DEFAULT 0 AFTER is_admin",
    "ALTER TABLE users ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 AFTER is_verified",
    "ALTER TABLE users ADD COLUMN deleted_at DATETIME DEFAULT NULL AFTER is_deleted",
    # posts
    "ALTER TABLE posts ADD COLUMN deleted_at DATETIME DEFAULT NULL AFTER field",
    # wiki_pages
    "ALTER TABLE wiki_pages ADD COLUMN drawing_data LONGTEXT DEFAULT NULL AFTER view_count",
    # clans (클랜전 주간 목표)
    "ALTER TABLE clans ADD COLUMN weekly_goal_min INT DEFAULT 600 AFTER leader_id",
    # chat_messages (파일 첨부 지원)
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
        cursor.execute("SHOW COLUMNS FROM users")
        print('\nusers 컬럼 확인:')
        for row in cursor.fetchall():
            print(' ', row['Field'])
        cursor.execute("SHOW COLUMNS FROM chat_messages")
        print('\nchat_messages 컬럼 확인:')
        for row in cursor.fetchall():
            print(' ', row['Field'])
finally:
    conn.close()
