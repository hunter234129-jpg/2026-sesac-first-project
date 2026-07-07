from flask import Blueprint, jsonify, g
from datetime import timedelta
from db.connection import get_db
from utils.auth import login_required

achievement_bp = Blueprint('achievement', __name__)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})


# 업적 카탈로그 — metric 값이 threshold 이상이면 달성
ACHIEVEMENTS = [
    {'key': 'first_session', 'emoji': '🌱', 'title': '첫 발걸음',      'desc': '첫 공부 세션을 완료했어요',   'category': '시작', 'metric': 'sessions',          'threshold': 1},
    {'key': 'h10',           'emoji': '⏱️', 'title': '10시간 클럽',     'desc': '누적 10시간 공부',           'category': '시간', 'metric': 'hours',             'threshold': 10},
    {'key': 'h100',          'emoji': '🔥', 'title': '100시간 클럽',    'desc': '누적 100시간 공부',          'category': '시간', 'metric': 'hours',             'threshold': 100},
    {'key': 'h500',          'emoji': '☄️', 'title': '500시간 여정',    'desc': '누적 500시간 공부',          'category': '시간', 'metric': 'hours',             'threshold': 500},
    {'key': 'streak3',       'emoji': '📅', 'title': '삼일 연속',       'desc': '3일 연속 공부',              'category': '연속', 'metric': 'longest_streak',    'threshold': 3},
    {'key': 'streak7',       'emoji': '🗓️', 'title': '일주일 개근',     'desc': '7일 연속 공부',              'category': '연속', 'metric': 'longest_streak',    'threshold': 7},
    {'key': 'streak30',      'emoji': '🏆', 'title': '한 달 개근',      'desc': '30일 연속 공부',             'category': '연속', 'metric': 'longest_streak',    'threshold': 30},
    {'key': 'days30',        'emoji': '📆', 'title': '꾸준함의 증거',   'desc': '총 30일 공부',               'category': '습관', 'metric': 'days',              'threshold': 30},
    {'key': 'marathon',      'emoji': '💪', 'title': '마라톤 세션',     'desc': '한 세션 3시간 이상 공부',     'category': '습관', 'metric': 'max_session_hours', 'threshold': 3},
    {'key': 'night_owl',     'emoji': '🦉', 'title': '밤의 수호자',     'desc': '자정~새벽 4시 사이 공부',     'category': '습관', 'metric': 'night_sessions',    'threshold': 1},
    {'key': 'early_bird',    'emoji': '🐤', 'title': '아침형 인간',     'desc': '새벽 5~7시에 공부 시작',      'category': '습관', 'metric': 'early_sessions',    'threshold': 1},
    {'key': 'social_post',   'emoji': '✍️', 'title': '지식 공유자',     'desc': '게시글을 작성했어요',         'category': '활동', 'metric': 'posts',             'threshold': 1},
    {'key': 'social_clan',   'emoji': '🛡️', 'title': '동료와 함께',     'desc': '모임에 참가했어요',           'category': '활동', 'metric': 'clans',             'threshold': 1},
]


def _compute_metrics(cursor, user_id):
    """업적 평가에 필요한 사용자 지표를 한 번에 계산."""
    cursor.execute(
        '''SELECT COUNT(*)                          AS sessions,
                  COALESCE(SUM(duration_sec), 0)     AS total_sec,
                  COALESCE(MAX(duration_sec), 0)     AS max_sec,
                  COUNT(DISTINCT DATE(started_at))   AS days,
                  SUM(CASE WHEN HOUR(started_at) BETWEEN 0 AND 3 THEN 1 ELSE 0 END) AS night_sessions,
                  SUM(CASE WHEN HOUR(started_at) IN (5, 6)       THEN 1 ELSE 0 END) AS early_sessions
           FROM study_sessions
           WHERE user_id = %s AND ended_at IS NOT NULL AND duration_sec > 0''',
        (user_id,)
    )
    s = cursor.fetchone() or {}

    # 최장 연속일
    cursor.execute(
        '''SELECT DISTINCT DATE(started_at) AS d
           FROM study_sessions
           WHERE user_id = %s AND ended_at IS NOT NULL AND duration_sec > 0''',
        (user_id,)
    )
    dates = sorted(r['d'] for r in cursor.fetchall())
    longest = 0
    if dates:
        one = timedelta(days=1)
        run = longest = 1
        for i in range(1, len(dates)):
            run = run + 1 if dates[i] - dates[i - 1] == one else 1
            longest = max(longest, run)

    cursor.execute('SELECT COUNT(*) AS c FROM posts WHERE user_id = %s AND deleted_at IS NULL', (user_id,))
    posts = cursor.fetchone()['c']
    cursor.execute('SELECT COUNT(*) AS c FROM post_members WHERE user_id = %s AND left_at IS NULL', (user_id,))
    clans = cursor.fetchone()['c']

    total_sec = int(s.get('total_sec') or 0)
    return {
        'sessions':          int(s.get('sessions') or 0),
        'hours':             total_sec / 3600,
        'days':              int(s.get('days') or 0),
        'longest_streak':    longest,
        'max_session_hours': int(s.get('max_sec') or 0) / 3600,
        'night_sessions':    int(s.get('night_sessions') or 0),
        'early_sessions':    int(s.get('early_sessions') or 0),
        'posts':             int(posts or 0),
        'clans':             int(clans or 0),
    }


@achievement_bp.route('/api/achievements', methods=['GET'])
@login_required
def list_achievements():
    """업적 목록 조회. 방문 시 새로 달성한 업적을 자동으로 획득 처리."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        metrics = _compute_metrics(cursor, g.user_id)

        cursor.execute(
            'SELECT achievement_key, unlocked_at FROM user_achievements WHERE user_id = %s',
            (g.user_id,)
        )
        unlocked = {r['achievement_key']: r['unlocked_at'] for r in cursor.fetchall()}

        newly = []
        for a in ACHIEVEMENTS:
            if metrics.get(a['metric'], 0) >= a['threshold'] and a['key'] not in unlocked:
                cursor.execute(
                    'INSERT IGNORE INTO user_achievements (user_id, achievement_key) VALUES (%s, %s)',
                    (g.user_id, a['key'])
                )
                newly.append(a['key'])
        if newly:
            conn.commit()
            cursor.execute(
                'SELECT achievement_key, unlocked_at FROM user_achievements WHERE user_id = %s',
                (g.user_id,)
            )
            unlocked = {r['achievement_key']: r['unlocked_at'] for r in cursor.fetchall()}
    finally:
        conn.close()

    items = []
    for a in ACHIEVEMENTS:
        cur    = metrics.get(a['metric'], 0)
        is_un  = a['key'] in unlocked
        items.append({
            'key':         a['key'],
            'emoji':       a['emoji'],
            'title':       a['title'],
            'desc':        a['desc'],
            'category':    a['category'],
            'threshold':   a['threshold'],
            'current':     round(cur, 1) if isinstance(cur, float) else cur,
            'progress':    min(1.0, cur / a['threshold']) if a['threshold'] else 1.0,
            'unlocked':    is_un,
            'unlocked_at': str(unlocked[a['key']]) if is_un else None,
            'newly':       a['key'] in newly,
        })

    return ok({
        'achievements':   items,
        'unlocked_count': sum(1 for i in items if i['unlocked']),
        'total_count':    len(items),
        'newly_unlocked': newly,
    })
