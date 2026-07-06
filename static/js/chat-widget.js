/* ─────────────────────────────────────────────
   실시간 1:1 채팅 위젯 — 접속 현황 · 채팅 신청/수락 · 플로팅 채팅창
   api.js의 renderNav()가 로그인 상태일 때 동적으로 로드하고
   window.startChatWidget()을 호출해서 초기화한다 (모든 페이지 공통).
   ───────────────────────────────────────────── */

const BLOCKED_EXTS = new Set(['.exe', '.bat', '.scr', '.dll', '.msi']);

function showChatDialog(icon, title, body) {
  document.getElementById('__chatFileDlg')?.remove();
  const overlay = document.createElement('div');
  overlay.id = '__chatFileDlg';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;';
  overlay.innerHTML = `
    <div style="background:#1b2340;border-radius:16px;padding:32px 36px;max-width:340px;width:90%;
                box-shadow:0 8px 40px rgba(0,0,0,.7);text-align:center;">
      <div style="font-size:40px;margin-bottom:14px;">${icon}</div>
      <div style="font-size:17px;font-weight:700;color:#fff;margin-bottom:10px;">${title}</div>
      <div style="font-size:13px;color:#94a3b8;line-height:1.6;margin-bottom:22px;">${body}</div>
      <button style="padding:9px 28px;background:#4f46e5;color:#fff;border:none;border-radius:8px;
                     font-size:14px;font-weight:600;cursor:pointer;" id="__chatFileDlgClose">확인</button>
    </div>`;
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  document.getElementById('__chatFileDlgClose').onclick = close;
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
}

function showBlockedExtDialog(ext) {
  showChatDialog('🚫', '파일 전송 불가',
    `<span style="color:#f87171;font-weight:600;">${escapeHtml(ext)}</span> 확장자 파일은<br>보안상 전송할 수 없어요.<br><span style="font-size:12px;opacity:.7;">(.exe · .bat · .scr · .dll · .msi)</span>`);
}

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

function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

const KO_DOW = ['일', '월', '화', '수', '목', '금', '토'];
function formatDateLabel(d) {
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${KO_DOW[d.getDay()]}요일`;
}
function toDateKey(d) { return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; }
function formatTime(d) {
  const h = d.getHours(), m = d.getMinutes();
  return `${h < 12 ? '오전' : '오후'} ${h % 12 || 12}:${String(m).padStart(2, '0')}`;
}

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
  let myAvatarId = null;
  const btnByUid = {};           // uid -> [신청 버튼 엘리먼트, ...] (드롭다운 + 전체보기 페이지에 각각 존재 가능)
  const pendingOutgoing = new Set();   // 응답 대기 중인 채팅 신청 대상 uid (online_users 재렌더에도 유지)
  const partnerAvatarCache = new Map(); // user_id -> avatar_id (파트너 아바타 변경 감지용)

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
    if (me && me.avatar_id !== myAvatarId) {
      myAvatarId = me.avatar_id;
      window.dispatchEvent(new CustomEvent('avatar-changed', { detail: { avatar_id: myAvatarId } }));
    } else if (me) {
      myAvatarId = me.avatar_id;
    }
    renderMyAvatarBox();
    document.querySelectorAll('.cf-my-avatar-btn').forEach(btn => { btn.innerHTML = avatarHtml(myAvatarId, 22); });
    document.querySelectorAll('.cf-my-avatar-head').forEach(el => { el.innerHTML = avatarHtml(myAvatarId, 26); });

    const others = users.filter(u => u.user_id !== myId);

    // 파트너 아바타 변경 감지 → 열린 채팅창 실시간 업데이트
    others.forEach(u => {
      const cached = partnerAvatarCache.get(u.user_id);
      if (cached !== undefined && cached !== u.avatar_id) {
        document.querySelectorAll(`.chat-float[data-partner-id="${u.user_id}"]`).forEach(w => {
          if (w._updatePartnerAvatar) w._updatePartnerAvatar(u.avatar_id);
        });
      }
      partnerAvatarCache.set(u.user_id, u.avatar_id);
    });

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
  function openChatWindow(room, partnerName, partnerAvatarId, partnerId, history) {
    if (document.querySelector(`.chat-float[data-room="${room}"]`)) return;

    let pAvId = partnerAvatarId;  // 가변 참조 — 파트너 아바타 변경 시 _updatePartnerAvatar로 갱신

    const win = document.createElement('div');
    win.className = 'chat-float';
    win.dataset.room = room;
    if (partnerId) win.dataset.partnerId = String(partnerId);
    win._updatePartnerAvatar = (newId) => {
      pAvId = newId;
      win.querySelectorAll('.cf-partner-avatar').forEach(span => {
        span.innerHTML = avatarHtml(newId, 28);
      });
    };
    win.innerHTML = `
      <div class="cf-head">
        <span class="cf-partner" title="내 아바타 변경"><span class="cf-my-avatar-head">${avatarHtml(myAvatarId, 26)}</span><span>${escapeHtml(partnerName)}님과의 채팅</span></span>
        <span class="cf-head-actions">
          <button class="cf-leave" type="button">나가기</button>
        </span>
      </div>
      <div class="cf-log"></div>
      <form class="cf-form">
        <button type="button" class="cf-emoji-btn" title="이모지">😀</button>
        <button type="button" class="cf-file-btn" title="파일 첨부">＋</button>
        <input type="file" class="cf-file-input" hidden>
        <textarea class="cf-text-input" placeholder="메시지를 입력하세요" maxlength="1000" autocomplete="off" rows="1"></textarea>
        <button type="submit" class="cf-send-btn">전송</button>
      </form>`;
    floatWrap.appendChild(win);

    const log          = win.querySelector('.cf-log');
    const form         = win.querySelector('.cf-form');
    const input        = win.querySelector('.cf-text-input');
    const leaveBtn     = win.querySelector('.cf-leave');
    const emojiBtn     = win.querySelector('.cf-emoji-btn');
    const partnerEl    = win.querySelector('.cf-partner');
    const fileBtn      = win.querySelector('.cf-file-btn');
    const fileInput    = win.querySelector('.cf-file-input');

    const picker = buildEmojiPicker((emoji) => {
      const start = input.selectionStart ?? input.value.length;
      const end   = input.selectionEnd ?? input.value.length;
      input.value = input.value.slice(0, start) + emoji + input.value.slice(end);
      input.focus();
      input.selectionStart = input.selectionEnd = start + emoji.length;
    });
    win.appendChild(picker);
    emojiBtn.onclick = (e) => { e.stopPropagation(); picker.classList.toggle('hidden'); };

    const myAvatarPicker = buildAvatarPicker();
    myAvatarPicker.classList.add('cf-avatar-picker');
    win.appendChild(myAvatarPicker);
    myAvatarPicker.style.top = win.querySelector('.cf-head').offsetHeight + 'px';
    partnerEl.style.cursor = 'pointer';
    partnerEl.onclick = (e) => { e.stopPropagation(); myAvatarPicker.classList.toggle('hidden'); };

    fileBtn.onclick = () => fileInput.click();
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      fileInput.value = '';
      if (!file) return;
      const ext = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase() : '';
      if (BLOCKED_EXTS.has(ext)) { showBlockedExtDialog(ext || file.name); return; }
      if (file.size > 300 * 1024 * 1024) {
        showChatDialog('⚠️', '최대 용량 초과',
          '최대용량 <span style="color:#f87171;font-weight:600;">(300MB)</span>을 초과하였습니다.<br>더 작은 파일을 선택해 주세요.');
        return;
      }
      fileBtn.disabled = true;
      fileBtn.textContent = '⏳';
      try {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('ref_type', 'chat');
        const uploaded = await api('/api/upload', { method: 'POST', body: fd, isForm: true });
        socket.emit('chat_file', {
          room, file_url: uploaded.url, file_name: uploaded.original, mime_type: file.type, file_size: file.size
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
      if (!myAvatarPicker.contains(e.target) && !partnerEl.contains(e.target)) myAvatarPicker.classList.add('hidden');
    });

    let lastMsgDateKey = null;
    function addDateSep(label) {
      const div = document.createElement('div');
      div.className = 'cf-date-sep';
      div.innerHTML = `<span>📅 ${label}</span>`;
      log.appendChild(div);
    }
    function maybeAddDateSep(isoStr) {
      const d = isoStr ? new Date(isoStr) : new Date();
      const key = toDateKey(d);
      if (key !== lastMsgDateKey) {
        addDateSep(formatDateLabel(d));
        lastMsgDateKey = key;
      }
    }

    function _msgRow(cls, isoStr) {
      const d = isoStr ? new Date(isoStr) : new Date();
      const row = document.createElement('div');
      row.className = `cf-msg-row ${cls}`;
      if (cls === 'other') {
        const avatarEl = document.createElement('span');
        avatarEl.className = 'cf-partner-avatar';
        avatarEl.innerHTML = avatarHtml(pAvId, 28);
        row.appendChild(avatarEl);
      }
      const timeEl = document.createElement('span');
      timeEl.className = 'cf-msg-time';
      timeEl.textContent = formatTime(d);
      return { row, timeEl };
    }

    function addMsg(cls, text, isoStr) {
      maybeAddDateSep(isoStr || null);
      if (cls === 'me' || cls === 'other') {
        const { row, timeEl } = _msgRow(cls, isoStr);
        const bubble = document.createElement('div');
        bubble.className = `cf-msg ${cls}`;
        bubble.innerHTML = linkify(escapeHtml(text));
        row.appendChild(bubble);
        row.appendChild(timeEl);
        log.appendChild(row);
      } else {
        const div = document.createElement('div');
        div.className = `cf-msg ${cls}`;
        div.innerHTML = linkify(escapeHtml(text));
        log.appendChild(div);
      }
      log.scrollTop = log.scrollHeight;
    }

    function addFileMsg(cls, fileUrl, fileName, mimeType, fileSize, isoStr) {
      maybeAddDateSep(isoStr || null);
      const bubble = document.createElement('div');
      bubble.className = `cf-msg ${cls} file`;
      const isImage = (mimeType || '').startsWith('image/');
      const safeName = escapeHtml(fileName || '파일');
      if (isImage) {
        bubble.innerHTML = `<a href="${fileUrl}" target="_blank" rel="noopener noreferrer"><img class="cf-file-img" src="${fileUrl}" alt="${safeName}"></a>`;
      } else {
        const sizeHtml = fileSize ? `<span class="cf-file-size">용량: ${formatFileSize(fileSize)}</span>` : '';
        bubble.innerHTML = `<a href="${fileUrl}" target="_blank" rel="noopener noreferrer" class="cf-file-link"><span class="cf-file-dl-icon">↓</span><span class="cf-file-info"><span class="cf-file-name-text">${safeName}</span>${sizeHtml}</span></a>`;
      }
      if (cls === 'me' || cls === 'other') {
        const { row, timeEl } = _msgRow(cls, isoStr);
        row.appendChild(bubble);
        row.appendChild(timeEl);
        log.appendChild(row);
      } else {
        log.appendChild(bubble);
      }
      log.scrollTop = log.scrollHeight;
    }

    function addFromPayload(cls, m) {
      const isoStr = m.created_at || null;
      if (m.msg_type === 'file') addFileMsg(cls, m.file_url, m.file_name, m.mime_type, m.file_size, isoStr);
      else addMsg(cls, m.content, isoStr);
    }

    if (history && history.length) {
      history.forEach(m => addFromPayload(m.sender_id === myId ? 'me' : 'other', m));
    } else {
      addMsg('sys', `${partnerName}님과 채팅을 시작했어요.`);
    }

    function autoResize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 80) + 'px';
    }
    input.addEventListener('input', autoResize);

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });

    form.onsubmit = (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      socket.emit('chat_message', { room, message: text });
      input.value = '';
      input.style.height = 'auto';
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
        openChatWindow(r.room, r.partner_username, r.partner_avatar_id, r.partner_id, r.history);
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
      openChatWindow(d.room, d.partner_username, d.partner_avatar_id, d.partner_id);
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
