/* ─────────────────────────────────────────────────────────────
   excalidraw-modal.js — Excalidraw 풀스크린 편집 모달

   ② UI/UX 충돌 대응: Excalidraw는 Tiptap의 ProseMirror DOM 안에는
   절대 마운트하지 않는다. 평소엔 이미지 한 장(wiki-editor.js의
   drawingBlock 노드뷰)만 보이고, "편집"을 누르면 완전히 별도의
   전역 오버레이(body 최상위, position:fixed, 풀스크린)에 새로
   React 루트를 마운트한다. 마우스 휠/드래그가 에디터의 스크롤이나
   ProseMirror 커서 이동과 물리적으로 같은 DOM 트리를 공유하지 않으므로
   이벤트 버블링 충돌 자체가 구조적으로 발생하지 않는다.

   React/Excalidraw 로딩: Excalidraw 0.17+ 는 더 이상 단일 UMD 파일을
   배포하지 않고 코드-스플릿된 ESM 번들만 제공한다(unpkg dist/ 확인 결과
   dist/prod 아래 청크 파일들로 쪼개져 있음). 그래서 UMD <script> 태그
   대신 esm.sh(의 자동 CJS/ESM 변환 + 의존성 고정)로 동적 import한다 —
   Tiptap/Yjs 조합에 쓴 것과 동일한 전략. 실제 그림을 열기 전까지는
   로드하지 않는다(무거운 번들을 방문자 전원에게 강제하지 않기 위함).
   ───────────────────────────────────────────────────────────── */

const REACT_VER  = 'react@18.3.1';
const RDOM_VER   = 'react-dom@18.3.1';
const EXCALI_VER = '@excalidraw/excalidraw@0.18.1';
const EXCALI_CSS = 'https://unpkg.com/@excalidraw/excalidraw@0.18.1/dist/prod/index.css';

let _loadPromise = null;
let _libs = null;   // { React, createRoot, Excalidraw, exportToBlob }

function ensureCss() {
  if (document.getElementById('excalidraw-css')) return;
  const link = document.createElement('link');
  link.id = 'excalidraw-css';
  link.rel = 'stylesheet';
  link.href = EXCALI_CSS;
  document.head.appendChild(link);
}

async function ensureLibs() {
  if (_loadPromise) return _loadPromise;
  _loadPromise = (async () => {
    ensureCss();
    const [React, ReactDOMClient, ExcalidrawPkg] = await Promise.all([
      import('https://esm.sh/' + REACT_VER),
      import('https://esm.sh/' + RDOM_VER + '/client?deps=' + REACT_VER),
      import('https://esm.sh/' + EXCALI_VER + '?deps=' + REACT_VER + ',' + RDOM_VER),
    ]);
    _libs = {
      React: React.default || React,
      createRoot: ReactDOMClient.createRoot,
      Excalidraw: ExcalidrawPkg.Excalidraw,
      exportToBlob: ExcalidrawPkg.exportToBlob,
    };
  })();
  return _loadPromise;
}

let overlayEl = null;
let reactRoot = null;
let excalidrawApi = null;
let presenceSocket = null;
let currentBlockId = null;
let currentSlug = null;
let prevHtmlZoom = null;   // 그림판 여는 동안 html의 zoom을 잠깐 1로 내렸다가 복구하기 위한 저장값

// html { zoom: 1.25 }(style.css)가 걸려있으면 Excalidraw 캔버스의 포인터 좌표 계산이
// 어긋나서 마우스 커서 위치와 실제 펜/지우개가 그려지는 위치가 달라진다(캔버스 기반
// 드로잉 라이브러리가 흔히 겪는 문제). 모달에만 CSS로 zoom:1을 걸면 position:fixed와
// 중첩된 zoom이 브라우저에서 꼬여서 모달 자체가 안 보이는 부작용이 있었다 — 그래서
// 특정 요소가 아니라 문서 전체(html)의 zoom을 열려있는 동안만 잠깐 1로 내린다.
function suspendPageZoom() {
  prevHtmlZoom = document.documentElement.style.zoom || '';
  document.documentElement.style.zoom = '1';
}
function restorePageZoom() {
  if (prevHtmlZoom !== null) document.documentElement.style.zoom = prevHtmlZoom;
  prevHtmlZoom = null;
}

function getSocket(slug) {
  if (presenceSocket && presenceSocket.connected) return presenceSocket;
  presenceSocket = window.io({ query: { token: (window.Auth && window.Auth.token) || '' } });
  presenceSocket.on('connect', () => presenceSocket.emit('join_wiki', { slug }));
  return presenceSocket;
}

function broadcastPresence(slug, blockId, editing) {
  const s = getSocket(slug);
  s.emit('drawing_presence', { slug, block_id: blockId, editing });
}

function buildOverlay() {
  const overlay = document.createElement('div');
  overlay.className = 'excalidraw-overlay';

  const panel = document.createElement('div');
  panel.className = 'excalidraw-panel';

  const header = document.createElement('div');
  header.className = 'excalidraw-header';
  header.innerHTML = `
    <span class="excalidraw-title">🎨 그림 편집</span>
    <div class="excalidraw-actions">
      <button type="button" class="btn btn-ghost" id="exCancelBtn">닫기</button>
      <button type="button" class="btn btn-primary" id="exSaveBtn">저장</button>
    </div>`;

  const mountDiv = document.createElement('div');
  mountDiv.className = 'excalidraw-mount';

  panel.append(header, mountDiv);
  overlay.appendChild(panel);

  // 배경 클릭 시 페이지 스크롤로 휠 이벤트가 새는 것만 차단(캔버스 자체 확대/축소는 Excalidraw가 자체 처리)
  overlay.addEventListener('wheel', (e) => { if (e.target === overlay || e.target === panel) e.preventDefault(); }, { passive: false });

  return { overlay, mountDiv, header };
}

async function open({ slug, blockId, onSaved }) {
  // slug는 없을 수 있다 — 위키를 아직 저장하지 않은 생성(초안) 화면에는 슬러그가
  // 없는데, 그런 경우까지 그림판을 막으면 "생성 화면에서 그림이 안 열린다"가 된다.
  // slug가 없으면 기존 씬 불러오기/scene_json 저장(재편집용)만 건너뛰고, 이미지
  // 업로드 자체는 그대로 진행해서 완성된 그림은 문서에 들어가게 한다.
  if (!blockId) return;
  currentBlockId = blockId;
  currentSlug = slug || null;
  suspendPageZoom();

  let loadErr = null;
  try { await ensureLibs(); } catch (e) { loadErr = e; }

  const { overlay, mountDiv, header } = buildOverlay();
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  overlayEl = overlay;

  if (loadErr) {
    mountDiv.innerHTML = `<p class="muted" style="padding:40px;text-align:center;">그림 도구를 불러오지 못했어요. 네트워크 연결을 확인해주세요.</p>`;
    header.querySelector('#exCancelBtn').onclick = close;
    return;
  }

  // 기존 씬 불러오기(있으면 이어서 편집) — 아직 저장 안 된 위키(slug 없음)는 건너뛴다.
  let initialData = undefined;
  if (slug) {
    try {
      const d = await window.api('/api/wiki/' + encodeURIComponent(slug) + '/drawings/' + encodeURIComponent(blockId), { auth: false });
      if (d && d.scene_json) {
        const parsed = JSON.parse(d.scene_json);
        initialData = { elements: parsed.elements || [], appState: parsed.appState || {} };
      }
    } catch (_) { /* 최초 편집 — 빈 캔버스로 시작 */ }

    broadcastPresence(slug, blockId, true);
  }

  const { React, createRoot, Excalidraw } = _libs;
  reactRoot = createRoot(mountDiv);
  reactRoot.render(
    React.createElement(Excalidraw, {
      initialData,
      excalidrawAPI: (api) => { excalidrawApi = api; },
      theme: 'dark',
    })
  );

  header.querySelector('#exCancelBtn').onclick = close;
  header.querySelector('#exSaveBtn').onclick = async () => {
    if (!excalidrawApi) return close();
    const btn = header.querySelector('#exSaveBtn');
    const prevLabel = btn.textContent;
    btn.disabled = true; btn.textContent = '저장 중...';
    try {
      const elements = excalidrawApi.getSceneElements();
      const appState  = excalidrawApi.getAppState();
      const files     = excalidrawApi.getFiles();

      const blob = await _libs.exportToBlob({
        elements, appState, files, mimeType: 'image/png',
      });

      const form = new FormData();
      form.append('file', blob, blockId + '.png');
      form.append('ref_type', 'wiki_drawing');
      const uploaded = await window.api('/api/upload', { method: 'POST', body: form, isForm: true });

      // scene_json(재편집용 원본 벡터 데이터)은 위키 문서가 실제로 존재해야 저장할 수 있다.
      // 아직 저장 전 초안(slug 없음)이면 이미지 자체는 그대로 문서에 들어가지만,
      // 벡터 재편집 데이터는 위키를 처음 저장한 뒤부터 저장된다.
      if (slug) {
        const sceneJson = JSON.stringify({
          elements,
          appState: { viewBackgroundColor: appState.viewBackgroundColor },
        });
        await window.api('/api/wiki/' + encodeURIComponent(slug) + '/drawings/' + encodeURIComponent(blockId), {
          method: 'PUT', body: { scene_json: sceneJson, png_file_id: uploaded.id },
        });
      }

      if (onSaved) onSaved(uploaded.url);
      close();
    } catch (err) {
      btn.disabled = false; btn.textContent = prevLabel;
      alert('저장에 실패했어요: ' + err.message);
    }
  };
}

function close() {
  if (!overlayEl) return;
  if (currentBlockId && currentSlug) broadcastPresence(currentSlug, currentBlockId, false);
  if (reactRoot) { reactRoot.unmount(); reactRoot = null; }
  overlayEl.remove();
  overlayEl = null;
  excalidrawApi = null;
  currentBlockId = null;
  currentSlug = null;
  document.body.style.overflow = '';
  restorePageZoom();
}

window.ExcalidrawModal = { open, close };
