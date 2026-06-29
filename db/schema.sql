-- 스터디 게시판 DB 초기화
-- 실행: mysql -h 192.168.56.101 -u scott -p < db/schema.sql
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
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT         DEFAULT NULL,
    leader_id   INT          NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
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

-- ── Migration (기존 DB 보유 시 실행) ─────────────────────────────────
-- ALTER TABLE users
--   ADD COLUMN real_name         VARCHAR(50)  DEFAULT NULL AFTER password_hash,
--   ADD COLUMN interest_keywords TEXT         DEFAULT NULL AFTER real_name,
--   ADD COLUMN is_verified       TINYINT(1)   DEFAULT 0   AFTER is_admin,
--   ADD COLUMN is_deleted        TINYINT(1)   DEFAULT 0   AFTER is_verified,
--   ADD COLUMN deleted_at        DATETIME     DEFAULT NULL AFTER is_deleted;
--
-- ALTER TABLE posts
--   ADD COLUMN deleted_at DATETIME DEFAULT NULL AFTER field;
--
-- ALTER TABLE wiki_pages
--   ADD COLUMN drawing_data LONGTEXT DEFAULT NULL AFTER view_count;
