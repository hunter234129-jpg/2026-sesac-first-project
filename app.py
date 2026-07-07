from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
import os
from config import MAX_UPLOAD_BYTES
from extensions import socketio

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES
CORS(app)
socketio.init_app(app)

from routes.auth         import auth_bp
from routes.post         import post_bp
from routes.comment      import comment_bp
from routes.wiki         import wiki_bp
from routes.study        import study_bp
from routes.notification import notification_bp
from routes.upload       import upload_bp
from routes.mission      import mission_bp
from routes.crawl        import crawl_bp
from routes.admin        import admin_bp
from routes.ocr          import ocr_bp
from routes.ai           import ai_bp
from routes.achievement  import achievement_bp
from routes.quiz         import quiz_bp
from routes.wrongnote    import wrongnote_bp
from routes.exams        import exams_bp
import routes.wiki_sync         # noqa: F401 — 위키 실시간 협업 SocketIO 핸들러 등록
import sockets.chat_events      # noqa: F401 — 1:1 채팅 SocketIO 핸들러 등록
import sockets.post_chat_events # noqa: F401 — 모임 그룹 채팅 SocketIO 핸들러 등록(chat_events의 sid_user 재사용)
sockets.chat_events.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(post_bp)
app.register_blueprint(comment_bp)
app.register_blueprint(wiki_bp)
app.register_blueprint(study_bp)
app.register_blueprint(notification_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(mission_bp)
app.register_blueprint(crawl_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(ocr_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(achievement_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(wrongnote_bp)
app.register_blueprint(exams_bp)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

# ── 시험 일정 크롤러 스케줄러 (매일 06:00, 18:00 KST) ──────────────────
# Flask 프로세스 안에 내장해서 OS(작업 스케줄러/cron)에 의존하지 않는다 —
# 지금은 윈도우에서 개발하지만 나중에 리눅스로 옮겨도 코드 수정 없이 그대로 동작한다.
# debug=True일 때 Werkzeug 리로더가 프로세스를 2개(부모 감시자+자식) 띄우는데,
# WERKZEUG_RUN_MAIN은 "실제로 요청을 처리하는 자식 프로세스"에서만 설정되므로
# 이 체크 없이 그냥 등록하면 스케줄러가 2번 등록돼 크롤링이 중복 실행된다.
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    from apscheduler.schedulers.background import BackgroundScheduler

    def _run_exam_crawl_job():
        from crawlers.run_all import crawl_and_normalize_all
        crawl_and_normalize_all()

    _scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    _scheduler.add_job(_run_exam_crawl_job, 'cron', hour='6,18', minute=0,
                        id='exam_crawl', replace_existing=True)
    _scheduler.start()

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/<page>')
def serve_page(page):
    """클린 URL(/login, /register, /dashboard 등)로 static의 html 페이지 제공"""
    filename = page if page.endswith('.html') else f'{page}.html'
    full = os.path.join(STATIC_DIR, filename)
    if os.path.isfile(full):
        return send_from_directory(STATIC_DIR, filename)
    return jsonify({'error': 'Not Found', 'code': 'NOT_FOUND'}), 404

if __name__ == '__main__':
    # allow_unsafe_werkzeug: 이 프로젝트는 기존에도 app.run(debug=True)로 개발 서버를
    # 직접 구동했으므로 배포 안전성 수준은 동일하다(운영 배포 시에는 gunicorn+eventlet 등으로 교체 필요).
    # PORT 환경변수로 포트 변경 가능(기본 5000) — 여러 인스턴스를 나란히 띄울 때 사용.
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '5000')),
                 debug=True, allow_unsafe_werkzeug=True)
    