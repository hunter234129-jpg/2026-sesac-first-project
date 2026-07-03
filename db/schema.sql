-- 스터디 게시판 DB 초기화
-- 실행: mysql -h 192.168.56.102 -u scott -p < db/schema.sql
--
-- 기존 DB가 있는 경우 맨 아래 Migration 섹션 참고

CREATE DATABASE IF NOT EXISTS studyboard
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE studyboard;

-- ── 회원 ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    username          VARCHAR(50)  NOT NULL UNIQUE,
    email             VARCHAR(100) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,
    real_name         VARCHAR(50)  DEFAULT NULL,
    interest_keywords TEXT         DEFAULT NULL,
    avatar_id         SMALLINT     NOT NULL DEFAULT 0,
    is_admin          TINYINT(1)   DEFAULT 0,
    is_verified       TINYINT(1)   DEFAULT 0,
    is_deleted        TINYINT(1)   DEFAULT 0,
    deleted_at        DATETIME     DEFAULT NULL,
    created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ── 게시판 ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS posts (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT          NOT NULL,
    title            VARCHAR(200) NOT NULL,
    content          TEXT,
    type             ENUM('post','study')  DEFAULT 'post',
    category         VARCHAR(50),
    status           ENUM('open','closed') DEFAULT 'open',
    view_count       INT  DEFAULT 0,
    recruit_count    INT  DEFAULT 0,
    recruit_deadline DATE,
    field            VARCHAR(100),
    deleted_at       DATETIME DEFAULT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS comments (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    post_id    INT  NOT NULL,
    user_id    INT  NOT NULL,
    content    TEXT NOT NULL,
    parent_id  INT  DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id)   REFERENCES posts(id)    ON DELETE CASCADE,
    FOREIGN KEY (user_id)   REFERENCES users(id),
    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
);

-- ── 위키 ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wiki_pages (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    title        VARCHAR(200) NOT NULL UNIQUE,
    slug         VARCHAR(200) NOT NULL UNIQUE,
    created_by   INT          NOT NULL,
    view_count   INT          DEFAULT 0,
    drawing_data LONGTEXT     DEFAULT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS wiki_revisions (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    wiki_id    INT  NOT NULL,
    author_id  INT  NOT NULL,
    content    LONGTEXT,
    summary    VARCHAR(200),
    version    INT NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wiki_id)   REFERENCES wiki_pages(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS wiki_view_logs (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    wiki_id   INT NOT NULL,
    user_id   INT DEFAULT NULL,
    ip_hash   VARCHAR(64),
    viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wiki_id) REFERENCES wiki_pages(id) ON DELETE CASCADE
);

-- ── 키워드 알림 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS keyword_subscriptions (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,
    keyword    VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_keyword (user_id, keyword),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT         NOT NULL,
    type       VARCHAR(50) NOT NULL,
    content    TEXT        NOT NULL,
    ref_type   VARCHAR(50) DEFAULT NULL,
    ref_id     INT         DEFAULT NULL,
    is_read    TINYINT(1)  DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── 스터디 세션 ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS study_sessions (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT      NOT NULL,
    started_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at     DATETIME DEFAULT NULL,
    duration_sec INT      DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── 클랜 ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clans (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT         DEFAULT NULL,
    leader_id       INT          NOT NULL,
    weekly_goal_min INT          DEFAULT 600,   -- 주간 공동 목표(분), 기본 10시간
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (leader_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS clan_members (
    clan_id            INT NOT NULL,
    user_id            INT NOT NULL,
    contribution_score INT DEFAULT 0,
    joined_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (clan_id, user_id),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── 미션 ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS missions (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    title      VARCHAR(200) NOT NULL,
    content    TEXT,
    date       DATE         NOT NULL,
    is_random  TINYINT(1)   DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_missions (
    user_id    INT NOT NULL,
    mission_id INT NOT NULL,
    is_done    TINYINT(1) DEFAULT 0,
    done_at    DATETIME   DEFAULT NULL,
    PRIMARY KEY (user_id, mission_id),
    FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

-- ── 실시간 1:1 채팅 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_rooms (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user1_id   INT      NOT NULL,
    user2_id   INT      NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at  DATETIME DEFAULT NULL,
    FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    room_id    INT  NOT NULL,
    sender_id  INT  NOT NULL,
    content    TEXT NOT NULL,
    msg_type   ENUM('text','file') DEFAULT 'text',
    file_url   VARCHAR(255) DEFAULT NULL,
    file_name  VARCHAR(255) DEFAULT NULL,
    mime_type  VARCHAR(100) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id)   REFERENCES chat_rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id)
);

-- ── 파일 ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS files (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,
    original    VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    mime_type  VARCHAR(100) DEFAULT NULL,
    ref_type   VARCHAR(50)  DEFAULT NULL,
    ref_id     INT          DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ── 위키 드로잉(Excalidraw 벡터 씬) ──────────────────────────────────
-- 벡터 데이터는 여기, PNG 스냅샷은 files 테이블에 저장(DB 비대화 방지)
CREATE TABLE IF NOT EXISTS wiki_drawings (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    wiki_id     INT          NOT NULL,
    block_id    VARCHAR(64)  NOT NULL,   -- Tiptap 노드의 고유 id (scene_id)
    scene_json  LONGTEXT,                -- Excalidraw elements+appState 원본(재편집용)
    png_file_id INT          DEFAULT NULL,
    updated_by  INT          NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wiki_block (wiki_id, block_id),
    FOREIGN KEY (wiki_id)     REFERENCES wiki_pages(id) ON DELETE CASCADE,
    FOREIGN KEY (png_file_id) REFERENCES files(id)      ON DELETE SET NULL,
    FOREIGN KEY (updated_by)  REFERENCES users(id)
);

-- ── 업적(뱃지) ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_achievements (
    user_id         INT         NOT NULL,
    achievement_key VARCHAR(50) NOT NULL,
    unlocked_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── AI 문제풀기(즉석 문제 생성) ────────────────────────────────────────
-- 사용자가 자유 텍스트로 요청("중2 수학 이차방정식")하면 Gemini가 그 자리에서
-- 문제를 만들어낸다. Gemini는 순수 JSON 출제 자판기 역할만 하고, 정답 판정·
-- 레벨(난이도) 추적·오답노트 적재는 전부 백엔드가 담당한다(상태는 여기 DB에 저장).

-- 사용자별 진행 중인 문제풀기 세션(진단 5문제 → 적응형 문제 반복) 상태
CREATE TABLE IF NOT EXISTS ai_quiz_state (
    user_id          INT NOT NULL PRIMARY KEY,
    subject_query    VARCHAR(300) NOT NULL,           -- 사용자가 입력한 요청 원문
    phase            ENUM('diagnostic','adaptive') NOT NULL DEFAULT 'diagnostic',
    level            TINYINT      DEFAULT NULL,        -- 1(하)~5(상), 진단 전엔 NULL
    correct_streak   INT NOT NULL DEFAULT 0,
    wrong_streak     INT NOT NULL DEFAULT 0,
    question_count   INT NOT NULL DEFAULT 0,
    correct_count    INT NOT NULL DEFAULT 0,           -- 진단 단계에서 맞은 개수
    diagnostic_total INT NOT NULL DEFAULT 5,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- AI가 즉석에서 생성한 문제(채점용으로 정답을 서버에 보관, 클라이언트엔 노출 안 함)
CREATE TABLE IF NOT EXISTS ai_quiz_questions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    subject_query VARCHAR(300) NOT NULL,
    phase         ENUM('diagnostic','adaptive') NOT NULL,
    level         TINYINT NOT NULL,       -- 1(하)~5(상)
    question      TEXT NOT NULL,
    choices       TEXT NOT NULL,          -- JSON 배열 문자열(보기 4개)
    answer_index  TINYINT NOT NULL,       -- 정답 보기 인덱스(0~3)
    explanation   TEXT,
    chosen_index  TINYINT DEFAULT NULL,
    answered      TINYINT(1) NOT NULL DEFAULT 0,
    correct       TINYINT(1) DEFAULT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── 오답노트 ─────────────────────────────────────────────────────────
-- AI 문제풀기에서 틀리면 자동으로 쌓인다(문제 자체가 매번 새로 생성되므로
-- 단원 단위가 아니라 틀린 문제 하나하나를 기록으로 남긴다).
CREATE TABLE IF NOT EXISTS ai_quiz_wrong_notes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    subject_query VARCHAR(300) NOT NULL,
    level         TINYINT NOT NULL,
    question      TEXT NOT NULL,
    choices       TEXT NOT NULL,
    answer_index  TINYINT NOT NULL,
    chosen_index  TINYINT NOT NULL,
    explanation   TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Migration (기존 DB 보유 시 실행) ─────────────────────────────────
-- ALTER TABLE users
--   ADD COLUMN real_name         VARCHAR(50)  DEFAULT NULL AFTER password_hash,
--   ADD COLUMN interest_keywords TEXT         DEFAULT NULL AFTER real_name,
--   ADD COLUMN is_verified       TINYINT(1)   DEFAULT 0   AFTER is_admin,
--   ADD COLUMN is_deleted        TINYINT(1)   DEFAULT 0   AFTER is_verified,
--   ADD COLUMN deleted_at        DATETIME     DEFAULT NULL AFTER is_deleted;
--
-- ALTER TABLE users
--   ADD COLUMN avatar_id SMALLINT NOT NULL DEFAULT 0 AFTER interest_keywords;
--
-- ALTER TABLE posts
--   ADD COLUMN deleted_at DATETIME DEFAULT NULL AFTER field;
--
-- ALTER TABLE wiki_pages
--   ADD COLUMN drawing_data LONGTEXT DEFAULT NULL AFTER view_count;
--
-- ALTER TABLE clans
--   ADD COLUMN weekly_goal_min INT DEFAULT 600 AFTER leader_id;
--
-- ALTER TABLE chat_messages
--   ADD COLUMN msg_type  ENUM('text','file') DEFAULT 'text' AFTER content,
--   ADD COLUMN file_url  VARCHAR(255) DEFAULT NULL AFTER msg_type,
--   ADD COLUMN file_name VARCHAR(255) DEFAULT NULL AFTER file_url,
--   ADD COLUMN mime_type VARCHAR(100) DEFAULT NULL AFTER file_name;
--
-- CREATE TABLE IF NOT EXISTS wiki_drawings (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     wiki_id     INT          NOT NULL,
--     block_id    VARCHAR(64)  NOT NULL,
--     scene_json  LONGTEXT,
--     png_file_id INT          DEFAULT NULL,
--     updated_by  INT          NOT NULL,
--     updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--     UNIQUE KEY uq_wiki_block (wiki_id, block_id),
--     FOREIGN KEY (wiki_id)     REFERENCES wiki_pages(id) ON DELETE CASCADE,
--     FOREIGN KEY (png_file_id) REFERENCES files(id)      ON DELETE SET NULL,
--     FOREIGN KEY (updated_by)  REFERENCES users(id)
-- );
--
-- CREATE TABLE IF NOT EXISTS curriculum_topics (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     subject     ENUM('국어','영어','수학') NOT NULL,
--     grade       ENUM('중1','중2','중3','고1','고2','고3') NOT NULL,
--     step_order  INT          NOT NULL,
--     unit_name   VARCHAR(100) NOT NULL,
--     description VARCHAR(255) DEFAULT NULL,
--     created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE KEY uq_subject_order (subject, step_order)
-- );
--
-- CREATE TABLE IF NOT EXISTS user_topic_progress (
--     user_id    INT NOT NULL,
--     topic_id   INT NOT NULL,
--     is_done    TINYINT(1) DEFAULT 0,
--     done_at    DATETIME   DEFAULT NULL,
--     PRIMARY KEY (user_id, topic_id),
--     FOREIGN KEY (user_id)  REFERENCES users(id)             ON DELETE CASCADE,
--     FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE CASCADE
-- );
--
-- -- 이해도 자가진단(약점 추천 기능) 컬럼 추가
-- ALTER TABLE user_topic_progress
--   ADD COLUMN understanding TINYINT DEFAULT NULL AFTER is_done;
--
-- -- 단원별 확인 문제(1문제, 4지선다) 테이블 추가
-- CREATE TABLE IF NOT EXISTS curriculum_quiz (
--     id           INT AUTO_INCREMENT PRIMARY KEY,
--     topic_id     INT  NOT NULL UNIQUE,
--     question     TEXT NOT NULL,
--     choices      TEXT NOT NULL,
--     answer_index TINYINT NOT NULL,
--     explanation  VARCHAR(255) DEFAULT NULL,
--     created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
--     FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE CASCADE
-- );
--
-- -- 오답노트 테이블 추가
-- CREATE TABLE IF NOT EXISTS wrong_notes (
--     id            INT AUTO_INCREMENT PRIMARY KEY,
--     user_id       INT NOT NULL,
--     topic_id      INT NOT NULL,
--     chosen_index  TINYINT NOT NULL,
--     wrong_count   INT NOT NULL DEFAULT 1,
--     last_wrong_at DATETIME DEFAULT CURRENT_TIMESTAMP,
--     created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE KEY uq_user_topic (user_id, topic_id),
--     FOREIGN KEY (user_id)  REFERENCES users(id)             ON DELETE CASCADE,
--     FOREIGN KEY (topic_id) REFERENCES curriculum_topics(id) ON DELETE CASCADE
-- );
--
-- -- ── "학습가이드"(교육과정 로드맵) → "문제풀기"(AI 즉석 문제 생성)로 전환 ──
-- -- 기존 커리큘럼 기반 테이블을 걷어내고 AI 문제풀기용 테이블로 교체한다.
-- DROP TABLE IF EXISTS wrong_notes;
-- DROP TABLE IF EXISTS curriculum_quiz;
-- DROP TABLE IF EXISTS user_topic_progress;
-- DROP TABLE IF EXISTS curriculum_topics;
--
-- CREATE TABLE IF NOT EXISTS ai_quiz_state (
--     user_id          INT NOT NULL PRIMARY KEY,
--     subject_query    VARCHAR(300) NOT NULL,
--     phase            ENUM('diagnostic','adaptive') NOT NULL DEFAULT 'diagnostic',
--     level            TINYINT      DEFAULT NULL,
--     correct_streak   INT NOT NULL DEFAULT 0,
--     wrong_streak     INT NOT NULL DEFAULT 0,
--     question_count   INT NOT NULL DEFAULT 0,
--     correct_count    INT NOT NULL DEFAULT 0,
--     diagnostic_total INT NOT NULL DEFAULT 5,
--     updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
-- );
--
-- CREATE TABLE IF NOT EXISTS ai_quiz_questions (
--     id            INT AUTO_INCREMENT PRIMARY KEY,
--     user_id       INT NOT NULL,
--     subject_query VARCHAR(300) NOT NULL,
--     phase         ENUM('diagnostic','adaptive') NOT NULL,
--     level         TINYINT NOT NULL,
--     question      TEXT NOT NULL,
--     choices       TEXT NOT NULL,
--     answer_index  TINYINT NOT NULL,
--     explanation   TEXT,
--     chosen_index  TINYINT DEFAULT NULL,
--     answered      TINYINT(1) NOT NULL DEFAULT 0,
--     correct       TINYINT(1) DEFAULT NULL,
--     created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
-- );
--
-- CREATE TABLE IF NOT EXISTS ai_quiz_wrong_notes (
--     id            INT AUTO_INCREMENT PRIMARY KEY,
--     user_id       INT NOT NULL,
--     subject_query VARCHAR(300) NOT NULL,
--     level         TINYINT NOT NULL,
--     question      TEXT NOT NULL,
--     choices       TEXT NOT NULL,
--     answer_index  TINYINT NOT NULL,
--     chosen_index  TINYINT NOT NULL,
--     explanation   TEXT,
--     created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
-- );
