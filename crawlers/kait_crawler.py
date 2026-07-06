"""KAIT(한국정보통신진흥협회) 자격검정 크롤러 — DIAT 등.
실제 운영 사이트는 ihd.or.kr(자격검정 전용 포털)이며, 시험일정 표가
정적 HTML로 그대로 내려온다(로그인/자바스크립트 불필요).
"""
import re
import requests
from bs4 import BeautifulSoup

from crawlers.normalize import parse_date_range, upsert_exam, quarantine

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}
SCHEDULE_URL = 'https://www.ihd.or.kr/guidecert.do'

_ROUND_RE = re.compile(r'(\d+)\s*회')


def crawl_kait(cursor, fallback_year):
    """tbl_schedule 표를 파싱한다. 종목/등급 칸은 rowspan으로 여러 행에 걸쳐 있어서,
    BeautifulSoup이 그 칸을 생략한 행에서는 마지막으로 본 값을 그대로 이어 쓴다.
    """
    resp = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, 'html.parser')

    table = soup.find('table', class_='tbl_schedule')
    if not table:
        return {'saved': 0, 'failed': 0, 'error': 'tbl_schedule 표를 찾지 못함(페이지 구조 변경 가능성)'}

    body = table.find('tbody') or table
    saved, failed = 0, 0
    cur_subject, cur_level = None, None

    for tr in body.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        texts = [c.get_text(strip=True) for c in cells]

        # rowspan으로 생략된 앞쪽 칸(종목/등급)을 직전 값으로 채워 항상 6칸을 맞춘다
        if len(texts) == 6:
            cur_subject, cur_level = texts[0], texts[1]
            round_txt, apply_txt, exam_txt, result_txt = texts[2:6]
        elif len(texts) == 5:
            cur_level = texts[0]
            round_txt, apply_txt, exam_txt, result_txt = texts[1:5]
        elif len(texts) == 4:
            round_txt, apply_txt, exam_txt, result_txt = texts
        else:
            continue  # 헤더 등 데이터 행이 아님

        if cur_subject is None:
            quarantine(cursor, source='kait', raw={'row': texts}, reason='종목명을 아직 못 정함(표 첫 행 형식 확인 필요)')
            failed += 1
            continue

        m = _ROUND_RE.search(round_txt)
        round_ = int(m.group(1)) if m else None

        apply_start, apply_end, y = parse_date_range(apply_txt, fallback_year)
        exam_start,  exam_end,  y = parse_date_range(exam_txt,  fallback_year, y)
        result_start, _,        y = parse_date_range(result_txt, fallback_year, y)

        if apply_start is None and exam_start is None:
            quarantine(cursor, source='kait',
                       raw={'subject': cur_subject, 'level': cur_level, 'row': texts},
                       reason='날짜 파싱 실패')
            failed += 1
            continue

        name = f'{cur_subject} {cur_level}'.strip() if cur_level and cur_level != cur_subject else cur_subject
        upsert_exam(
            cursor, name=name, round_=round_, category='IT자격증(KAIT)', source='kait',
            apply_start=apply_start, apply_end=apply_end,
            exam_start=exam_start, exam_end=exam_end, result_date=result_start,
            source_url=SCHEDULE_URL,
        )
        saved += 1

    return {'saved': saved, 'failed': failed}
