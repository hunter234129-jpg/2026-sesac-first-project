from flask import Blueprint, jsonify, request, g
from db.connection import get_db
from utils.auth import login_required
<<<<<<< HEAD
from config import GEMINI_API_KEY, GEMINI_MODEL
=======
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed

ai_bp = Blueprint('ai', __name__)

SYSTEM = (
    "너는 'StudyBoard'라는 학습 플랫폼의 AI 스터디 도우미야. "
    "한국어로 친절하고 명확하게, 학습에 실질적으로 도움이 되도록 답해. "
    "모르면 모른다고 솔직히 말하고, 답은 핵심부터 간결하게 정리해."
)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def _client():
<<<<<<< HEAD
    if not GEMINI_API_KEY:
        return None
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(messages, system=SYSTEM, max_tokens=8192):
    """Gemini 호출 → 텍스트 반환. 키 없으면 RuntimeError('NO_KEY')."""
    client = _client()
    if client is None:
        raise RuntimeError('NO_KEY')

    from google.genai import types

    # Anthropic 형식(role: assistant) → Gemini 형식(role: model) 변환
    contents = [
        types.Content(
            role='model' if m['role'] == 'assistant' else 'user',
            parts=[types.Part(text=m['content'])]
        )
        for m in messages
    ]

    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return resp.text.strip()
=======
    if not ANTHROPIC_API_KEY:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def call_claude(messages, system=SYSTEM, max_tokens=1500):
    """Claude 호출 → 텍스트 반환. 키 없으면 RuntimeError('NO_KEY')."""
    client = _client()
    if client is None:
        raise RuntimeError('NO_KEY')
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return ''.join(b.text for b in resp.content if b.type == 'text').strip()
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed


def _guard(fn):
    """공통 에러 처리 래퍼"""
    try:
        return fn()
    except RuntimeError as e:
        if str(e) == 'NO_KEY':
<<<<<<< HEAD
            return err('AI 기능을 쓰려면 서버에 GEMINI_API_KEY 환경변수를 설정해야 해요',
                       'NO_API_KEY', 503)
        raise
    except Exception as e:
        name = type(e).__name__
        if name == 'ModuleNotFoundError':
            return err('google-genai 패키지가 필요합니다 (pip install google-genai)', 'MISSING_DEPENDENCY', 500)
=======
            return err('AI 기능을 쓰려면 서버에 ANTHROPIC_API_KEY 환경변수를 설정해야 해요',
                       'NO_API_KEY', 503)
        raise
    except Exception as e:
        # anthropic 패키지 미설치 / API 오류 등
        name = type(e).__name__
        if name == 'ModuleNotFoundError':
            return err('anthropic 패키지가 필요합니다 (pip install anthropic)', 'MISSING_DEPENDENCY', 500)
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed
        return err(f'AI 응답 생성 실패: {e}', 'AI_FAILED', 502)


@ai_bp.route('/api/ai/chat', methods=['POST'])
@login_required
def chat():
    data     = request.get_json() or {}
    messages = data.get('messages')
    single   = data.get('message')

<<<<<<< HEAD
=======
    # messages 배열 우선, 없으면 단일 message
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed
    convo = []
    if isinstance(messages, list) and messages:
        for m in messages[-20:]:                     # 최근 20개만
            role = m.get('role')
            content = (m.get('content') or '').strip()
            if role in ('user', 'assistant') and content:
                convo.append({'role': role, 'content': content})
    elif single:
        convo = [{'role': 'user', 'content': single.strip()}]

    if not convo or convo[-1]['role'] != 'user':
        return err('보낼 메시지가 없습니다', 'EMPTY_MESSAGE')

<<<<<<< HEAD
    return _guard(lambda: ok({'reply': call_gemini(convo, max_tokens=8192)}))
=======
    return _guard(lambda: ok({'reply': call_claude(convo, max_tokens=2000)}))
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed


@ai_bp.route('/api/ai/summarize', methods=['POST'])
@login_required
def summarize():
    data    = request.get_json() or {}
    post_id = data.get('post_id')
    text    = (data.get('text') or '').strip()

<<<<<<< HEAD
=======
    # post_id가 오면 게시글 본문을 불러와 요약
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed
    if post_id:
        conn = get_db(); cursor = conn.cursor()
        try:
            cursor.execute(
                'SELECT title, content FROM posts WHERE id = %s AND deleted_at IS NULL',
                (post_id,)
            )
            post = cursor.fetchone()
        finally:
            conn.close()
        if not post:
            return err('게시글을 찾을 수 없습니다', 'NOT_FOUND', 404)
        text = f"제목: {post['title']}\n\n{post['content'] or ''}"

    if not text:
        return err('요약할 내용이 없습니다 (post_id 또는 text 필요)', 'EMPTY')

    prompt = f"다음 글을 핵심 위주로 3~5개의 불릿으로 요약해줘:\n\n{text}"
<<<<<<< HEAD
    return _guard(lambda: ok({'summary': call_gemini([{'role': 'user', 'content': prompt}], max_tokens=4096)}))
=======
    return _guard(lambda: ok({'summary': call_claude([{'role': 'user', 'content': prompt}], max_tokens=1000)}))
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed


@ai_bp.route('/api/ai/plan', methods=['POST'])
@login_required
def study_plan():
    data = request.get_json() or {}
    goal = (data.get('goal') or '').strip()
    if not goal:
        return err('목표(goal)를 입력해주세요', 'EMPTY_GOAL')

    prompt = (
        f"다음 학습 목표에 대한 현실적인 공부 계획을 세워줘. "
        f"기간이 명시되지 않았으면 4주를 기준으로, 주차별 목표와 매일 할 일을 표처럼 정리해줘.\n\n목표: {goal}"
    )
<<<<<<< HEAD
    return _guard(lambda: ok({'plan': call_gemini([{'role': 'user', 'content': prompt}], max_tokens=8192)}))
=======
    return _guard(lambda: ok({'plan': call_claude([{'role': 'user', 'content': prompt}], max_tokens=2500)}))
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed


@ai_bp.route('/api/ai/wiki-draft', methods=['POST'])
@login_required
def wiki_draft():
    data  = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return err('주제(title)를 입력해주세요', 'EMPTY_TITLE')

    prompt = (
        f"'{title}'에 대한 위키 문서 초안을 한국어로 작성해줘. "
        f"개요, 핵심 개념, 자세한 설명, 정리 순서로 구성하고 마크다운 형식으로 써줘."
    )
    return _guard(lambda: ok({'title': title,
<<<<<<< HEAD
                              'draft': call_gemini([{'role': 'user', 'content': prompt}], max_tokens=8192)}))
=======
                              'draft': call_claude([{'role': 'user', 'content': prompt}], max_tokens=3000)}))
>>>>>>> a44dcce5d27164e4347f36c481b199d4059f86ed
