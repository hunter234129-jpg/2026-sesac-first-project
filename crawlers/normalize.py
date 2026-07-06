"""크롤러 공용 유틸 — 날짜 파싱 + exams/exams_unparsed 저장.

여러 출처(Q-net 캘린더, Q-net 종목별, KAIT 등)가 날짜를 조금씩 다르게 표기한다:
  - "07.01(수)~07.02(목)"        (연도 없음 — 크롤링 시점 기준으로 추정 필요)
  - "2026.01.12~01.15"           (연도 명시, 종료일은 시작일과 같은 연도 공유)
  - "'25.12.08~12.17"            (2자리 연도, 작은따옴표)
  - "01.24"                      (연도 없이 단독 날짜 — 같은 행의 앞선 연도를 이어받음)

여기서는 "행 안에서 왼쪽부터 훑으면서, 연도가 명시되면 갱신하고 없으면 직전 연도를
그대로 쓴다"는 한 가지 규칙으로 전부 처리한다. 그래도 실패하면(패턴 자체가 안 맞으면)
None을 반환하고, 호출부가 exams_unparsed에 원본을 격리해서 조용히 틀린 데이터가
들어가는 일이 없게 한다.
"""
import json
import re
from datetime import date

_YEAR4 = r'(?:(\d{4})\.)?'
_YEAR2 = r"(?:'(\d{2})\.)?"
_MD    = r'(\d{1,2})\.(\d{1,2})'
_TOKEN_RE = re.compile(rf'{_YEAR4}{_YEAR2}{_MD}')


def _resolve_year(y4, y2, current_year, fallback_year):
    if y4:
        return int(y4)
    if y2:
        return 2000 + int(y2)
    return current_year or fallback_year


def parse_date_range(text, fallback_year, current_year=None):
    """"MM.DD" / "YYYY.MM.DD~MM.DD" 등 한 셀 안의 날짜(범위)를 (start, end, 마지막으로 확정된 연도)로.
    파싱 실패(날짜 토큰이 하나도 안 잡힘)하면 (None, None, current_year)를 반환한다.
    """
    if not text:
        return None, None, current_year
    matches = list(_TOKEN_RE.finditer(text))
    if not matches:
        return None, None, current_year

    dates = []
    year = current_year
    for m in matches:
        y4, y2, mm, dd = m.groups()
        year = _resolve_year(y4, y2, year, fallback_year)
        try:
            dates.append(date(year, int(mm), int(dd)))
        except ValueError:
            return None, None, current_year  # 2/30 같은 존재 안 하는 날짜 — 파싱 실패로 취급

    if len(dates) == 1:
        return dates[0], dates[0], year
    return dates[0], dates[-1], year


def extract_round(name_text):
    """"정보처리기사 제3회" 형태에서 (이름, 회차)를 분리. 회차가 없으면 (원문, None)."""
    m = re.search(r'제\s*(\d+)\s*회', name_text)
    if not m:
        return name_text.strip(), None
    return name_text[:m.start()].strip() or name_text.strip(), int(m.group(1))


def upsert_exam(cursor, *, name, round_=None, category=None, source,
                 apply_start=None, apply_end=None, exam_start=None, exam_end=None,
                 result_date=None, source_url=None):
    """exams 테이블에 upsert. 유니크 키는 (name, round) — Q-net 캘린더는 원서접수/시험일/
    발표일이 서로 다른 날짜(=다른 크롤링 행)로 따로따로 나오기 때문에, 한 번의 호출로는
    일부 필드만 채워질 수 있다. COALESCE로 "이번에 값이 없으면 기존 값 유지"하게 해서
    여러 번에 걸쳐 들어오는 부분 정보를 하나의 레코드로 누적한다.
    """
    cursor.execute(
        '''INSERT INTO exams
             (name, round, category, source, apply_start, apply_end,
              exam_start, exam_end, result_date, source_url, last_synced_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
           ON DUPLICATE KEY UPDATE
             category    = VALUES(category),
             source      = VALUES(source),
             apply_start = COALESCE(VALUES(apply_start), apply_start),
             apply_end   = COALESCE(VALUES(apply_end),   apply_end),
             exam_start  = COALESCE(VALUES(exam_start),  exam_start),
             exam_end    = COALESCE(VALUES(exam_end),    exam_end),
             result_date = COALESCE(VALUES(result_date), result_date),
             source_url  = COALESCE(VALUES(source_url),  source_url),
             last_synced_at = NOW()''',
        (name, round_, category, source, apply_start, apply_end,
         exam_start, exam_end, result_date, source_url)
    )


def quarantine(cursor, *, source, raw, reason):
    """날짜 파싱 등에 실패한 원본 행을 조용히 버리지 않고 검역 테이블에 남긴다."""
    cursor.execute(
        'INSERT INTO exams_unparsed (source, raw_data, reason) VALUES (%s, %s, %s)',
        (source, json.dumps(raw, ensure_ascii=False), reason)
    )
