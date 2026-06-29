"""
Phase 1~3 스모크 테스트 — 주요 API 흐름을 순서대로 호출해 검증.
실행: python smoke_test.py
"""
import time
import requests

BASE = 'http://127.0.0.1:5000'
SUFFIX = str(int(time.time()))           # 매 실행 고유값 (중복 회원가입 방지)
EMAIL  = f'smoke_{SUFFIX}@test.com'
UNAME  = f'smoke_{SUFFIX}'

passed = failed = 0

def check(name, cond, detail=''):
    global passed, failed
    mark = 'PASS' if cond else 'FAIL'
    if cond: passed += 1
    else:    failed += 1
    print(f'[{mark}] {name}' + (f'  -> {detail}' if detail and not cond else ''))

def j(resp):
    try:    return resp.json()
    except Exception: return {}

# ── Auth ─────────────────────────────────────────────────────────────
r = requests.post(f'{BASE}/api/auth/register', json={
    'username': UNAME, 'email': EMAIL, 'password': '1234',
    'real_name': '테스터', 'interest_keywords': '파이썬,자바'
})
check('회원가입', r.status_code == 201, f'{r.status_code} {j(r)}')

r = requests.post(f'{BASE}/api/auth/login', json={'email': EMAIL, 'password': '1234'})
token = j(r).get('data', {}).get('access_token')
check('로그인 + 토큰 발급', bool(token), f'{r.status_code} {j(r)}')
H = {'Authorization': f'Bearer {token}'}

r = requests.get(f'{BASE}/api/auth/me', headers=H)
check('내 정보 조회', r.status_code == 200 and j(r)['data']['username'] == UNAME)

# ── Keyword + Notification (게시글 등록 시 알림 자동 생성) ────────────
r = requests.post(f'{BASE}/api/keywords', headers=H, json={'keyword': '파이썬'})
check('키워드 등록', r.status_code == 201, f'{r.status_code} {j(r)}')

r = requests.post(f'{BASE}/api/posts', headers=H, json={
    'title': '파이썬 스터디 모집합니다', 'content': '같이 공부해요', 'type': 'study'
})
post_id = j(r).get('data', {}).get('id')
check('게시글 작성', r.status_code == 201 and post_id, f'{r.status_code} {j(r)}')

r = requests.get(f'{BASE}/api/notifications', headers=H)
unread = j(r).get('data', {}).get('unread', 0)
check('키워드 알림 자동 생성', r.status_code == 200 and unread >= 1, f'unread={unread}')

r = requests.get(f'{BASE}/api/posts/{post_id}')
check('게시글 상세 + 조회수', r.status_code == 200 and j(r)['data']['view_count'] >= 1)

r = requests.get(f'{BASE}/api/auth/me/posts', headers=H)
check('내 게시글 목록', r.status_code == 200 and j(r)['data']['total'] >= 1)

# ── Study Session ────────────────────────────────────────────────────
r = requests.post(f'{BASE}/api/study/start', headers=H)
check('공부 시작', r.status_code == 201, f'{r.status_code} {j(r)}')

r = requests.get(f'{BASE}/api/study/status', headers=H)
check('세션 상태(active)', r.status_code == 200 and j(r)['data']['active'] is True)

time.sleep(1)
r = requests.post(f'{BASE}/api/study/end', headers=H)
dur = j(r).get('data', {}).get('duration_sec')
check('공부 종료 + duration 계산', r.status_code == 200 and dur is not None and dur >= 1, f'dur={dur}')

r = requests.get(f'{BASE}/api/study/stats', headers=H)
check('공부 통계', r.status_code == 200)

r = requests.get(f'{BASE}/api/study/ranking?period=all')
check('공부 랭킹', r.status_code == 200)

# ── Clan ─────────────────────────────────────────────────────────────
r = requests.post(f'{BASE}/api/clans', headers=H, json={
    'name': f'테스트클랜_{SUFFIX}', 'description': '스모크 테스트 클랜'
})
clan_id = j(r).get('data', {}).get('id')
check('클랜 생성', r.status_code == 201 and clan_id, f'{r.status_code} {j(r)}')

r = requests.get(f'{BASE}/api/clans/{clan_id}/members')
check('멤버 조회(생성자 자동가입)', r.status_code == 200 and len(j(r)['data']) == 1)

r = requests.delete(f'{BASE}/api/clans/{clan_id}/leave', headers=H)
check('클랜장 탈퇴 차단', r.status_code == 400, f'{r.status_code}')

# ── Mission ──────────────────────────────────────────────────────────
r = requests.get(f'{BASE}/api/missions/today', headers=H)
mid = j(r).get('data', {}).get('id')
check('오늘의 미션 조회', r.status_code == 200 and mid, f'{r.status_code} {j(r)}')

r = requests.post(f'{BASE}/api/missions/{mid}/done', headers=H)
check('미션 완료', r.status_code == 200)

r = requests.get(f'{BASE}/api/missions/history', headers=H)
check('미션 이력', r.status_code == 200 and len(j(r)['data']) >= 1)

# ── Wiki ─────────────────────────────────────────────────────────────
r = requests.post(f'{BASE}/api/wiki', headers=H, json={
    'title': f'스모크위키_{SUFFIX}', 'content': '# 제목\n내용입니다'
})
slug = j(r).get('data', {}).get('slug')
check('위키 생성', r.status_code == 201 and slug, f'{r.status_code} {j(r)}')

r = requests.get(f'{BASE}/api/wiki/{slug}')
check('위키 상세', r.status_code == 200)

# ── Admin (비관리자 → 403 차단 확인) ─────────────────────────────────
r = requests.get(f'{BASE}/api/admin/users', headers=H)
check('관리자 가드(비관리자 403)', r.status_code == 403, f'{r.status_code}')

# ── Upload ───────────────────────────────────────────────────────────
files = {'file': ('test.txt', b'hello upload', 'text/plain')}
r = requests.post(f'{BASE}/api/upload', headers=H, files=files)
url = j(r).get('data', {}).get('url')
check('파일 업로드', r.status_code == 201 and url, f'{r.status_code} {j(r)}')
if url:
    r = requests.get(f'{BASE}{url}')
    check('파일 다운로드', r.status_code == 200 and r.content == b'hello upload')

# ── 결과 ─────────────────────────────────────────────────────────────
print('\n' + '=' * 40)
print(f'  결과:  PASS {passed}  /  FAIL {failed}')
print('=' * 40)
