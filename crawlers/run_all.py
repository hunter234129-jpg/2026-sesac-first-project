"""전체 시험 크롤러 오케스트레이터 — APScheduler(06:00/18:00)와 관리자 수동 실행
엔드포인트가 동일하게 이 함수 하나만 호출한다.
"""
import datetime

from db.connection import get_db
from crawlers.qnet_crawler import crawl_qnet_professional, crawl_qnet_technical
from crawlers.kait_crawler import crawl_kait


def crawl_and_normalize_all():
    fallback_year = datetime.date.today().year
    conn   = get_db()
    cursor = conn.cursor()
    results = {}
    try:
        for key, fn in [
            ('qnet_technical',   lambda: crawl_qnet_technical(cursor)),
            ('qnet_professional', lambda: crawl_qnet_professional(cursor, fallback_year)),
            ('kait',             lambda: crawl_kait(cursor, fallback_year)),
        ]:
            try:
                results[key] = fn()
                conn.commit()
            except Exception as e:
                conn.rollback()
                results[key] = {'error': str(e)}
    finally:
        conn.close()
    return results


if __name__ == '__main__':
    import json
    print(json.dumps(crawl_and_normalize_all(), ensure_ascii=False, indent=2))
