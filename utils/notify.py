def notify_keyword_match(get_db, post_id, title, content):
    """게시글 등록 시 키워드 구독자에게 알림 생성"""
    text = f'{title} {content}'.lower()
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, keyword FROM keyword_subscriptions')
        subs = cursor.fetchall()
        for sub in subs:
            if sub['keyword'].lower() in text:
                cursor.execute(
                    '''INSERT INTO notifications (user_id, type, content, ref_type, ref_id)
                       VALUES (%s, 'keyword', %s, 'post', %s)''',
                    (sub['user_id'],
                     f'관심 키워드 [{sub["keyword"]}] 관련 게시글이 등록됐습니다.',
                     post_id)
                )
        conn.commit()
    finally:
        conn.close()
