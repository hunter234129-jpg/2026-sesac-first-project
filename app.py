from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
import os
from config import MAX_UPLOAD_BYTES

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES
CORS(app)

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
    app.run(host='0.0.0.0', debug=True)
