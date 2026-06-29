import os
import uuid
from flask import Blueprint, jsonify, request, g, send_from_directory
from werkzeug.utils import secure_filename
from db.connection import get_db
from utils.auth import login_required
from config import UPLOAD_DIR, MAX_UPLOAD_BYTES, ALLOWED_EXTENSIONS

upload_bp = Blueprint('upload', __name__)

os.makedirs(UPLOAD_DIR, exist_ok=True)


def ok(data, msg='ok'):
    return jsonify({'data': data, 'message': msg})

def err(msg, code, status=400):
    return jsonify({'error': msg, 'code': code}), status


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return err('file 필드가 필요합니다', 'NO_FILE')

    file = request.files['file']
    if not file or file.filename == '':
        return err('선택된 파일이 없습니다', 'NO_FILE')
    if not allowed_file(file.filename):
        return err('허용되지 않는 파일 형식입니다', 'INVALID_EXTENSION')

    # 용량 체크
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_UPLOAD_BYTES:
        return err('파일이 너무 큽니다 (최대 10MB)', 'TOO_LARGE', 413)

    original = secure_filename(file.filename)
    ext      = original.rsplit('.', 1)[1].lower()
    stored   = f'{uuid.uuid4().hex}.{ext}'
    file.save(os.path.join(UPLOAD_DIR, stored))

    ref_type = request.form.get('ref_type')
    ref_id   = request.form.get('ref_id', type=int)

    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''INSERT INTO files
               (user_id, original, stored_name, mime_type, ref_type, ref_id)
               VALUES (%s, %s, %s, %s, %s, %s)''',
            (g.user_id, original, stored, file.mimetype, ref_type, ref_id)
        )
        conn.commit()
        file_id = cursor.lastrowid
    finally:
        conn.close()

    return ok({
        'id':       file_id,
        'original': original,
        'url':      f'/api/files/{stored}'
    }, '업로드 완료'), 201


@upload_bp.route('/api/files/<stored>', methods=['GET'])
def serve_file(stored):
    stored = secure_filename(stored)
    if not os.path.exists(os.path.join(UPLOAD_DIR, stored)):
        return err('파일을 찾을 수 없습니다', 'NOT_FOUND', 404)
    return send_from_directory(UPLOAD_DIR, stored)


@upload_bp.route('/api/files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    conn   = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT user_id, stored_name FROM files WHERE id = %s',
            (file_id,)
        )
        f = cursor.fetchone()
        if not f:
            return err('파일을 찾을 수 없습니다', 'NOT_FOUND', 404)
        if f['user_id'] != g.user_id and not g.is_admin:
            return err('본인 파일만 삭제할 수 있습니다', 'FORBIDDEN', 403)

        cursor.execute('DELETE FROM files WHERE id = %s', (file_id,))
        conn.commit()
    finally:
        conn.close()

    path = os.path.join(UPLOAD_DIR, f['stored_name'])
    if os.path.exists(path):
        os.remove(path)

    return ok({}, '삭제 완료')
