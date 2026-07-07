"""Q-net(한국산업인력공단) 크롤러 — 국가기술자격(종목별 API) + 국가전문자격(캘린더).

국가기술자격은 같은 등급(기사/산업기사/기능사 등) 전체가 보통 같은 날 시험을 보지만,
정보보안기사처럼 시행기관이 Q-net(한국산업인력공단)이 아니라 다른 기관(KCA 등)인
예외가 있고, 그런 종목은 Q-net 자체 일정 API에 데이터가 없다. 그래서 종목마다
`qnet_jmcd_registry`에 등록해두고, schedulable=1인 것만 이 API로 가져온다.
"""
import re
import requests
from bs4 import BeautifulSoup

from crawlers.normalize import parse_date_range, upsert_exam, quarantine

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}

CALENDAR_URL = 'https://www.q-net.or.kr/crf021.do?id=crf02103&gSite=Q&gId=&CST_ID=CRF_Stns_06'
JMCD_SCHEDULE_URL = 'https://www.q-net.or.kr/crf005.do?id=crf00503s02&jmCd={jmcd}'

# "필기 원서접수 알아보기" 뒤에 항상 붙는 캘린더 등록 버튼 문구 — 파싱 전에 제거
_TAIL_SUFFIX_RE = re.compile(r'구글\s*일정에\s*현재\s*데이터\s*등록하기\s*$')
_ROUND_RE = re.compile(r'제?\s*(\d+)\s*회')

# 사건 설명 문자열에서 apply(원서접수) / exam(시험) / result(발표) 중 어느 필드에
# 해당하는지 판단하는 키워드. 순서가 중요 — "합격자 발표"를 "시험"보다 먼저 검사한다.
_EVENT_FIELD_KEYWORDS = [
    ('result', ['합격자 발표', '합격발표', '발표']),
    ('apply',  ['원서접수', '접수']),
    ('exam',   ['시험', '면접', '심사', '필기', '실기']),
]
# "제63회 변리사 2차"처럼 "시험"이라는 말 없이 그냥 "N차"로만 끝나는 경우도 있다 —
# Q-net 표기에서 회차 뒤의 "N차"는 항상 "N차 시험"을 뜻하므로 exam으로 분류한다.
_STAGE_ONLY_RE = re.compile(r'\d+차\s*$')


def _classify_event(text):
    for field, keywords in _EVENT_FIELD_KEYWORDS:
        if any(k in text for k in keywords):
            return field
    if _STAGE_ONLY_RE.search(text):
        return 'exam'
    return None


def crawl_qnet_professional(cursor, fallback_year):
    """캘린더 페이지에서 '전문자격'으로 시작하는(=구체적 이름이 나오는) 사건만 반영.
    '기술자격' 접두(등급명만 나오는 국가기술자격)는 crawl_qnet_technical이 담당하므로 건너뛴다.
    """
    resp = requests.get(CALENDAR_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, 'html.parser')

    saved, skipped, failed = 0, 0, 0
    for table in soup.find_all('table'):
        body = table.find('tbody') or table
        for tr in body.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            cells = [c for c in cells if c]
            if len(cells) != 2:
                continue
            date_text, desc_text = cells
            desc_text = _TAIL_SUFFIX_RE.sub('', desc_text)

            for event in desc_text.split(','):
                event = event.strip()
                if not event.startswith('전문자격'):
                    skipped += 1
                    continue
                event = event[len('전문자격'):].strip()

                m = _ROUND_RE.search(event)
                if not m:
                    quarantine(cursor, source='qnet_pro', raw={'date': date_text, 'event': event},
                               reason='회차(제N회) 패턴을 찾지 못함')
                    failed += 1
                    continue
                round_ = int(m.group(1))
                name = event[m.end():].strip()
                field = _classify_event(name)
                if not field:
                    quarantine(cursor, source='qnet_pro', raw={'date': date_text, 'event': event},
                               reason='원서접수/시험/발표 중 어느 것인지 판별 불가')
                    failed += 1
                    continue
                # 사건 유형 키워드(원서접수/시험/발표 등)를 떼어내면 순수 자격증명만 남는다
                cert_name = re.split('|'.join(
                    k for _, kws in _EVENT_FIELD_KEYWORDS for k in kws
                ), name)[0].strip() or name

                start, end, _ = parse_date_range(date_text, fallback_year)
                if start is None:
                    quarantine(cursor, source='qnet_pro', raw={'date': date_text, 'event': event},
                               reason='날짜 파싱 실패')
                    failed += 1
                    continue

                kwargs = {'name': cert_name, 'round_': round_, 'category': '전문자격',
                          'source': 'qnet_pro', 'source_url': CALENDAR_URL}
                if field == 'apply':
                    kwargs.update(apply_start=start, apply_end=end)
                elif field == 'exam':
                    kwargs.update(exam_start=start, exam_end=end)
                else:
                    kwargs.update(result_date=start)
                upsert_exam(cursor, **kwargs)
                saved += 1

    return {'saved': saved, 'skipped_tier_only': skipped, 'failed': failed}


def crawl_qnet_technical(cursor):
    """qnet_jmcd_registry에 등록된 종목마다 개별 시험일정 API를 조회해 그대로 반영."""
    cursor.execute('SELECT jmcd, cert_name FROM qnet_jmcd_registry WHERE schedulable = 1')
    targets = cursor.fetchall()

    saved, failed, no_data = 0, 0, 0
    for row in targets:
        jmcd, cert_name = row['jmcd'], row['cert_name']
        url = JMCD_SCHEDULE_URL.format(jmcd=jmcd)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
        except requests.RequestException as e:
            quarantine(cursor, source='qnet_tech', raw={'jmcd': jmcd, 'error': str(e)},
                       reason='요청 실패')
            failed += 1
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table')
        if not table or '시험정보가 없습니다' in resp.text:
            no_data += 1
            continue

        body = table.find('tbody') or table
        for tr in body.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if len(cells) < 7:
                continue
            gubun, wr_apply, wr_exam, wr_result, pr_apply, pr_exam, final_result = cells[:7]

            m = _ROUND_RE.search(gubun)
            round_ = int(m.group(1)) if m else None
            fallback_year_m = re.search(r'(\d{4})', gubun)
            fallback_year = int(fallback_year_m.group(1)) if fallback_year_m else None
            if round_ is None or fallback_year is None:
                quarantine(cursor, source='qnet_tech',
                           raw={'jmcd': jmcd, 'row': cells}, reason='구분 컬럼에서 연도/회차 추출 실패')
                failed += 1
                continue

            apply_start, apply_end, y = parse_date_range(wr_apply, fallback_year)
            exam_start,  exam_end,  y = parse_date_range(wr_exam,  fallback_year, y)
            result_start, _,        y = parse_date_range(final_result, fallback_year, y)

            if apply_start is None and exam_start is None:
                quarantine(cursor, source='qnet_tech', raw={'jmcd': jmcd, 'row': cells},
                           reason='날짜 파싱 실패')
                failed += 1
                continue

            upsert_exam(
                cursor, name=cert_name, round_=round_, category='국가기술자격',
                source='qnet_tech', apply_start=apply_start, apply_end=apply_end,
                exam_start=exam_start, exam_end=exam_end, result_date=result_start,
                source_url=f'https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd={jmcd}',
            )
            saved += 1

    return {'saved': saved, 'no_schedule_data': no_data, 'failed': failed, 'targets': len(targets)}
