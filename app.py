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
from routes.clan         import clan_bp
from routes.upload       import upload_bp
from routes.mission      import mission_bp
from routes.crawl        import crawl_bp
from routes.admin        import admin_bp
from routes.ocr          import ocr_bp
from routes.ai           import ai_bp
from routes.achievement  import achievement_bp
from routes.roadmap      import roadmap_bp
from routes.wrongnote    import wrongnote_bp
import routes.wiki_sync      # noqa: F401 — 위키 실시간 협업 SocketIO 핸들러 등록
import sockets.chat_events   # noqa: F401 — 채팅 SocketIO 핸들러 등록
sockets.chat_events.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(post_bp)
app.register_blueprint(comment_bp)
app.register_blueprint(wiki_bp)
app.register_blueprint(study_bp)
app.register_blueprint(notification_bp)
app.register_blueprint(clan_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(mission_bp)
app.register_blueprint(crawl_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(ocr_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(achievement_bp)
app.register_blueprint(roadmap_bp)
app.register_blueprint(wrongnote_bp)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

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
    socketio.run(app, host='0.0.0.0', debug=True, allow_unsafe_werkzeug=True)
