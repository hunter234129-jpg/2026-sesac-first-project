"""신규 마이그레이션을 config.py의 DB 접속 정보로 실행하는 스크립트.

schema.sql의 CREATE TABLE IF NOT EXISTS는 테이블이 "이미 있으면" 아무것도 안 하기 때문에,
예전에 studyboard DB를 먼저 만들어 쓰던 사람이 최신 schema.sql을 다시 실행해도
기존 테이블에 새로 추가된 컬럼(avatar_id 등)은 반영되지 않는다. 이 스크립트가 그 차이를 메운다.
새로 생긴 테이블(post_members 등)도 여기서 CREATE TABLE IF NOT EXISTS로 같이 만들어준다 —
팀원이 mysql로 schema.sql을 다시 안 돌리고 이 스크립트만 실행해도 최신 상태로 맞춰지게 하기 위함.

실행: venv\\Scripts\\python.exe run_schema.py
여러 번 실행해도 안전함(이미 적용된 컬럼/테이블은 건너뜀).
"""
import pymysql
from config import DB_CONFIG

# 클랜 폐지 → 게시판 "스터디 모집" 게시글(모임)로 역할 통합하면서 새로 생긴 테이블.
# schema.sql에도 동일하게 정의돼 있지만, 기존 DB를 쓰는 사람은 이 스크립트만 돌려도
# 바로 반영되도록 여기서도 만든다(IF NOT EXISTS라 중복 실행해도 안전).
CREATE_TABLES = [
    """CREATE TABLE IF NOT EXISTS post_members (
        post_id            INT NOT NULL,
        user_id            INT NOT NULL,
        contribution_score INT DEFAULT 0,
        joined_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        left_at            DATETIME DEFAULT NULL,
        PRIMARY KEY (post_id, user_id),
        FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS post_chat_messages (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        post_id    INT NOT NULL,
        sender_id  INT DEFAULT NULL,
        msg_type   ENUM('text','file','system') DEFAULT 'text',
        content    TEXT,
        file_url   VARCHAR(255) DEFAULT NULL,
        file_name  VARCHAR(255) DEFAULT NULL,
        file_size  INT          DEFAULT NULL,
        mime_type  VARCHAR(100) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (post_id)   REFERENCES posts(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL,
        INDEX idx_post_created (post_id, created_at)
    )""",
]

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
    # chat_messages (파일 첨부 지원)
    "ALTER TABLE chat_messages ADD COLUMN msg_type ENUM('text','file') DEFAULT 'text' AFTER content",
    "ALTER TABLE chat_messages ADD COLUMN file_url VARCHAR(255) DEFAULT NULL AFTER msg_type",
    "ALTER TABLE chat_messages ADD COLUMN file_name VARCHAR(255) DEFAULT NULL AFTER file_url",
    "ALTER TABLE chat_messages ADD COLUMN mime_type VARCHAR(100) DEFAULT NULL AFTER file_name",
    # chat_messages (파일 크기 — 코드는 이미 참조하는데 컬럼이 누락돼 있던 기존 버그 수정)
    "ALTER TABLE chat_messages ADD COLUMN file_size INT DEFAULT NULL AFTER file_name",
    # posts (클랜 폐지 → 스터디 모집 게시글이 모임 역할을 흡수, 시험 연동)
    "ALTER TABLE posts ADD COLUMN linked_exam_name VARCHAR(150) DEFAULT NULL AFTER field",
]

# 클랜 시스템 폐지(스터디 모집 게시글로 역할 통합) — 실제 운영 데이터가 있다면 이
# 스크립트를 돌리기 전에 clan_members/clan_chat_messages를 post_members/
# post_chat_messages로 옮기는 마이그레이션을 먼저 실행해야 한다
# (지금은 테스트 데이터뿐이라 바로 DROP한다). 순서 중요 — FK 참조 역순으로 지운다.
DROP_TABLES = ['clan_chat_messages', 'clan_members', 'clans']

conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
try:
    for sql in CREATE_TABLES:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            conn.commit()
            print('생성(없었다면):', sql.strip().splitlines()[0])

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

    for table in DROP_TABLES:
        with conn.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS {table}')
            conn.commit()
            print('삭제(있었다면):', table)

    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM users")
        print('\nusers 컬럼 확인:')
        for row in cursor.fetchall():
            print(' ', row['Field'])
        cursor.execute("SHOW COLUMNS FROM chat_messages")
        print('\nchat_messages 컬럼 확인:')
        for row in cursor.fetchall():
            print(' ', row['Field'])
        cursor.execute("SHOW COLUMNS FROM posts")
        print('\nposts 컬럼 확인:')
        for row in cursor.fetchall():
            print(' ', row['Field'])
        cursor.execute("SHOW TABLES LIKE 'post\\_%'")
        print('\npost_* 테이블 확인(post_members/post_chat_messages 있어야 함):')
        for row in cursor.fetchall():
            print(' ', list(row.values())[0])
finally:
    conn.close()
