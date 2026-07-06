"""모임(스터디 모집글) 그룹 채팅 — 카카오톡 오픈채팅 방식.

1:1 채팅(chat_events.py)과 근본적으로 다른 점: 신청/수락 핸드셰이크가 없다.
모임 가입 자체가 이미 입장 승인이므로, 활성 멤버면 그냥 방에 join한다.
connect/disconnect 이벤트는 등록하지 않는다 — chat_events.py가 이미 등록해서
sid_user(소켓 sid -> user_id)를 관리하고 있고, Flask-SocketIO는 같은 이벤트에
핸들러가 여러 개면 나중에 import되는 쪽이 덮어써버리기 때문에(이 프로젝트에서
이미 한 번 겪은 버그) 새로 등록하지 않고 그 상태를 그대로 재사용한다.
"""
from flask import request
from flask_socketio import join_room, leave_room, emit

from extensions import socketio
from db.connection import get_db
from sockets.chat_events import sid_user, _contains_banned_word


def room_name(post_id):
    return f'post_{post_id}'


def _is_active_member(cursor, post_id, user_id):
    cursor.execute(
        'SELECT 1 FROM post_members WHERE post_id=%s AND user_id=%s AND left_at IS NULL',
        (post_id, user_id)
    )
    return cursor.fetchone() is not None


def post_system_message(post_id, text):
    """가입/탈퇴 시 REST 라우트(routes/post.py)에서 호출 — 시스템 메시지를 영구
    저장하고 지금 방에 있는 사람들에게 바로 보여준다."""
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO post_chat_messages (post_id, sender_id, msg_type, content) "
            "VALUES (%s, NULL, 'system', %s)",
            (post_id, text)
        )
        conn.commit()
        msg_id = cursor.lastrowid
    finally:
        conn.close()

    socketio.emit('post_message', {
        'id': msg_id, 'post_id': post_id, 'sender_id': None,
        'username': None, 'avatar_id': None, 'msg_type': 'system', 'content': text,
    }, room=room_name(post_id))


@socketio.on('join_post_chat')
def on_join_post_chat(data):
    user_id = sid_user.get(request.sid)
    post_id = (data or {}).get('post_id')
    if not user_id or not post_id:
        return
    conn   = get_db()
    cursor = conn.cursor()
    try:
        if not _is_active_member(cursor, post_id, user_id):
            return
    finally:
        conn.close()
    join_room(room_name(post_id))


@socketio.on('leave_post_chat')
def on_leave_post_chat(data):
    """페이지를 벗어날 때 소켓 room에서만 나간다 — 모임 탈퇴(REST /leave)와는 다른 이벤트."""
    post_id = (data or {}).get('post_id')
    if post_id:
        leave_room(room_name(post_id))


@socketio.on('post_message')
def on_post_message(data):
    data      = data or {}
    sender_id = sid_user.get(request.sid)
    post_id   = data.get('post_id')
    text      = (data.get('message') or '').strip()
    if not sender_id or not post_id or not text:
        return
    if len(text) > 1000:
        text = text[:1000]

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if not _is_active_member(cursor, post_id, sender_id):
            return
        if _contains_banned_word(text):
            emit('chat_blocked', {'post_id': post_id,
                                   'message': '비속어는 사용할 수 없습니다. 깨끗한 채팅 문화를 만들어주세요.'})
            return

        cursor.execute('SELECT username, avatar_id FROM users WHERE id=%s', (sender_id,))
        sender = cursor.fetchone()
        cursor.execute(
            "INSERT INTO post_chat_messages (post_id, sender_id, msg_type, content) "
            "VALUES (%s, %s, 'text', %s)",
            (post_id, sender_id, text)
        )
        conn.commit()
        msg_id = cursor.lastrowid
    finally:
        conn.close()

    socketio.emit('post_message', {
        'id': msg_id, 'post_id': post_id, 'sender_id': sender_id,
        'username': sender['username'], 'avatar_id': sender['avatar_id'],
        'msg_type': 'text', 'content': text,
    }, room=room_name(post_id))


@socketio.on('post_file')
def on_post_file(data):
    data      = data or {}
    sender_id = sid_user.get(request.sid)
    post_id   = data.get('post_id')
    file_url  = (data.get('file_url') or '').strip()
    file_name = (data.get('file_name') or '').strip()[:255]
    mime_type = (data.get('mime_type') or '').strip()[:100]
    try:
        file_size = int(data.get('file_size') or 0)
    except (ValueError, TypeError):
        file_size = 0
    if not sender_id or not post_id or not file_url or not file_name:
        return
    if not file_url.startswith('/api/files/'):
        emit('chat_error', {'message': '올바르지 않은 파일입니다.'})
        return

    conn   = get_db()
    cursor = conn.cursor()
    try:
        if not _is_active_member(cursor, post_id, sender_id):
            return
        cursor.execute('SELECT username, avatar_id FROM users WHERE id=%s', (sender_id,))
        sender = cursor.fetchone()
        content = f'\U0001F4CE {file_name}'
        cursor.execute(
            '''INSERT INTO post_chat_messages
                 (post_id, sender_id, msg_type, content, file_url, file_name, file_size, mime_type)
               VALUES (%s, %s, 'file', %s, %s, %s, %s, %s)''',
            (post_id, sender_id, content, file_url, file_name, file_size or None, mime_type)
        )
        conn.commit()
        msg_id = cursor.lastrowid
    finally:
        conn.close()

    socketio.emit('post_message', {
        'id': msg_id, 'post_id': post_id, 'sender_id': sender_id,
        'username': sender['username'], 'avatar_id': sender['avatar_id'],
        'msg_type': 'file', 'content': content,
        'file_url': file_url, 'file_name': file_name, 'file_size': file_size, 'mime_type': mime_type,
    }, room=room_name(post_id))
