/* ─────────────────────────────────────────────
   공통 API 헬퍼 — fetch 래퍼 + 토큰 관리
   ───────────────────────────────────────────── */

const TOKEN_KEY = 'sb_token';
const NAME_KEY  = 'sb_username';

const Auth = {
  get token()    { return localStorage.getItem(TOKEN_KEY); },
  get username() { return localStorage.getItem(NAME_KEY); },
  get isLoggedIn() { return !!this.token; },
  /** JWT payload 디코딩 (서명 검증 X, 화면 표시/권한 UI 용도) */
  get payload() {
    const t = this.token;
    if (!t) return {};
    try {
      const p = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(decodeURIComponent(escape(atob(p))));
    } catch (_) { return {}; }
  },
  get userId()  { return this.payload.user_id ?? null; },
  get isAdmin() { return !!this.payload.is_admin; },
  save(token, username) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(NAME_KEY, username);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(NAME_KEY);
  },
  /** 로그인 안 됐으면 로그인 페이지로 리다이렉트 */
  require() {
    if (!this.isLoggedIn) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname);
      return false;
    }
    return true;
  },
  logout() {
    this.clear();
    location.href = '/';
  }
};

/**
 * API 호출. 성공 시 응답 JSON의 data를 반환, 실패 시 Error throw.
 * @param {string} path  예: '/api/auth/login'
 * @param {object} opts  { method, body, auth(기본 true), raw }
 */
async function api(path, opts = {}) {
  const { method = 'GET', body, auth = true, isForm = false } = opts;
  const headers = {};
  if (!isForm) headers['Content-Type'] = 'application/json';
  if (auth && Auth.token) headers['Authorization'] = 'Bearer ' + Auth.token;

  const res = await fetch(path, {
    method,
    headers,
    body: body == null ? undefined : (isForm ? body : JSON.stringify(body)),
  });

  let json = {};
  try { json = await res.json(); } catch (_) {}

  if (!res.ok) {
    // 토큰 만료/무효 → 로그인 페이지로
    if (res.status === 401 && Auth.isLoggedIn) {
      Auth.clear();
      location.href = '/login';
    }
    const msg = json.error || `요청 실패 (${res.status})`;
    const err = new Error(msg);
    err.code = json.code;
    err.status = res.status;
    throw err;
  }
  return json.data;
}

/* ── 화면 공통 유틸 ── */

/** alert div(.alert)에 메시지 표시 */
function showAlert(el, message, type = 'error') {
  if (!el) return;
  el.textContent = message;
  el.className = `alert show alert-${type}`;
}
function hideAlert(el) {
  if (el) el.className = 'alert';
}

/** 버튼 로딩 상태 토글 */
function setLoading(btn, loading, labelWhenDone) {
  if (!btn) return;
  if (loading) {
    btn.dataset.label = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 처리 중...';
  } else {
    btn.disabled = false;
    btn.innerHTML = labelWhenDone || btn.dataset.label || btn.innerHTML;
  }
}

/** 상단 네비게이션을 로그인 상태에 맞게 렌더 (요소 id="navLinks") */
function renderNav() {
  const nav = document.getElementById('navLinks');
  if (!nav) return;
  if (Auth.isLoggedIn) {
    nav.innerHTML = `
      <a href="/stats" class="live-badge" id="liveBadge" title="지금 공부 중인 사람 수">🛰️ <b id="liveCount">·</b><span class="live-word">공부 중</span></a>
      <a href="/board">게시판</a>
      <a href="/wiki">위키</a>
      <a href="/dashboard">대시보드</a>
      <a href="/notifications" class="bell" id="notifBell" title="알림">🔔<span class="bell-count hidden" id="bellCount">0</span></a>
      <span class="muted">${escapeHtml(Auth.username)}님</span>
      <a href="#" id="logoutBtn">로그아웃</a>`;
    document.getElementById('logoutBtn').onclick = (e) => { e.preventDefault(); Auth.logout(); };
    startNotifPolling();
  } else {
    nav.innerHTML = `
      <a href="/stats" class="live-badge" id="liveBadge" title="지금 공부 중인 사람 수">🛰️ <b id="liveCount">·</b><span class="live-word">공부 중</span></a>
      <a href="/board">게시판</a>
      <a href="/wiki">위키</a>
      <a href="/login">로그인</a>
      <a href="/register">회원가입</a>`;
  }
  startLivePolling();
}

/* 상단 알림 아이콘 — 미읽음 개수 폴링 (30초) */
let _notifTimer = null;
async function updateBell() {
  const badge = document.getElementById('bellCount');
  if (!badge) return;
  try {
    const d = await api('/api/notifications?size=1');
    const n = d.unread || 0;
    badge.textContent = n > 99 ? '99+' : n;
    badge.classList.toggle('hidden', n === 0);
  } catch (_) {}
}
function startNotifPolling() {
  updateBell();
  if (_notifTimer) clearInterval(_notifTimer);
  _notifTimer = setInterval(updateBell, 30000);
}

/* 상단 "지금 N명 공부 중" — 실시간 인원 폴링 (20초, 비회원 포함) */
let _liveTimer = null;
async function updateLive() {
  const el = document.getElementById('liveCount');
  if (!el) return;
  try {
    const d = await api('/api/study/live', { auth: false });
    const n = d.count || 0;
    el.textContent = n;
    document.getElementById('liveBadge')?.classList.toggle('alive', n > 0);
  } catch (_) { el.textContent = '·'; }
}
function startLivePolling() {
  updateLive();
  if (_liveTimer) clearInterval(_liveTimer);
  _liveTimer = setInterval(updateLive, 20000);
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]
  ));
}

/** ?key=value 쿼리 파라미터 읽기 */
function queryParam(key) {
  return new URLSearchParams(location.search).get(key);
}
