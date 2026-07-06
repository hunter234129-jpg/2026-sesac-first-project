from flask import request
from flask_socketio import join_room, leave_room, emit
from extensions import socketio
from utils.auth import decode_token

# connect/disconnect 이벤트는 sockets.chat_events도 등록하는데, Flask-SocketIO는
# 같은 (namespace, event)에 핸들러를 하나만 유지해 나중에 import되는 쪽이 덮어쓴다.
# 그래서 접속 시점에 캐시하는 대신, 필요할 때(drawing_presence) 그때그때 토큰을 읽는다.
def _username_from_request():
    token = request.args.get('token')
    if not token:
        return None
    try:
        return decode_token(token)['username']
    except Exception:
        return None


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


@socketio.on('request_sync')
def on_request_sync(payload):
    """새로 접속한 클라이언트가 "이미 누가 편집 중인 상태"를 요청 — 같은 방의 다른
    클라이언트에게 중계해서, 그 중 하나가 full_sync로 현재 Y.Doc 상태를 보내주게 한다.
    이 중계가 없으면 새 접속자는 응답을 영영 못 받아서 매번 DB의 초기 내용을
    새 문서에 다시 끼워 넣게 되고, 결국 그림/차트 등 블록이 접속할 때마다 중복된다."""
    slug = (payload or {}).get('slug')
    if slug:
        emit('request_sync', {}, room=f'wiki:{slug}', include_self=False)


@socketio.on('full_sync')
def on_full_sync(payload):
    """request_sync에 대한 응답(현재 Y.Doc 전체 상태)을 요청자 쪽으로 중계.
    Yjs 상태 병합은 멱등적이라 같은 방의 여러 명이 동시에 응답해도 안전하다."""
    slug  = (payload or {}).get('slug')
    state = (payload or {}).get('state')
    if slug:
        emit('full_sync', {'state': state}, room=f'wiki:{slug}', include_self=False)


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
    emit('drawing_presence', {
        'block_id': block_id,
        'editing':  bool((payload or {}).get('editing')),
        'username': _username_from_request() or '익명',
        'sid':      request.sid,
    }, room=f'wiki:{slug}', include_self=False)
