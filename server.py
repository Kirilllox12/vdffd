from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import sqlite3
import hashlib
import secrets
import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

@app.route('/')
def index():
    return jsonify({'status': 'Vox Server Running', 'version': '1.0'})

DB_FILE = 'vox_database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        status TEXT DEFAULT 'active',
        role TEXT DEFAULT 'user',
        verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP,
        avatar TEXT,
        bio TEXT
    )''')
    
    # Таблица сессий
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        token TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Таблица чатов
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT DEFAULT 'private',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        avatar TEXT
    )''')
    
    # Таблица участников чатов
    c.execute('''CREATE TABLE IF NOT EXISTS chat_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        role TEXT DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chat_id) REFERENCES chats(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Таблица сообщений
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        content TEXT,
        type TEXT DEFAULT 'text',
        file_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        edited INTEGER DEFAULT 0,
        FOREIGN KEY (chat_id) REFERENCES chats(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Таблица блокировок
    c.execute('''CREATE TABLE IF NOT EXISTS bans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reason TEXT,
        banned_by INTEGER,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (banned_by) REFERENCES users(id)
    )''')
    
    # Таблица обращений в поддержку
    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Таблица ботов
    c.execute('''CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        token TEXT UNIQUE,
        owner_id INTEGER,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_id) REFERENCES users(id)
    )''')
    
    # Таблица премиум подписок
    c.execute('''CREATE TABLE IF NOT EXISTS premium (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_creator_user():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", ('maloy',))
    if not c.fetchone():
        password_hash = hash_password('admin123')
        c.execute("""INSERT INTO users (username, password_hash, role, verified) 
                     VALUES (?, ?, ?, ?)""", ('maloy', password_hash, 'creator', 1))
        conn.commit()
    conn.close()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if len(username) < 4:
        return jsonify({'success': False, 'error': 'Юзернейм должен быть минимум 4 символа'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль должен быть минимум 6 символов'}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Юзернейм уже занят'}), 400
    
    password_hash = hash_password(password)
    c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
    user_id = c.lastrowid
    
    token = secrets.token_hex(32)
    c.execute("INSERT INTO sessions (user_id, token) VALUES (?, ?)", (user_id, token))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'token': token, 'username': username, 'user_id': user_id})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    password_hash = hash_password(password)
    c.execute("SELECT id, username, role, verified, status FROM users WHERE username = ? AND password_hash = ?", 
              (username, password_hash))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
    
    user_id, username, role, verified, status = user
    
    if status == 'banned':
        c.execute("SELECT reason FROM bans WHERE user_id = ? ORDER BY banned_at DESC LIMIT 1", (user_id,))
        ban = c.fetchone()
        reason = ban[0] if ban else 'Нарушение правил'
        conn.close()
        return jsonify({'success': False, 'error': 'banned', 'reason': reason}), 403
    
    token = secrets.token_hex(32)
    c.execute("INSERT INTO sessions (user_id, token) VALUES (?, ?)", (user_id, token))
    c.execute("UPDATE users SET last_seen = ? WHERE id = ?", (datetime.datetime.now(), user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'token': token, 
        'username': username, 
        'user_id': user_id,
        'role': role,
        'verified': verified
    })

@app.route('/api/auto_login', methods=['POST'])
def auto_login():
    data = request.json
    token = data.get('token', '')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""SELECT u.id, u.username, u.role, u.verified, u.status 
                 FROM sessions s JOIN users u ON s.user_id = u.id 
                 WHERE s.token = ?""", (token,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Неверный токен'}), 401
    
    user_id, username, role, verified, status = user
    
    if status == 'banned':
        c.execute("SELECT reason FROM bans WHERE user_id = ? ORDER BY banned_at DESC LIMIT 1", (user_id,))
        ban = c.fetchone()
        reason = ban[0] if ban else 'Нарушение правил'
        conn.close()
        return jsonify({'success': False, 'error': 'banned', 'reason': reason}), 403
    
    c.execute("UPDATE users SET last_seen = ? WHERE id = ?", (datetime.datetime.now(), user_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'username': username,
        'user_id': user_id,
        'role': role,
        'verified': verified
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json
    token = data.get('token', '')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/support/create', methods=['POST'])
def create_support_ticket():
    data = request.json
    token = data.get('token', '')
    subject = data.get('subject', '')
    message = data.get('message', '')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
    session = c.fetchone()
    if not session:
        conn.close()
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    user_id = session[0]
    c.execute("INSERT INTO support_tickets (user_id, subject, message) VALUES (?, ?, ?)",
              (user_id, subject, message))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Обращение отправлено'})

@app.route('/api/chats', methods=['GET'])
def get_chats():
    token = request.args.get('token', '')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
    session = c.fetchone()
    if not session:
        conn.close()
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    user_id = session[0]
    
    c.execute("""SELECT c.id, c.name, c.type, c.avatar 
                 FROM chats c 
                 JOIN chat_members cm ON c.id = cm.chat_id 
                 WHERE cm.user_id = ?""", (user_id,))
    chats = c.fetchall()
    
    conn.close()
    
    chats_list = [{'id': ch[0], 'name': ch[1], 'type': ch[2], 'avatar': ch[3]} for ch in chats]
    return jsonify({'success': True, 'chats': chats_list})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('join')
def handle_join(data):
    room = data['chat_id']
    join_room(room)
    emit('status', {'msg': 'Joined chat'}, room=room)

@socketio.on('message')
def handle_message(data):
    chat_id = data['chat_id']
    user_id = data['user_id']
    content = data['content']
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (chat_id, user_id, content) VALUES (?, ?, ?)",
              (chat_id, user_id, content))
    message_id = c.lastrowid
    conn.commit()
    conn.close()
    
    emit('new_message', {
        'id': message_id,
        'chat_id': chat_id,
        'user_id': user_id,
        'content': content,
        'timestamp': datetime.datetime.now().isoformat()
    }, room=chat_id)

if __name__ == '__main__':
    init_db()
    create_creator_user()
    port = int(os.environ.get('PORT', 5000))
    print(f"Сервер Vox запущен на порту {port}")
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
