from flask import Flask, redirect, url_for, render_template, send_from_directory, request, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import urllib.parse
import argparse
import psutil
import socket
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
socketio = SocketIO(app, cors_allowed_origins="*")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# 获取本地IP地址
def get_local_ip(family):
    for interface, snics in psutil.net_if_addrs().items():
        for snic in snics:
            if snic.family == family and interface in ['以太网', 'en0']:
                return snic.address


# 支持的文件类型映射到图标
ICON_MAP = {
    'pdf': 'fa-file-pdf',
    'doc': 'fa-file-word',
    'docx': 'fa-file-word',
    'xls': 'fa-file-excel',
    'xlsx': 'fa-file-excel',
    'ppt': 'fa-file-powerpoint',
    'pptx': 'fa-file-powerpoint',
    'zip': 'fa-file-archive',
    'rar': 'fa-file-archive',
    '7z': 'fa-file-archive',
    'txt': 'fa-file-alt',
    'jpg': 'fa-file-image',
    'jpeg': 'fa-file-image',
    'png': 'fa-file-image',
    'gif': 'fa-file-image',
    'bmp': 'fa-file-image',
    'svg': 'fa-file-image',
    'mp4': 'fa-file-video',
    'avi': 'fa-file-video',
    'mov': 'fa-file-video',
    'mkv': 'fa-file-video',
    'mp3': 'fa-file-audio',
    'wav': 'fa-file-audio',
    'ogg': 'fa-file-audio',
}


def convert_size(size_in_bytes):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0

    # 循环转换单位
    while size_in_bytes >= 1024 and index < len(units) - 1:
        size_in_bytes /= 1024
        index += 1

    # 返回格式化结果
    return f"{size_in_bytes:.2f} {units[index]}"


def get_icon(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ICON_MAP.get(ext, 'fa-file')


def get_file_list():
    files = []
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], f)
        if os.path.isfile(path):
            stat = os.stat(path)
            files.append({
                'name': f,
                'size': convert_size(stat.st_size),
                'mtime': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'url': f'/download/{urllib.parse.quote(f)}',
                'icon': get_icon(f),
                'timestamp': stat.st_mtime
            })
    files.sort(key=lambda e: e['timestamp'], reverse=True)
    return files


@app.route('/')
def index():
    files = get_file_list()
    ip = get_local_ip(socket.AF_INET)
    port = 5000
    server_url = f"http://{ip}:{port}"
    return render_template('index.html', files=files, server_url=server_url)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = file.filename
        safe_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        counter = 1
        while os.path.exists(safe_path):
            name, ext = os.path.splitext(filename)
            safe_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{name}_{counter}{ext}")
            counter += 1
            filename = f"{name}_{counter}{ext}"
        file.save(safe_path)
        # 通知所有客户端文件已更新
        socketio.emit('file_updated')
        return jsonify({'message': 'Upload successful', 'filename': filename}), 200


@app.route('/download/<path:filename>')
def download(filename):
    decoded_filename = urllib.parse.unquote(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], decoded_filename, as_attachment=True)


@app.route('/clear', methods=['POST'])
def clear_files():
    for f in os.listdir(UPLOAD_FOLDER):
        os.remove(os.path.join(UPLOAD_FOLDER, f))
    # 通知所有客户端文件已更新
    socketio.emit('file_updated')
    return redirect(url_for('index'))


@app.route('/api/files')
def get_files_api():
    files = get_file_list()
    return jsonify({'files': files})


# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    # 生成唯一客户端ID
    client_id = request.sid
    emit('connection_response', {'message': 'Connected to server', 'client_id': client_id})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('send_message')
def handle_send_message(data):
    message = data.get('message', '')
    client_id = data.get('client_id', '')
    if message:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 广播消息给所有客户端
        emit('new_message', {
            'message': message,
            'timestamp': timestamp,
            'client_id': client_id
        }, broadcast=True)


if __name__ == '__main__':
    # 局域网IP
    local_ip = get_local_ip(socket.AF_INET)
    print(f"🚀 服务启动成功！")
    print(f"🌐 访问地址: http://{local_ip}:5000")
    print(f"📱 在浏览器中打开上述地址，或使用手机扫描页面上的二维码")
    app.run(host='0.0.0.0', port=5000, debug=False)
