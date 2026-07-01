from flask import request
from flask_socketio import join_room, leave_room, emit
from extensions import socketio
from utils.auth import decode_token

_sid_users = {}   # sid -> {'user_id', 'username'} | None(비로그인 뷰어)


def _user_from_token(token):
    if not token:
        return None
    try:
        payload = decode_token(token)
        return {'user_id': payload['user_id'], 'username': payload['username']}
    except Exception:
        return None


@socketio.on('connect')
def on_connect():
    _sid_users[request.sid] = _user_from_token(request.args.get('token'))


@socketio.on('disconnect')
def on_disconnect():
    _sid_users.pop(request.sid, None)


@socketio.on('join_wiki')
def on_join_wiki(payload):
    slug = (payload or {}).get('slug')
    if slug:
        join_room(f'wiki:{slug}')


@socketio.on('leave_wiki')
def on_leave_wiki(payload):
    slug = (payload or {}).get('slug')
    if slug:
        leave_room(f'wiki:{slug}')


@socketio.on('doc_update')
def on_doc_update(payload):
    """Tiptap(Yjs) 문서 업데이트 릴레이. 서버는 내용을 해석하지 않고 같은 방의
    다른 클라이언트에게만 그대로 전달한다 — CRDT 병합은 각 클라이언트의 Y.Doc이 수행."""
    slug   = (payload or {}).get('slug')
    update = (payload or {}).get('update')
    if slug and update:
        emit('doc_update', {'update': update}, room=f'wiki:{slug}', include_self=False)


@socketio.on('awareness_update')
def on_awareness_update(payload):
    """커서 위치·색상 등 프레즌스 정보 릴레이"""
    slug  = (payload or {}).get('slug')
    state = (payload or {}).get('state')
    if slug:
        emit('awareness_update', {'state': state, 'sid': request.sid},
             room=f'wiki:{slug}', include_self=False)


@socketio.on('drawing_presence')
def on_drawing_presence(payload):
    """그림 블록을 지금 누가 편집 중인지 알려주는 어드바이저리 락(강제성 없음)"""
    slug     = (payload or {}).get('slug')
    block_id = (payload or {}).get('block_id')
    if not slug or not block_id:
        return
    user = _sid_users.get(request.sid)
    emit('drawing_presence', {
        'block_id': block_id,
        'editing':  bool((payload or {}).get('editing')),
        'username': user['username'] if user else '익명',
        'sid':      request.sid,
    }, room=f'wiki:{slug}', include_self=False)
