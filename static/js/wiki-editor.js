/* ─────────────────────────────────────────────────────────────
   wiki-editor.js — Tiptap 리치 에디터 + Yjs 실시간 협업 + Drawing/Chart 블록

   설계 원칙(제약사항 대응):
   ① 데이터 크기: Excalidraw 벡터 씬은 DB에 두되(wiki_drawings, 재편집용),
      Tiptap 문서에는 image_url + block_id만 들어간다. 편집 모드가 아닌
      한 벡터 JSON은 절대 이 파일이 다루는 문서 트리에 로드되지 않는다.
   ② UI/UX 충돌: 그림 블록은 평소 <img> 하나만 렌더링한다. Excalidraw는
      이 파일이 만드는 ProseMirror DOM 안에 절대 마운트하지 않고,
      전역 풀스크린 모달(excalidraw-modal.js)에서만 마운트한다.
   ③ SSR: 이 프로젝트는 서버 렌더링이 없는 Flask+정적 HTML이라 해당 없음.
      다만 무거운 라이브러리는 mount() 호출 시점에만 동적 import한다.

   Yjs/ProseMirror 계열 패키지는 esm.sh 의 ?deps= 로 버전을 강제 고정해
   서로 다른 사본이 로드되어 instanceof 불일치가 나는 것을 방지한다.
   (버전은 2025년 기준 상호 호환되는 조합. 브라우저 콘솔에 peer 불일치
   경고가 뜨면 이 상수만 맞는 버전으로 교체하면 된다.)
   ───────────────────────────────────────────────────────────── */

const PM  = 'prosemirror-state@1.4.3,prosemirror-view@1.33.9,prosemirror-model@1.23.0,prosemirror-transform@1.10.2';
const YJS = 'yjs@13.6.19';

const CURSOR_COLORS = ['#4f8eff', '#3ad4ff', '#a06bff', '#ffb740', '#2fd69e', '#f06060'];

let _mod = null;   // 동적 import된 라이브러리 캐시(중복 로드 방지)
async function loadLibs() {
  if (_mod) return _mod;
  const [core, starterKit, collab, collabCursor, Y, awarenessMod] = await Promise.all([
    import('https://esm.sh/@tiptap/core@2.9.1?deps=' + PM),
    import('https://esm.sh/@tiptap/starter-kit@2.9.1?deps=' + PM),
    import('https://esm.sh/@tiptap/extension-collaboration@2.9.1?deps=' + PM + ',' + YJS),
    import('https://esm.sh/@tiptap/extension-collaboration-cursor@2.9.1?deps=' + PM + ',' + YJS),
    import('https://esm.sh/' + YJS),
    import('https://esm.sh/y-protocols@1.0.6/awareness?deps=' + YJS),
  ]);
  _mod = {
    Editor: core.Editor, Node: core.Node, mergeAttributes: core.mergeAttributes,
    StarterKit: starterKit.default,
    Collaboration: collab.default,
    CollaborationCursor: collabCursor.default,
    Y, Awareness: awarenessMod.Awareness,
  };
  return _mod;
}

function makeDrawingBlock({ Node, mergeAttributes }) {
  return Node.create({
    name: 'drawingBlock',
    group: 'block',
    atom: true,
    selectable: true,
    draggable: true,
    addAttributes() {
      return {
        blockId:  { default: null },
        imageUrl: { default: null },
        version:  { default: 0 },
      };
    },
    parseHTML() { return [{ tag: 'div[data-drawing-block]' }]; },
    renderHTML({ HTMLAttributes }) {
      return ['div', mergeAttributes(HTMLAttributes, { 'data-drawing-block': '' })];
    },
    addNodeView() {
      return ({ node, editor, getPos }) => {
        const dom = document.createElement('div');
        dom.className = 'wiki-drawing-block';
        dom.contentEditable = false;

        const empty = document.createElement('div');
        empty.className = 'wdb-empty';
        empty.textContent = '🎨 빈 그림 — "편집"을 눌러 그려보세요';

        const img = document.createElement('img');
        img.className = 'wdb-img';

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'wdb-edit-btn';
        editBtn.textContent = '✏️ 편집';
        editBtn.style.display = editor.isEditable ? '' : 'none';

        const presence = document.createElement('div');
        presence.className = 'wdb-presence hidden';

        dom.append(empty, img, editBtn, presence);

        function render() {
          const url = node.attrs.imageUrl;
          img.style.display   = url ? 'block' : 'none';
          empty.style.display = url ? 'none'  : 'flex';
          if (url) img.src = url + (url.includes('?') ? '&' : '?') + 'v=' + (node.attrs.version || 0);
        }
        render();

        editBtn.addEventListener('click', (e) => {
          e.preventDefault();
          window.ExcalidrawModal && window.ExcalidrawModal.open({
            slug: window.__wikiEditorSlug,
            blockId: node.attrs.blockId,
            onSaved: (imageUrl) => {
              if (typeof getPos !== 'function') return;
              editor.view.dispatch(editor.view.state.tr.setNodeMarkup(getPos(), undefined, {
                ...node.attrs, imageUrl, version: (node.attrs.version || 0) + 1,
              }));
            },
          });
        });

        const onPresence = (e) => {
          const p = e.detail;
          if (p.block_id !== node.attrs.blockId) return;
          presence.textContent = p.editing ? `🔒 편집 중: ${p.username}` : '';
          presence.classList.toggle('hidden', !p.editing);
        };
        window.addEventListener('wiki:drawing-presence', onPresence);

        return {
          dom,
          update(updated) {
            if (updated.type.name !== 'drawingBlock') return false;
            node = updated; render(); return true;
          },
          destroy() { window.removeEventListener('wiki:drawing-presence', onPresence); },
          ignoreMutation: () => true,
        };
      };
    },
  });
}

function makeChartBlock({ Node, mergeAttributes }) {
  return Node.create({
    name: 'chartBlock',
    group: 'block',
    atom: true,
    selectable: true,
    draggable: true,
    addAttributes() {
      return {
        chartType: { default: 'bar' },
        title:     { default: '' },
        labels:    { default: '["항목1","항목2","항목3"]' },
        values:    { default: '[10,20,15]' },
      };
    },
    parseHTML() { return [{ tag: 'div[data-chart-block]' }]; },
    renderHTML({ HTMLAttributes }) {
      return ['div', mergeAttributes(HTMLAttributes, { 'data-chart-block': '' })];
    },
    addNodeView() {
      return ({ node, editor, getPos }) => {
        const dom = document.createElement('div');
        dom.className = 'wiki-chart-block';
        dom.contentEditable = false;

        const canvas = document.createElement('canvas');
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'wcb-edit-btn';
        editBtn.textContent = '✏️ 편집';
        editBtn.style.display = editor.isEditable ? '' : 'none';

        const form = document.createElement('div');
        form.className = 'wcb-form hidden';
        form.innerHTML = `
          <label>제목 <input type="text" class="wcb-title"></label>
          <label>종류
            <select class="wcb-type">
              <option value="bar">막대</option>
              <option value="line">선</option>
              <option value="pie">원형</option>
            </select>
          </label>
          <label>항목 (쉼표로 구분) <input type="text" class="wcb-labels" placeholder="1월, 2월, 3월"></label>
          <label>값 (쉼표로 구분) <input type="text" class="wcb-values" placeholder="10, 20, 15"></label>
          <div class="wcb-form-actions">
            <button type="button" class="btn btn-primary wcb-apply">적용</button>
            <button type="button" class="btn btn-ghost wcb-cancel">취소</button>
          </div>`;

        dom.append(canvas, editBtn, form);

        let chartInst = null;
        function draw() {
          if (!window.Chart) return;
          let labels = [], values = [];
          try { labels = JSON.parse(node.attrs.labels); } catch (_) {}
          try { values = JSON.parse(node.attrs.values); } catch (_) {}
          if (chartInst) chartInst.destroy();
          chartInst = new window.Chart(canvas, {
            type: node.attrs.chartType,
            data: {
              labels,
              datasets: [{ label: node.attrs.title || '', data: values, backgroundColor: CURSOR_COLORS }],
            },
            options: {
              responsive: true,
              plugins: { title: { display: !!node.attrs.title, text: node.attrs.title } },
            },
          });
        }
        draw();

        editBtn.addEventListener('click', (e) => {
          e.preventDefault();
          form.querySelector('.wcb-title').value = node.attrs.title || '';
          form.querySelector('.wcb-type').value  = node.attrs.chartType || 'bar';
          try { form.querySelector('.wcb-labels').value = JSON.parse(node.attrs.labels).join(', '); } catch (_) {}
          try { form.querySelector('.wcb-values').value = JSON.parse(node.attrs.values).join(', '); } catch (_) {}
          form.classList.remove('hidden');
        });
        form.querySelector('.wcb-cancel').addEventListener('click', (e) => {
          e.preventDefault(); form.classList.add('hidden');
        });
        form.querySelector('.wcb-apply').addEventListener('click', (e) => {
          e.preventDefault();
          const labels = form.querySelector('.wcb-labels').value.split(',').map(s => s.trim()).filter(Boolean);
          const values = form.querySelector('.wcb-values').value.split(',').map(s => Number(s.trim()) || 0);
          if (typeof getPos !== 'function') return;
          editor.view.dispatch(editor.view.state.tr.setNodeMarkup(getPos(), undefined, {
            ...node.attrs,
            title:     form.querySelector('.wcb-title').value,
            chartType: form.querySelector('.wcb-type').value,
            labels:    JSON.stringify(labels),
            values:    JSON.stringify(values),
          }));
          form.classList.add('hidden');
        });
        form.addEventListener('mousedown', (e) => e.stopPropagation());

        return {
          dom,
          update(updated) {
            if (updated.type.name !== 'chartBlock') return false;
            node = updated; draw(); return true;
          },
          destroy() { if (chartInst) chartInst.destroy(); },
          ignoreMutation: () => true,
        };
      };
    },
  });
}

/** 저장된 content 문자열 → Tiptap JSON 문서. 구버전(순수 텍스트) 위키도 문단으로 감싸 표시. */
function toTiptapDoc(raw) {
  if (!raw) return { type: 'doc', content: [{ type: 'paragraph' }] };
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.type === 'doc') return parsed;
  } catch (_) { /* 레거시 텍스트 */ }
  const paras = String(raw).split(/\n{2,}/);
  return {
    type: 'doc',
    content: paras.map(p => ({
      type: 'paragraph',
      content: p ? [{ type: 'text', text: p }] : [],
    })),
  };
}

let editor = null;
let ydoc = null;
let socket = null;
let autosaveTimer = null;
let snapshotTimer = null;
let dirtySinceSnapshot = false;

const SNAPSHOT_INTERVAL_MS = 5 * 60 * 1000;   // 5분마다 이력에 자동 스냅샷 기록

function mkToolbarBtn(label, title, onClick, extraClass) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'tb-btn' + (extraClass ? ' ' + extraClass : '');
  btn.title = title;
  btn.textContent = label;
  // 버튼 클릭으로 에디터의 현재 선택 영역이 풀리지 않도록(포커스 이동 방지)
  btn.addEventListener('mousedown', (e) => e.preventDefault());
  btn.addEventListener('click', onClick);
  return btn;
}

/** 삼성노트/노션처럼 입력 영역 바로 위에 붙는 서식 도구모음(편집 가능할 때만) */
function buildToolbar(editorInstance, { title }) {
  const bar = document.createElement('div');
  bar.className = 'tiptap-toolbar';

  const fmtGroup = document.createElement('div');
  fmtGroup.className = 'tb-group';
  const FORMAT_BUTTONS = [
    { label: 'B',   title: '굵게 (Ctrl+B)',     cls: 'tb-bold',   cmd: e => e.chain().focus().toggleBold().run(),                    active: e => e.isActive('bold') },
    { label: 'I',   title: '기울임 (Ctrl+I)',   cls: 'tb-italic', cmd: e => e.chain().focus().toggleItalic().run(),                  active: e => e.isActive('italic') },
    { label: 'S',   title: '취소선',            cls: 'tb-strike', cmd: e => e.chain().focus().toggleStrike().run(),                  active: e => e.isActive('strike') },
    { label: '</>', title: '인라인 코드',        cmd: e => e.chain().focus().toggleCode().run(),                     active: e => e.isActive('code') },
    { divider: true },
    { label: 'H1',  title: '제목 1',            cmd: e => e.chain().focus().toggleHeading({ level: 1 }).run(),      active: e => e.isActive('heading', { level: 1 }) },
    { label: 'H2',  title: '제목 2',            cmd: e => e.chain().focus().toggleHeading({ level: 2 }).run(),      active: e => e.isActive('heading', { level: 2 }) },
    { label: 'H3',  title: '제목 3',            cmd: e => e.chain().focus().toggleHeading({ level: 3 }).run(),      active: e => e.isActive('heading', { level: 3 }) },
    { divider: true },
    { label: '•—',  title: '글머리 기호 목록',   cmd: e => e.chain().focus().toggleBulletList().run(),               active: e => e.isActive('bulletList') },
    { label: '1.',  title: '번호 매기기 목록',   cmd: e => e.chain().focus().toggleOrderedList().run(),              active: e => e.isActive('orderedList') },
    { label: '"',   title: '인용구',            cmd: e => e.chain().focus().toggleBlockquote().run(),               active: e => e.isActive('blockquote') },
    { label: '{ }', title: '코드 블록',          cmd: e => e.chain().focus().toggleCodeBlock().run(),                active: e => e.isActive('codeBlock') },
    { label: '―',   title: '구분선',            cmd: e => e.chain().focus().setHorizontalRule().run(),              active: () => false },
  ];
  FORMAT_BUTTONS.forEach((b) => {
    if (b.divider) { fmtGroup.appendChild(Object.assign(document.createElement('span'), { className: 'tb-divider' })); return; }
    b.el = mkToolbarBtn(b.label, b.title, () => b.cmd(editorInstance), b.cls);
    fmtGroup.appendChild(b.el);
  });

  const insertGroup = document.createElement('div');
  insertGroup.className = 'tb-group';
  insertGroup.append(
    mkToolbarBtn('🎨 그림', '그림 추가', () => insertDrawing(), 'tb-insert'),
    mkToolbarBtn('📊 차트', '차트 추가', () => insertChart(), 'tb-insert'),
  );
  const aiBtn = mkToolbarBtn('🛰️ AI 초안', 'AI가 초안을 작성해요', async () => {
    const prevLabel = aiBtn.textContent;
    aiBtn.disabled = true; aiBtn.textContent = '생성 중...';
    try {
      const draft = await window.api('/api/ai/wiki-draft', { method: 'POST', body: { title: title || '' } });
      editorInstance.commands.setContent(toTiptapDoc(draft.draft));
    } catch (err) {
      alert('AI 초안 생성에 실패했어요: ' + err.message);
    } finally {
      aiBtn.disabled = false; aiBtn.textContent = prevLabel;
    }
  }, 'tb-insert tb-ai');
  insertGroup.appendChild(aiBtn);

  bar.append(fmtGroup, insertGroup);

  editorInstance.on('transaction', () => {
    FORMAT_BUTTONS.forEach((b) => { if (b.el) b.el.classList.toggle('is-active', !!b.active(editorInstance)); });
  });

  return bar;
}

/**
 * 위키 문서를 마운트한다 — 보기/편집 구분 없이 항상 같은 실시간 세션에 join한다.
 * editable=false(뷰어/비로그인)여도 다른 사람의 편집이 새로고침 없이 그대로 반영된다.
 * editable=true(로그인 사용자)일 때만 로컬 편집 + 자동저장/자동 스냅샷을 수행하고,
 * 입력 영역 바로 위에 서식 도구모음을 붙인다.
 */
async function mount({ container, slug, initialContent, username, editable, title }) {
  await destroy();
  window.__wikiEditorSlug = slug;

  const { Editor, Node, mergeAttributes, StarterKit, Collaboration, CollaborationCursor, Y, Awareness } = await loadLibs();
  const DrawingBlock = makeDrawingBlock({ Node, mergeAttributes });
  const ChartBlock   = makeChartBlock({ Node, mergeAttributes });

  ydoc = new Y.Doc();
  const awareness = new Awareness(ydoc);
  const fragment = ydoc.getXmlFragment('wiki-content');

  container.innerHTML = '';
  const contentEl = document.createElement('div');
  contentEl.className = 'tiptap-content';

  editor = new Editor({
    element: contentEl,
    editable: !!editable,
    extensions: [
      StarterKit.configure({ history: false }),
      Collaboration.configure({ document: ydoc, field: 'wiki-content' }),
      CollaborationCursor.configure({
        provider: { awareness },
        user: { name: username || '익명', color: CURSOR_COLORS[Math.floor(Math.random() * CURSOR_COLORS.length)] },
      }),
      DrawingBlock, ChartBlock,
    ],
  });

  if (editable) container.appendChild(buildToolbar(editor, { title }));
  container.appendChild(contentEl);

  // ── 실시간 동기화: 서버는 Yjs 업데이트를 해석하지 않고 방(room) 안에서만 릴레이한다 ──
  // 뷰어도 같은 방에 join하므로 편집 화면을 열지 않아도 남의 변경이 바로 보인다.
  let receivedRemoteSync = false;
  socket = window.io({ query: { token: (window.Auth && Auth.token) || '' } });

  socket.on('connect', () => {
    socket.emit('join_wiki', { slug });
    socket.emit('request_sync', { slug });
  });
  socket.on('request_sync', () => {
    if (ydoc) socket.emit('full_sync', { slug, state: Y.encodeStateAsUpdate(ydoc) });
  });
  socket.on('full_sync', ({ state }) => {
    receivedRemoteSync = true;
    Y.applyUpdate(ydoc, new Uint8Array(state), 'remote');
  });
  socket.on('doc_update', ({ update }) => {
    Y.applyUpdate(ydoc, new Uint8Array(update), 'remote');
  });
  socket.on('drawing_presence', (payload) => {
    window.dispatchEvent(new CustomEvent('wiki:drawing-presence', { detail: payload }));
  });

  ydoc.on('update', (update, origin) => {
    if (origin === 'remote') return;   // 원격에서 받은 걸 그대로 되돌려 보내지 않음
    if (socket && socket.connected) socket.emit('doc_update', { slug, update });
    if (editable) { dirtySinceSnapshot = true; scheduleAutosave(slug); }
  });

  // 다른 접속자가 이미 있으면 그 실시간 상태를 우선한다(중복 삽입 방지를 위한 짧은 유예).
  await new Promise(resolve => setTimeout(resolve, 450));
  if (fragment.length === 0 && !receivedRemoteSync && initialContent) {
    editor.commands.setContent(toTiptapDoc(initialContent));
  }

  if (editable) startSnapshotTimer(slug);

  return editor;
}

function scheduleAutosave(slug) {
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(async () => {
    if (!editor || !slug || !window.api) return;
    try {
      await window.api('/api/wiki/' + encodeURIComponent(slug) + '/autosave', {
        method: 'PATCH', body: { content: JSON.stringify(editor.getJSON()) },
      });
      window.dispatchEvent(new CustomEvent('wiki:autosaved'));
    } catch (_) { /* 자동 저장 실패는 조용히 무시(다음 저장 사이클에서 재시도) */ }
  }, 2000);
}

// 저장 버튼 없이도 이력이 의미를 갖도록, 실제 변경이 있었던 경우에만 일정 주기로
// wiki_revisions에 새 버전을 스냅샷으로 남긴다(요약은 자동 생성).
function startSnapshotTimer(slug) {
  clearInterval(snapshotTimer);
  snapshotTimer = setInterval(async () => {
    if (!editor || !dirtySinceSnapshot || !window.api) return;
    try {
      await window.api('/api/wiki/' + encodeURIComponent(slug), {
        method: 'PUT',
        body: { content: JSON.stringify(editor.getJSON()), summary: '자동 스냅샷 · ' + new Date().toLocaleString() },
      });
      dirtySinceSnapshot = false;
      window.dispatchEvent(new CustomEvent('wiki:snapshotted'));
    } catch (_) { /* 다음 주기에 재시도 */ }
  }, SNAPSHOT_INTERVAL_MS);
}

async function destroy() {
  clearTimeout(autosaveTimer);
  clearInterval(snapshotTimer);
  dirtySinceSnapshot = false;
  if (socket) { socket.emit('leave_wiki', { slug: window.__wikiEditorSlug }); socket.disconnect(); socket = null; }
  if (editor) { editor.destroy(); editor = null; }
  ydoc = null;
}

// atom 노드(그림/차트) 삽입 직후에는 ProseMirror가 그 노드를 NodeSelection으로 선택된
// 상태로 두는데, 그 상태에서 다음 insertContent를 호출하면 방금 넣은 블록을 "대체"해버린다.
// 뒤에 빈 문단을 함께 넣어 커서를 텍스트 선택으로 옮겨두면 연속 삽입이 서로 덮어쓰지 않는다.
function insertDrawing() {
  if (!editor) return;
  editor.chain().focus().insertContent([
    { type: 'drawingBlock', attrs: { blockId: crypto.randomUUID(), imageUrl: null, version: 0 } },
    { type: 'paragraph' },
  ]).run();
}

function insertChart() {
  if (!editor) return;
  editor.chain().focus().insertContent([
    { type: 'chartBlock', attrs: {} },
    { type: 'paragraph' },
  ]).run();
}

window.WikiEditor = {
  mount, destroy, insertDrawing, insertChart, toTiptapDoc,
  getEditor: () => editor,
};
