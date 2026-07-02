/* ─────────────────────────────────────────────
   실시간 1:1 채팅 위젯 — 접속 현황 · 채팅 신청/수락 · 플로팅 채팅창
   api.js의 renderNav()가 로그인 상태일 때 동적으로 로드하고
   window.startChatWidget()을 호출해서 초기화한다 (모든 페이지 공통).
   ───────────────────────────────────────────── */

const EMOJIS = [
  '😀','😁','😂','🤣','😊','😍','😘','😎','🤔','🙄','😴','😢','😭','😡','🥳','😱',
  '👍','👎','👏','🙏','💪','🤝','👋','✌️',
  '❤️','🔥','⭐','🎉','✅','❌','💯','⏰',
  '📚','📝','☕','🍀','🎯','💡','🚀','😅'
];

/* 만화 캐릭터풍 아바타 — index가 그대로 서버 저장값(avatar_id). 순서 변경 금지. */
const AVATARS = [
  { emoji: '🦊', bg: '#FF6B6B' }, { emoji: '🐱', bg: '#FFA94D' }, { emoji: '🐶', bg: '#FFD43B' },
  { emoji: '🐼', bg: '#94D82D' }, { emoji: '🐨', bg: '#37B24D' }, { emoji: '🦁', bg: '#20C997' },
  { emoji: '🐯', bg: '#22B8CF' }, { emoji: '🐵', bg: '#4DABF7' }, { emoji: '🐰', bg: '#5C7CFA' },
  { emoji: '🐺', bg: '#845EF7' }, { emoji: '🐸', bg: '#CC5DE8' }, { emoji: '🐧', bg: '#F783AC' },
  { emoji: '🦉', bg: '#FF8787' }, { emoji: '🐙', bg: '#FFC078' }, { emoji: '🦋', bg: '#FFE066' },
  { emoji: '🐹', bg: '#B2F2BB' }, { emoji: '🐭', bg: '#99E9F2' }, { emoji: '🐔', bg: '#91A7FF' },
  { emoji: '🐮', bg: '#D0BFFF' }, { emoji: '🐷', bg: '#FCC2D7' }
];

function avatarHtml(avatarId, size) {
  const a = AVATARS[avatarId] || AVATARS[0];
  return `<span class="avatar-chip" style="background:${a.bg}; width:${size}px; height:${size}px; font-size:${Math.round(size * 0.58)}px;">${a.emoji}</span>`;
}

/* 이스케이프된 텍스트에서 URL을 찾아 클릭 가능한 링크로 바꾼다 (반드시 escapeHtml 이후에 호출) */
const URL_RE = /(https?:\/\/[^\s<]+[^\s<.,:;!?'")\]])/g;
function linkify(escapedText) {
  return escapedText.replace(URL_RE, (url) =>
    `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
}

window.startChatWidget = function () {
  if (window.__chatWidgetStarted) return;
  window.__chatWidgetStarted = true;
  if (!window.io || !Auth.isLoggedIn) return;

  const myId = Auth.userId;
  let socket = null;
  let myAvatarId = 0;
  const btnByUid = {};           // uid -> [신청 버튼 엘리먼트, ...] (드롭다운 + 전체보기 페이지에 각각 존재 가능)
  const pendingOutgoing = new Set();   // 응답 대기 중인 채팅 신청 대상 uid (online_users 재렌더에도 유지)

  /* ── 플로팅 채팅창 컨테이너 ── */
  const floatWrap = document.createElement('div');
  floatWrap.id = 'chatFloatWrap';
  document.body.appendChild(floatWrap);

  /* ── 수신 채팅 신청 토스트 컨테이너 ── */
  const toastWrap = document.createElement('div');
  toastWrap.id = 'chatToastWrap';
  document.body.appendChild(toastWrap);

  function showToast(html, timeout) {
    const el = document.createElement('div');
    el.className = 'chat-toast';
    el.innerHTML = html;
    toastWrap.appendChild(el);
    if (timeout) setTimeout(() => el.remove(), timeout);
    return el;
  }

  /* ── 접속 중인 멤버 목록 렌더 (네브바 드롭다운 + /members 전체보기 페이지 공용) ── */
  function buildRow(u) {
    const row = document.createElement('div');
    row.className = 'online-row';
    row.dataset.uid = u.user_id;
    const isPending = pendingOutgoing.has(u.user_id);
    row.innerHTML = `
      <span class="avatar-wrap">${avatarHtml(u.avatar_id, 32)}<span class="online-dot"></span></span>
      <span class="online-name">${escapeHtml(u.username)}</span>
      <button class="btn btn-ghost online-chat-btn" type="button" ${isPending ? 'disabled' : ''}>${isPending ? '신청 보냄 (대기 중)' : '💬 채팅 신청'}</button>`;
    const btn = row.querySelector('.online-chat-btn');
    (btnByUid[u.user_id] = btnByUid[u.user_id] || []).push(btn);
    btn.onclick = () => {
      setBtnState(u.user_id, true, '신청 중...');
      socket.emit('chat_request', { to_user_id: u.user_id });
    };
    return row;
  }

  function setBtnState(uid, disabled, label) {
    (btnByUid[uid] || []).forEach(btn => {
      btn.disabled = disabled;
      btn.textContent = label;
    });
  }

  function resetAllPending() {
    pendingOutgoing.clear();
    Object.keys(btnByUid).forEach(uid => setBtnState(Number(uid), false, '💬 채팅 신청'));
  }

  function renderOnlineList(users) {
    const me = users.find(u => u.user_id === myId);
    if (me) myAvatarId = me.avatar_id;
    renderMyAvatarBox();
    document.querySelectorAll('.cf-my-avatar-btn').forEach(btn => { btn.innerHTML = avatarHtml(myAvatarId, 22); });

    const others = users.filter(u => u.user_id !== myId);
    for (const uid in btnByUid) delete btnByUid[uid];

    const dropdownList = document.getElementById('onlineDropdownList');
    if (dropdownList) {
      dropdownList.innerHTML = '';
      if (!others.length) {
        dropdownList.innerHTML = '<p class="muted" style="font-size:13px;">지금 접속 중인 멤버가 없어요.</p>';
      } else {
        others.slice(0, 8).forEach(u => dropdownList.appendChild(buildRow(u)));
      }
    }

    const fullList = document.getElementById('onlineMembersFull');
    if (fullList) {
      fullList.innerHTML = '';
      if (!others.length) {
        fullList.innerHTML = '<p class="muted" style="font-size:14px;">지금 접속 중인 다른 멤버가 없어요.</p>';
      } else {
        others.forEach(u => fullList.appendChild(buildRow(u)));
      }
    }

    const badge = document.getElementById('onlineCount');
    if (badge) {
      badge.textContent = others.length > 99 ? '99+' : others.length;
      badge.classList.toggle('hidden', others.length === 0);
    }
  }

  /* ── 이모지 피커 (채팅 메시지에 삽입) ── */
  function buildEmojiPicker(onPick) {
    const picker = document.createElement('div');
    picker.className = 'emoji-picker hidden';
    picker.innerHTML = EMOJIS.map(e => `<button type="button" class="emoji-item">${e}</button>`).join('');
    picker.querySelectorAll('.emoji-item').forEach(b => {
      b.onclick = () => onPick(b.textContent);
    });
    return picker;
  }

  /* ── 아바타 피커 (내 프로필 아바타 선택) ── */
  function buildAvatarPicker() {
    const picker = document.createElement('div');
    picker.className = 'avatar-picker hidden';
    picker.innerHTML = AVATARS.map((a, i) =>
      `<button type="button" class="avatar-pick-item" data-i="${i}" style="background:${a.bg};" title="이 아바타로 변경">${a.emoji}</button>`
    ).join('');
    picker.querySelectorAll('.avatar-pick-item').forEach(b => {
      b.onclick = () => {
        socket.emit('update_avatar', { avatar_id: Number(b.dataset.i) });
        picker.classList.add('hidden');
      };
    });
    return picker;
  }

  /* ── /members 페이지의 "내 아바타" 박스 ── */
  function renderMyAvatarBox() {
    const box = document.getElementById('myAvatarBox');
    if (!box) return;
    if (!box.dataset.built) {
      box.dataset.built = '1';
      box.innerHTML = `
        <div class="my-avatar-row">
          <span class="my-avatar-current">${avatarHtml(myAvatarId, 56)}</span>
          <div class="my-avatar-text">
            <div class="my-avatar-title">내 아바타</div>
            <div class="muted" style="font-size:13px;">마음에 드는 캐릭터로 바꿔보세요.</div>
          </div>
          <button class="btn btn-ghost my-avatar-btn" type="button">변경</button>
        </div>`;
      const picker = buildAvatarPicker();
      box.appendChild(picker);
      box.querySelector('.my-avatar-btn').onclick = (e) => { e.stopPropagation(); picker.classList.toggle('hidden'); };
      document.addEventListener('click', (e) => {
        if (!picker.contains(e.target) && !e.target.closest('.my-avatar-btn')) picker.classList.add('hidden');
      });
    } else {
      box.querySelector('.my-avatar-current').outerHTML = `<span class="my-avatar-current">${avatarHtml(myAvatarId, 56)}</span>`;
    }
  }

  /* ── 플로팅 채팅창 ──
     history가 주어지면(새로고침/페이지 이동 후 복원) 인사말 대신 지난 대화를 그대로 보여준다. */
  function openChatWindow(room, partnerName, partnerAvatarId, history) {
    if (document.querySelector(`.chat-float[data-room="${room}"]`)) return;

    const win = document.createElement('div');
    win.className = 'chat-float';
    win.dataset.room = room;
    win.innerHTML = `
      <div class="cf-head">
        <span class="cf-partner">${avatarHtml(partnerAvatarId, 26)}<span>${escapeHtml(partnerName)}님과의 채팅</span></span>
        <span class="cf-head-actions">
          <button class="cf-my-avatar-btn" type="button" title="내 아바타 변경">${avatarHtml(myAvatarId, 22)}</button>
          <button class="cf-leave" type="button">나가기</button>
        </span>
      </div>
      <div class="cf-log"></div>
      <form class="cf-form">
        <button type="button" class="cf-emoji-btn" title="이모지">😀</button>
        <button type="button" class="cf-file-btn" title="파일 첨부">＋</button>
        <input type="file" class="cf-file-input" hidden>
        <input type="text" class="cf-text-input" placeholder="메시지를 입력하세요" maxlength="1000" autocomplete="off">
        <button type="submit" class="btn btn-primary">전송</button>
      </form>`;
    floatWrap.appendChild(win);

    const log          = win.querySelector('.cf-log');
    const form         = win.querySelector('.cf-form');
    const input        = win.querySelector('.cf-text-input');
    const leaveBtn     = win.querySelector('.cf-leave');
    const emojiBtn     = win.querySelector('.cf-emoji-btn');
    const myAvatarBtn  = win.querySelector('.cf-my-avatar-btn');
    const fileBtn      = win.querySelector('.cf-file-btn');
    const fileInput    = win.querySelector('.cf-file-input');

    const picker = buildEmojiPicker((emoji) => {
      const start = input.selectionStart ?? input.value.length;
      const end   = input.selectionEnd ?? input.value.length;
      input.value = input.value.slice(0, start) + emoji + input.value.slice(end);
      input.focus();
      input.selectionStart = input.selectionEnd = start + emoji.length;
    });
    form.appendChild(picker);
    emojiBtn.onclick = (e) => { e.stopPropagation(); picker.classList.toggle('hidden'); };

    const myAvatarPicker = buildAvatarPicker();
    win.querySelector('.cf-head').appendChild(myAvatarPicker);
    myAvatarBtn.onclick = (e) => { e.stopPropagation(); myAvatarPicker.classList.toggle('hidden'); };

    fileBtn.onclick = () => fileInput.click();
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      fileInput.value = '';
      if (!file) return;
      fileBtn.disabled = true;
      fileBtn.textContent = '⏳';
      try {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('ref_type', 'chat');
        const uploaded = await api('/api/upload', { method: 'POST', body: fd, isForm: true });
        socket.emit('chat_file', {
          room, file_url: uploaded.url, file_name: uploaded.original, mime_type: file.type
        });
      } catch (err) {
        addMsg('blocked', err.message || '파일 업로드에 실패했어요.');
      } finally {
        fileBtn.disabled = false;
        fileBtn.textContent = '＋';
      }
    };

    document.addEventListener('click', (e) => {
      if (!picker.contains(e.target) && e.target !== emojiBtn) picker.classList.add('hidden');
      if (!myAvatarPicker.contains(e.target) && e.target !== myAvatarBtn) myAvatarPicker.classList.add('hidden');
    });

    function addMsg(cls, text) {
      const div = document.createElement('div');
      div.className = `cf-msg ${cls}`;
      div.innerHTML = linkify(escapeHtml(text));
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }

    function addFileMsg(cls, fileUrl, fileName, mimeType) {
      const div = document.createElement('div');
      div.className = `cf-msg ${cls} cf-file`;
      const isImage = (mimeType || '').startsWith('image/');
      div.innerHTML = isImage
        ? `<a href="${fileUrl}" target="_blank" rel="noopener noreferrer"><img class="cf-file-img" src="${fileUrl}" alt="${escapeHtml(fileName)}"></a>`
        : `<a href="${fileUrl}" target="_blank" rel="noopener noreferrer" class="cf-file-link">📎 ${escapeHtml(fileName)}</a>`;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }

    function addFromPayload(cls, m) {
      if (m.msg_type === 'file') addFileMsg(cls, m.file_url, m.file_name, m.mime_type);
      else addMsg(cls, m.content);
    }

    if (history && history.length) {
      history.forEach(m => addFromPayload(m.sender_id === myId ? 'me' : 'other', m));
    } else {
      addMsg('sys', `${partnerName}님과 채팅을 시작했어요.`);
    }

    form.onsubmit = (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      socket.emit('chat_message', { room, message: text });
      input.value = '';
      picker.classList.add('hidden');
    };

    function endChat(systemText) {
      form.querySelector('button[type="submit"]').disabled = true;
      input.disabled = true;
      emojiBtn.disabled = true;
      fileBtn.disabled = true;
      if (systemText) addMsg('sys', systemText);
      leaveBtn.textContent = '닫기';
      leaveBtn.onclick = () => win.remove();
    }

    leaveBtn.onclick = () => {
      socket.emit('chat_leave', { room });
      win.remove();
    };

    win._addMsg = addMsg;
    win._addFromPayload = addFromPayload;
    win._endChat = endChat;
    input.focus();
  }

  function connectSocket() {
    socket = io({ auth: { token: Auth.token } });

    socket.on('online_users', (d) => renderOnlineList(d.users || []));

    socket.on('restore_rooms', (d) => {
      (d.rooms || []).forEach(r => {
        openChatWindow(r.room, r.partner_username, r.partner_avatar_id, r.history);
      });
    });

    socket.on('chat_request_sent', (d) => {
      pendingOutgoing.add(d.to_user_id);
      setBtnState(d.to_user_id, true, '신청 보냄 (대기 중)');
    });

    socket.on('chat_request', (d) => {
      const toast = showToast(`
        <div class="ct-text"><b>${escapeHtml(d.from_username)}</b>님이 채팅을 신청했어요.</div>
        <div class="ct-actions">
          <button class="btn btn-success ct-accept">수락</button>
          <button class="btn btn-ghost ct-reject">거절</button>
        </div>`);
      toast.querySelector('.ct-accept').onclick = () => {
        socket.emit('chat_response', { request_id: d.request_id, accept: true });
        toast.remove();
      };
      toast.querySelector('.ct-reject').onclick = () => {
        socket.emit('chat_response', { request_id: d.request_id, accept: false });
        toast.remove();
      };
    });

    socket.on('chat_rejected', (d) => {
      showToast('<div class="ct-text">상대방이 채팅 신청을 거절했어요.</div>', 3500);
      pendingOutgoing.delete(d.by_user_id);
      setBtnState(d.by_user_id, false, '💬 채팅 신청');
    });

    socket.on('chat_error', (d) => {
      showToast(`<div class="ct-text">${escapeHtml(d.message)}</div>`, 3500);
      resetAllPending();
    });

    socket.on('chat_accepted', (d) => {
      openChatWindow(d.room, d.partner_username, d.partner_avatar_id);
      pendingOutgoing.delete(d.partner_id);
      setBtnState(d.partner_id, false, '💬 채팅 신청');
    });

    socket.on('chat_message', (d) => {
      const win = document.querySelector(`.chat-float[data-room="${d.room}"]`);
      if (!win) return;
      win._addFromPayload(d.sender_id === myId ? 'me' : 'other', d);
    });

    socket.on('chat_blocked', (d) => {
      const win = document.querySelector(`.chat-float[data-room="${d.room}"]`);
      if (win) win._addMsg('blocked', d.message);
    });

    socket.on('chat_partner_left', (d) => {
      const win = document.querySelector(`.chat-float[data-room="${d.room}"]`);
      if (win) win._endChat(`${d.by_username || '상대방'}님이 채팅방을 나갔습니다.`);
    });
  }

  connectSocket();
};
