import datetime
from flask import Blueprint, jsonify, request

crawl_bp = Blueprint('crawl', __name__)

QNET_URL = 'https://www.q-net.or.kr/crf021.do?id=crf02103&gSite=Q&gId=&CST_ID=CRF_Stns_06'

# 간단한 메모리 캐시 (외부 사이트 과도 요청 방지, 1시간 유지)
_cache = {'fetched_at': None, 'data': None}
_CACHE_TTL = datetime.timedelta(hours=1)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def crawl_qnet_schedule():
    """q-net 연간 시험일정 페이지를 크롤링해 표 데이터를 반환"""
    import requests
    from bs4 import BeautifulSoup

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0 Safari/537.36'
    }
    resp = requests.get(QNET_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    soup   = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table')

    schedules = []
    for table in tables:
        # 헤더 추출
        headers_row = []
        thead = table.find('thead')
        if thead:
            headers_row = [th.get_text(strip=True) for th in thead.find_all('th')]

        body = table.find('tbody') or table
        for tr in body.find_all('tr'):
            cells = []
            for td in tr.find_all(['td', 'th']):
                for btn in td.find_all('button'):
                    btn.extract()
                cells.append(td.get_text(strip=True))
            cells = [c for c in cells if c]
            if not cells:
                continue
            if headers_row and len(cells) == len(headers_row):
                schedules.append(dict(zip(headers_row, cells)))
            else:
                schedules.append({'columns': cells})

    return {
        'source':  QNET_URL,
        'count':   len(schedules),
        'schedules': schedules
    }


@crawl_bp.route('/api/exam-schedule', methods=['GET'])
def exam_schedule():
    now   = datetime.datetime.now()
    force = request.args.get('refresh') == '1'

    # 캐시 유효하면 재사용
    if not force and _cache['data'] and _cache['fetched_at'] \
            and now - _cache['fetched_at'] < _CACHE_TTL:
        return ok({**_cache['data'], 'cached': True})

    try:
        data = crawl_qnet_schedule()
    except ImportError:
        return err('requests, beautifulsoup4 패키지가 필요합니다 (pip install requests beautifulsoup4)',
                   'MISSING_DEPENDENCY', 500)
    except Exception as e:
        # 크롤링 실패 시 캐시된 데이터라도 반환
        if _cache['data']:
            return ok({**_cache['data'], 'cached': True, 'stale': True})
        return err(f'시험일정을 가져오지 못했습니다: {e}', 'CRAWL_FAILED', 502)

    _cache['data']       = data
    _cache['fetched_at'] = now
    return ok({**data, 'cached': False})
