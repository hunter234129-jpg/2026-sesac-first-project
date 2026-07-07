"""실시간 1:1 채팅 — 접속 현황 · 채팅 신청/수락 · 실시간 메시지."""
import datetime
import itertools
import threading
import time

import jwt
from flask import request
from flask_socketio import join_room, leave_room, emit

from extensions import socketio
from db.connection import get_db
from utils.auth import decode_token

REJECT_COOLDOWN_SEC = 5 * 60
AVATAR_COUNT = 20   # static/js/chat-widget.js의 AVATARS 배열 길이와 일치해야 함
DISCONNECT_GRACE_SEC = 15   # 순간적인 네트워크 끊김/재연결을 "나감"으로 오판하지 않기 위한 유예 시간

_flask_app = None   # app.py가 init_app()으로 주입 — 백그라운드 타이머에서 app_context를 열기 위함


def init_app(app):
    global _flask_app
    _flask_app = app

# 채팅 비속어 필터 — 필요 시 목록만 추가/조정
BANNED_WORDS = [
    '바보', '멍청이', '병신', '븅신', '등신', '찐따', '찌질이', '쓰레기',
    '씨발', '시발', 'ㅅㅂ', 'ㅆㅂ', '개새끼', '개새기', '새끼', '지랄', '좆',
    '미친놈', '미친년', '닥쳐', '꺼져',
]


def _contains_banned_word(text):
    return any(word in text for word in BANNED_WORDS)

# ── 인메모리 상태 (단일 프로세스 개발 서버 기준) ──────────────────────
online_users     = {}                    # user_id -> {'username': str, 'avatar_id': int, 'sids': set()}
sid_user         = {}                    # sid -> user_id
pending_requests = {}                    # request_id -> {'from': user_id, 'to': user_id, 'pair': frozenset}
pending_pairs    = {}                    # frozenset({user_id, user_id}) -> request_id (쌍당 신청 1건 제한)
reject_cooldowns = {}                    # (rejected_from_id, rejecter_to_id) -> 재신청 가능 시각(epoch)
active_rooms     = {}                    # room_name -> {user_id, user_id}
room_db_id       = {}                    # room_name -> chat_rooms.id
room_member_info = {}                    # room_name -> {user_id: {'username': str, 'avatar_id': int}} (새로고침 복원용 스냅샷)
_req_ids         = itertools.count(1)


def _user_list():
    return [{'user_id': uid, 'username': info['username'], 'avatar_id': info.get('avatar_id', 0)}
            for uid, info in online_users.items()]


def _broadcast_online():
    socketio.emit('online_users', {'users': _user_list()})


def _room_name(user_a, user_b, req_id):
    lo, hi = sorted((user_a, user_b))
    return f'room_{lo}_{hi}_{req_id}'


def _active_rooms_for_user(user_id):
    """새로고침/페이지 이동 후 재접속 시 복원해줄 활성 채팅방 목록."""
    result = []
    for room_name, members in active_rooms.items():
        if user_id not in members:
            continue
        partner_id = next(iter(members - {user_id}), None)
        if partner_id is None:
            continue
        info = room_member_info.get(room_name, {}).get(partner_id, {})
        result.append({
            'room': room_name,
            'partner_id': partner_id,
            'partner_username': info.get('username', ''),
            'partner_avatar_id': info.get('avatar_id', 0),
        })
    return result


def _room_history(room_name, limit=200):
    db_id = room_db_id.get(room_name)
    if not db_id:
        return []
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT sender_id, content, msg_type, file_url, file_name, mime_type, file_size, created_at
               FROM chat_messages
               WHERE room_id = %s ORDER BY id ASC LIMIT %s''',
            (db_id, limit)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [{
        'sender_id': r['sender_id'], 'content': r['content'],
        'msg_type': r.get('msg_type') or 'text',
        'file_url': r.get('file_url'), 'file_name': r.get('file_name'),
        'mime_type': r.get('mime_type'), 'file_size': r.get('file_size'),
        'created_at': (r['created_at'].isoformat() + 'Z') if r.get('created_at') else None,
    } for r in rows]


def _close_room(room_name, left_by=None):
    """방 정리: DB 종료 처리 + 참여자 소켓 leave_room."""
    members = active_rooms.pop(room_name, None)
    db_id = room_db_id.pop(room_name, None)
    room_member_info.pop(room_name, None)
    if db_id:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE chat_rooms SET closed_at = NOW() WHERE id = %s', (db_id,))
            conn.commit()
        finally:
            conn.close()
    if members:
        for uid in members:
            info = online_users.get(uid)
            if not info:
                continue
            for sid in info['sids']:
                # namespace를 명시해야 함 — 백그라운드 타이머에서 호출될 때는
                # flask.request가 없어 leave_room()이 기본 namespace를 읽지 못한다.
                leave_room(room_name, sid=sid, namespace='/')
    return members


@socketio.on('connect')
def on_connect(auth):
    token = (auth or {}).get('token') or request.args.get('token')
    if not token:
        return False
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return False

    user_id  = payload['user_id']
    username = payload['username']
    sid = request.sid

    sid_user[sid] = user_id
    if user_id not in online_users:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT avatar_id FROM users WHERE id = %s', (user_id,))
            row = cursor.fetchone()
        finally:
            conn.close()
        online_users[user_id] = {'username': username, 'avatar_id': (row or {}).get('avatar_id', 0), 'sids': set()}
    online_users[user_id]['sids'].add(sid)
    join_room(f'user_{user_id}')
    _broadcast_online()

    # 새로고침/다른 페이지 이동 후에도 나가기 전까지는 채팅창이 그대로 복원되도록,
    # 현재 이 유저가 참여 중인 활성 채팅방과 지난 대화 내역을 접속 직후 알려준다.
    my_rooms = _active_rooms_for_user(user_id)
    if my_rooms:
        for r in my_rooms:
            # 새로고침으로 발급된 새 sid는 이전 sid와 달리 이 방에 join된 적이 없다.
            # 다시 join하지 않으면 상대방이 보낸 메시지가 이 sid까지 전달되지 않는다.
            join_room(r['room'], sid=sid)
            r['history'] = _room_history(r['room'])
        emit('restore_rooms', {'rooms': my_rooms})


def _finalize_offline_deferred(user_id, username):
    """threading.Timer 콜백 — leave_room()이 필요로 하는 Flask app_context를 열어준다."""
    if _flask_app is not None:
        with _flask_app.app_context():
            _finalize_offline(user_id, username)
    else:
        _finalize_offline(user_id, username)


def _finalize_offline(user_id, username):
    """연결 끊김 유예 시간이 지나도 재접속하지 않았으면 실제로 나간 것으로 처리."""
    if user_id in online_users:
        return  # 유예 시간 안에 재접속함 — 아무것도 하지 않는다

    for req_id, req in list(pending_requests.items()):
        if user_id not in (req['from'], req['to']):
            continue
        pending_requests.pop(req_id, None)
        pending_pairs.pop(req['pair'], None)
        other_id = req['to'] if req['from'] == user_id else req['from']
        if other_id in online_users:
            socketio.emit('chat_error',
                           {'message': '상대방의 연결이 끊어져 채팅 신청이 취소됐어요.'},
                           room=f'user_{other_id}')

    for room_name in list(active_rooms.keys()):
        members = active_rooms.get(room_name, set())
        if user_id not in members:
            continue
        socketio.emit('chat_partner_left',
                       {'room': room_name, 'by_user_id': user_id, 'by_username': username},
                       room=room_name)
        _close_room(room_name)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    user_id = sid_user.pop(sid, None)
    if user_id is None:
        return

    info = online_users.get(user_id)
    if info:
        info['sids'].discard(sid)
        if not info['sids']:
            del online_users[user_id]
    _broadcast_online()
    username = info['username'] if info else ''

    # 다른 탭으로 여전히 접속 중이면 아무것도 정리하지 않는다
    if user_id in online_users:
        return

    # 완전히 끊긴 경우 — 즉시 정리하지 않고 유예 시간을 두어, 짧은 네트워크 순단/재연결을
    # "채팅방 나감"으로 오판하지 않게 한다. 유예 시간 후에도 오프라인이면 그때 정리한다.
    timer = threading.Timer(DISCONNECT_GRACE_SEC, _finalize_offline_deferred, args=(user_id, username))
    timer.daemon = True
    timer.start()


@socketio.on('chat_request')
def on_chat_request(data):
    from_id = sid_user.get(request.sid)
    if from_id is None:
        return
    to_id = (data or {}).get('to_user_id')
    if to_id == from_id or to_id not in online_users:
        emit('chat_error', {'message': '상대방이 접속 중이 아닙니다.'})
        return

    pair_key = frozenset((from_id, to_id))
    if pair_key in pending_pairs:
        emit('chat_error', {'message': '이미 처리 대기 중인 채팅 신청이 있어요. 상대방의 응답을 기다려주세요.'})
        return

    unblock_at = reject_cooldowns.get((from_id, to_id))
    if unblock_at and time.time() < unblock_at:
        remain = int(unblock_at - time.time())
        emit('chat_error', {'message': f'거절한 상대에게는 {remain // 60}분 {remain % 60}초 후에 다시 신청할 수 있어요.'})
        return

    req_id = next(_req_ids)
    pending_requests[req_id] = {'from': from_id, 'to': to_id, 'pair': pair_key}
    pending_pairs[pair_key] = req_id
    from_username = online_users[from_id]['username']

    socketio.emit('chat_request',
                   {'request_id': req_id, 'from_user_id': from_id, 'from_username': from_username},
                   room=f'user_{to_id}')
    emit('chat_request_sent', {'request_id': req_id, 'to_user_id': to_id})


@socketio.on('chat_response')
def on_chat_response(data):
    data = data or {}
    req_id = data.get('request_id')
    accept = bool(data.get('accept'))
    req = pending_requests.pop(req_id, None)
    if not req:
        return
    pending_pairs.pop(req['pair'], None)

    responder_id = sid_user.get(request.sid)
    if responder_id != req['to']:
        return  # 신청 대상 본인만 응답 가능

    from_id, to_id = req['from'], req['to']
    if not accept:
        reject_cooldowns[(from_id, to_id)] = time.time() + REJECT_COOLDOWN_SEC
        socketio.emit('chat_rejected', {'by_user_id': to_id}, room=f'user_{from_id}')
        return
    if from_id not in online_users or to_id not in online_users:
        socketio.emit('chat_error', {'message': '상대방이 접속을 종료했습니다.'}, room=f'user_{from_id}')
        return

    room_name = _room_name(from_id, to_id, req_id)
    active_rooms[room_name] = {from_id, to_id}
    room_member_info[room_name] = {
        from_id: {'username': online_users[from_id]['username'], 'avatar_id': online_users[from_id]['avatar_id']},
        to_id:   {'username': online_users[to_id]['username'],   'avatar_id': online_users[to_id]['avatar_id']},
    }

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO chat_rooms (user1_id, user2_id) VALUES (%s, %s)',
            (from_id, to_id)
        )
        conn.commit()
        room_db_id[room_name] = cursor.lastrowid
    finally:
        conn.close()

    for uid in (from_id, to_id):
        for sid in online_users[uid]['sids']:
            join_room(room_name, sid=sid)

    socketio.emit('chat_accepted',
                   {'room': room_name, 'partner_id': to_id, 'partner_username': online_users[to_id]['username'],
                    'partner_avatar_id': online_users[to_id]['avatar_id']},
                   room=f'user_{from_id}')
    socketio.emit('chat_accepted',
                   {'room': room_name, 'partner_id': from_id, 'partner_username': online_users[from_id]['username'],
                    'partner_avatar_id': online_users[from_id]['avatar_id']},
                   room=f'user_{to_id}')


@socketio.on('chat_message')
def on_chat_message(data):
    data = data or {}
    sender_id = sid_user.get(request.sid)
    room_name = data.get('room')
    text = (data.get('message') or '').strip()
    if not sender_id or not room_name or not text:
        return
    if sender_id not in active_rooms.get(room_name, set()):
        return
    if len(text) > 1000:
        text = text[:1000]

    if _contains_banned_word(text):
        emit('chat_blocked', {
            'room': room_name,
            'message': '비속어는 사용할 수 없습니다. 깨끗한 채팅 문화를 만들어주세요.'
        })
        return

    db_id = room_db_id.get(room_name)
    if db_id:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO chat_messages (room_id, sender_id, content) VALUES (%s, %s, %s)',
                (db_id, sender_id, text)
            )
            conn.commit()
        finally:
            conn.close()

    socketio.emit('chat_message',
                   {'room': room_name, 'sender_id': sender_id,
                    'username': online_users[sender_id]['username'], 'content': text, 'msg_type': 'text',
                    'created_at': datetime.datetime.utcnow().isoformat() + 'Z'},
                   room=room_name)


@socketio.on('chat_file')
def on_chat_file(data):
    data = data or {}
    sender_id = sid_user.get(request.sid)
    room_name = data.get('room')
    file_url = (data.get('file_url') or '').strip()
    file_name = (data.get('file_name') or '').strip()[:255]
    mime_type = (data.get('mime_type') or '').strip()[:100]
    try:
        file_size = int(data.get('file_size') or 0)
    except (ValueError, TypeError):
        file_size = 0
    if not sender_id or not room_name or not file_url or not file_name:
        return
    if sender_id not in active_rooms.get(room_name, set()):
        return
    if not file_url.startswith('/api/files/'):
        emit('chat_error', {'message': '올바르지 않은 파일입니다.'})
        return

    content = f'📎 {file_name}'
    db_id = room_db_id.get(room_name)
    if db_id:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''INSERT INTO chat_messages (room_id, sender_id, content, msg_type, file_url, file_name, mime_type, file_size)
                   VALUES (%s, %s, %s, 'file', %s, %s, %s, %s)''',
                (db_id, sender_id, content, file_url, file_name, mime_type, file_size or None)
            )
            conn.commit()
        finally:
            conn.close()

    socketio.emit('chat_message',
                   {'room': room_name, 'sender_id': sender_id,
                    'username': online_users[sender_id]['username'], 'content': content,
                    'msg_type': 'file', 'file_url': file_url, 'file_name': file_name,
                    'mime_type': mime_type, 'file_size': file_size,
                    'created_at': datetime.datetime.utcnow().isoformat() + 'Z'},
                   room=room_name)


@socketio.on('update_avatar')
def on_update_avatar(data):
    user_id = sid_user.get(request.sid)
    if user_id is None:
        return
    avatar_id = (data or {}).get('avatar_id')
    if not isinstance(avatar_id, int) or not (0 <= avatar_id < AVATAR_COUNT):
        emit('chat_error', {'message': '올바르지 않은 아바타예요.'})
        return

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET avatar_id = %s WHERE id = %s', (avatar_id, user_id))
        conn.commit()
    finally:
        conn.close()

    info = online_users.get(user_id)
    if info:
        info['avatar_id'] = avatar_id
    _broadcast_online()


@socketio.on('chat_leave')
def on_chat_leave(data):
    user_id = sid_user.get(request.sid)
    room_name = (data or {}).get('room')
    members = active_rooms.get(room_name)
    if not members or user_id not in members:
        return
    username = online_users.get(user_id, {}).get('username', '')
    socketio.emit('chat_partner_left',
                   {'room': room_name, 'by_user_id': user_id, 'by_username': username},
                   room=room_name)
    _close_room(room_name)
