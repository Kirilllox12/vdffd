import asyncio
import websockets
import json
import sqlite3
import os
import uuid
from datetime import datetime

# Database path
db_path = '/tmp/velora_v2.db'

def get_db():
    return sqlite3.connect(db_path)

def init_db():
    db = get_db()
    c = db.cursor()
    
    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        display_name TEXT,
        bio TEXT DEFAULT '',
        avatar_color TEXT DEFAULT '#a855f7',
        avatar_data TEXT DEFAULT '',
        crystals INTEGER DEFAULT 100,
        premium INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        is_frozen INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        is_deleted INTEGER DEFAULT 0,
        delete_reason TEXT DEFAULT '',
        nft_uses INTEGER DEFAULT 0,
        session_token TEXT DEFAULT '',
        created_at TEXT
    )''')
    
    # Private messages
    c.execute('''CREATE TABLE IF NOT EXISTS private_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user TEXT,
        to_user TEXT,
        text TEXT,
        time TEXT
    )''')
    
    # Private chats
    c.execute('''CREATE TABLE IF NOT EXISTS private_chats (
        user1 TEXT,
        user2 TEXT,
        last_message TEXT,
        last_time TEXT,
        PRIMARY KEY (user1, user2)
    )''')

    # Support messages
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        from_user TEXT,
        email TEXT DEFAULT '',
        text TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    # User aliases (NFT Uses)
    c.execute('''CREATE TABLE IF NOT EXISTS user_aliases (
        alias TEXT PRIMARY KEY,
        owner TEXT NOT NULL,
        created_at TEXT
    )''')
    
    # Gifts
    c.execute('''CREATE TABLE IF NOT EXISTS gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        to_user TEXT,
        from_user TEXT,
        gift_id TEXT,
        created_at TEXT
    )''')
    
    # Premium requests
    c.execute('''CREATE TABLE IF NOT EXISTS premium_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )''')
    
    # Chats (groups/channels)
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        chat_type TEXT DEFAULT 'group',
        owner TEXT NOT NULL,
        avatar_color TEXT DEFAULT '#a855f7',
        avatar_data TEXT DEFAULT '',
        link TEXT UNIQUE,
        is_public INTEGER DEFAULT 0,
        created_at TEXT
    )''')
    
    # Chat members
    c.execute('''CREATE TABLE IF NOT EXISTS chat_members (
        chat_id TEXT,
        username TEXT,
        role TEXT DEFAULT 'member',
        joined_at TEXT,
        PRIMARY KEY (chat_id, username)
    )''')
    
    # Chat messages
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        from_user TEXT,
        text TEXT,
        media_type TEXT DEFAULT '',
        media_data TEXT DEFAULT '',
        reply_to INTEGER DEFAULT NULL,
        forward_from TEXT DEFAULT '',
        time TEXT
    )''')
    
    # Reactions
    c.execute('''CREATE TABLE IF NOT EXISTS reactions (
        message_id INTEGER,
        username TEXT,
        emoji TEXT,
        is_private INTEGER DEFAULT 0,
        PRIMARY KEY (message_id, username, is_private)
    )''')
    
    db.commit()
    db.close()

init_db()
clients = {}
ADMINS = ['cold', 'maloy']

async def send_to_user(username, data):
    for ws, user in clients.items():
        if user and user.get('username') == username:
            try:
                await ws.send(json.dumps(data, ensure_ascii=False))
            except:
                pass

async def send_private_chats(ws, username):
    db = get_db()
    c = db.cursor()
    c.execute('SELECT user2, last_message, last_time FROM private_chats WHERE user1=? ORDER BY last_time DESC', (username,))
    chats = [{'username': r[0], 'last_message': r[1], 'last_time': r[2]} for r in c.fetchall()]
    db.close()
    await ws.send(json.dumps({'type': 'private_chats', 'chats': chats}, ensure_ascii=False))

async def send_my_chats(ws, username):
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT c.id, c.name, c.description, c.chat_type, c.owner, c.avatar_color, c.avatar_data, c.link, c.is_public
                 FROM chats c JOIN chat_members m ON c.id = m.chat_id WHERE m.username=?''', (username,))
    chats = [{'id': r[0], 'name': r[1], 'description': r[2], 'type': r[3], 'owner': r[4], 
              'avatar_color': r[5], 'avatar_data': r[6], 'link': r[7], 'is_public': r[8]} for r in c.fetchall()]
    db.close()
    await ws.send(json.dumps({'type': 'my_chats', 'chats': chats}, ensure_ascii=False))


async def handle_client(websocket):
    print("Client connected")
    clients[websocket] = None
    try:
        async for message in websocket:
            try:
                msg = json.loads(message.strip())
                await process_message(msg, websocket)
            except Exception as e:
                print(f"Error: {e}")
    except:
        pass
    finally:
        if websocket in clients:
            del clients[websocket]
        print("Client disconnected")

async def process_message(msg, ws):
    t = msg.get('type')
    
    # ===== REGISTER =====
    if t == 'register':
        username = msg.get('username', '').lower().strip()
        password = msg.get('password', '')
        display_name = msg.get('display_name', username)
        avatar_color = msg.get('avatar_color', '#a855f7')
        
        if not username or len(username) < 3:
            await ws.send(json.dumps({'type': 'register_response', 'success': False, 'error': 'Минимум 3 символа'}))
            return
        if not password or len(password) < 4:
            await ws.send(json.dumps({'type': 'register_response', 'success': False, 'error': 'Пароль минимум 4 символа'}))
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT 1 FROM users WHERE username=?', (username,))
        if c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'register_response', 'success': False, 'error': 'Имя занято'}))
            return
        
        now = datetime.now().isoformat()
        c.execute('INSERT INTO users (username, password, display_name, avatar_color, created_at) VALUES (?,?,?,?,?)',
                  (username, password, display_name, avatar_color, now))
        db.commit()
        db.close()
        
        user = {'username': username, 'display_name': display_name, 'crystals': 100, 'premium': 0, 'avatar_color': avatar_color}
        clients[ws] = user
        await ws.send(json.dumps({'type': 'register_response', 'success': True, 'user': user}, ensure_ascii=False))
        await send_private_chats(ws, username)
        await send_my_chats(ws, username)

    # ===== LOGIN =====
    elif t == 'login':
        username = msg.get('username', '').lower().strip()
        password = msg.get('password', '')
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT username, display_name, crystals, premium, avatar_color, bio, is_deleted, delete_reason, is_banned FROM users WHERE username=? AND password=?', 
                  (username, password))
        row = c.fetchone()
        db.close()
        
        if not row:
            await ws.send(json.dumps({'type': 'login_response', 'success': False, 'error': 'Неверные данные'}))
            return
        if row[6]:
            await ws.send(json.dumps({'type': 'login_response', 'success': False, 'error': f'Аккаунт удалён: {row[7] or "Нарушение правил"}'}))
            return
        if row[8]:
            await ws.send(json.dumps({'type': 'login_response', 'success': False, 'error': 'Аккаунт заблокирован'}))
            return
        
        user = {'username': row[0], 'display_name': row[1], 'crystals': row[2], 'premium': row[3], 'avatar_color': row[4], 'bio': row[5] or ''}
        clients[ws] = user
        await ws.send(json.dumps({'type': 'login_response', 'success': True, 'user': user}, ensure_ascii=False))
        await send_private_chats(ws, username)
        await send_my_chats(ws, username)

    # ===== AUTO LOGIN =====
    elif t == 'auto_login':
        token = msg.get('token', '')
        username = msg.get('username', '').lower()
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT username, display_name, crystals, premium, avatar_color, bio, session_token, is_deleted, is_banned FROM users WHERE username=?', (username,))
        row = c.fetchone()
        db.close()
        
        if not row or row[6] != token:
            await ws.send(json.dumps({'type': 'auto_login_response', 'success': False}))
            return
        if row[7] or row[8]:
            await ws.send(json.dumps({'type': 'auto_login_response', 'success': False, 'error': 'Аккаунт заблокирован'}))
            return
        
        user = {'username': row[0], 'display_name': row[1], 'crystals': row[2], 'premium': row[3], 'avatar_color': row[4], 'bio': row[5] or ''}
        clients[ws] = user
        await ws.send(json.dumps({'type': 'auto_login_response', 'success': True, 'user': user}, ensure_ascii=False))
        await send_private_chats(ws, username)
        await send_my_chats(ws, username)


    # ===== CREATE CHAT (GROUP/CHANNEL) =====
    elif t == 'create_chat':
        if not clients.get(ws):
            return
        user = clients[ws]
        
        chat_type = msg.get('chat_type', 'group')
        name = msg.get('name', '').strip()
        description = msg.get('description', '')
        avatar_color = msg.get('avatar_color', '#a855f7')
        avatar_data = msg.get('avatar_data', '')
        is_public = msg.get('is_public', 0)
        
        if not name:
            await ws.send(json.dumps({'type': 'error', 'error': 'Введите название'}))
            return
        
        chat_id = str(uuid.uuid4())[:8]
        link = f"velora_{chat_id}"
        now = datetime.now().isoformat()
        
        db = get_db()
        c = db.cursor()
        c.execute('''INSERT INTO chats (id, name, description, chat_type, owner, avatar_color, avatar_data, link, is_public, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)''',
                  (chat_id, name, description, chat_type, user['username'], avatar_color, avatar_data, link, is_public, now))
        c.execute('INSERT INTO chat_members (chat_id, username, role, joined_at) VALUES (?,?,?,?)',
                  (chat_id, user['username'], 'owner', now))
        db.commit()
        db.close()
        
        chat = {'id': chat_id, 'name': name, 'description': description, 'type': chat_type, 
                'owner': user['username'], 'avatar_color': avatar_color, 'avatar_data': avatar_data, 
                'link': link, 'is_public': is_public}
        await ws.send(json.dumps({'type': 'chat_created', 'chat': chat}, ensure_ascii=False))

    # ===== JOIN CHAT =====
    elif t == 'join_chat':
        if not clients.get(ws):
            return
        user = clients[ws]
        link = msg.get('link', '').strip()
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT id, name, description, chat_type, owner, avatar_color, avatar_data, link, is_public FROM chats WHERE link=?', (link,))
        row = c.fetchone()
        
        if not row:
            db.close()
            await ws.send(json.dumps({'type': 'join_response', 'success': False, 'error': 'Чат не найден'}))
            return
        
        chat = {'id': row[0], 'name': row[1], 'description': row[2], 'type': row[3], 'owner': row[4],
                'avatar_color': row[5], 'avatar_data': row[6], 'link': row[7], 'is_public': row[8]}
        
        c.execute('SELECT 1 FROM chat_members WHERE chat_id=? AND username=?', (chat['id'], user['username']))
        already = c.fetchone() is not None
        
        if not already:
            now = datetime.now().isoformat()
            c.execute('INSERT INTO chat_members (chat_id, username, role, joined_at) VALUES (?,?,?,?)',
                      (chat['id'], user['username'], 'member', now))
            db.commit()
        db.close()
        
        await ws.send(json.dumps({'type': 'join_response', 'success': True, 'chat': chat, 'already': already}, ensure_ascii=False))

    # ===== LEAVE CHAT =====
    elif t == 'leave_chat':
        if not clients.get(ws):
            return
        user = clients[ws]
        chat_id = msg.get('chat_id', '')
        
        db = get_db()
        c = db.cursor()
        c.execute('DELETE FROM chat_members WHERE chat_id=? AND username=?', (chat_id, user['username']))
        db.commit()
        db.close()
        
        await ws.send(json.dumps({'type': 'left_chat', 'chat_id': chat_id}))

    # ===== CHAT MESSAGE =====
    elif t == 'chat_message':
        if not clients.get(ws):
            return
        user = clients[ws]
        chat_id = msg.get('chat_id', '')
        text = msg.get('text', '')
        media_type = msg.get('media_type', '')
        media_data = msg.get('media_data', '')
        reply_to = msg.get('reply_to')
        forward_from = msg.get('forward_from', '')
        
        if not chat_id or (not text and not media_data):
            return
        
        now = datetime.now().isoformat()
        
        db = get_db()
        c = db.cursor()
        c.execute('''INSERT INTO chat_messages (chat_id, from_user, text, media_type, media_data, reply_to, forward_from, time)
                     VALUES (?,?,?,?,?,?,?,?)''',
                  (chat_id, user['username'], text, media_type, media_data, reply_to, forward_from, now))
        msg_id = c.lastrowid
        
        c.execute('SELECT username FROM chat_members WHERE chat_id=?', (chat_id,))
        members = [r[0] for r in c.fetchall()]
        db.close()
        
        chat_msg = {'type': 'chat_message', 'id': msg_id, 'chat_id': chat_id, 'from': user['username'],
                    'text': text, 'media_type': media_type, 'media_data': media_data,
                    'reply_to': reply_to, 'forward_from': forward_from, 'time': now,
                    'avatar_color': user.get('avatar_color', '#a855f7')}
        
        for member in members:
            await send_to_user(member, chat_msg)

    # ===== GET CHAT HISTORY =====
    elif t == 'get_chat_history':
        if not clients.get(ws):
            return
        chat_id = msg.get('chat_id', '')
        
        db = get_db()
        c = db.cursor()
        c.execute('''SELECT m.id, m.from_user, m.text, m.media_type, m.media_data, m.reply_to, m.forward_from, m.time, u.avatar_color
                     FROM chat_messages m LEFT JOIN users u ON m.from_user = u.username
                     WHERE m.chat_id=? ORDER BY m.id DESC LIMIT 100''', (chat_id,))
        messages = []
        for r in c.fetchall():
            msg_data = {'id': r[0], 'from': r[1], 'text': r[2], 'media_type': r[3], 'media_data': r[4],
                       'reply_to': r[5], 'forward_from': r[6], 'time': r[7], 'avatar_color': r[8] or '#a855f7'}
            c.execute('SELECT username, emoji FROM reactions WHERE message_id=? AND is_private=0', (r[0],))
            reactions = {}
            for rr in c.fetchall():
                if rr[1] not in reactions:
                    reactions[rr[1]] = []
                reactions[rr[1]].append(rr[0])
            msg_data['reactions'] = reactions
            messages.append(msg_data)
        db.close()
        
        messages.reverse()
        await ws.send(json.dumps({'type': 'chat_history', 'chat_id': chat_id, 'messages': messages}, ensure_ascii=False))


    # ===== PRIVATE MESSAGE =====
    elif t == 'private_message':
        if not clients.get(ws):
            return
        user = clients[ws]
        to_user = msg.get('to', '').lower()
        text = msg.get('text', '')
        
        if not text or not to_user:
            return
        
        now = datetime.now().isoformat()
        
        # Handle HELPER messages
        if to_user == 'helper':
            db = get_db()
            c = db.cursor()
            c.execute('INSERT INTO support_messages (ticket_id, from_user, email, text, is_admin, created_at) VALUES (?,?,?,?,0,?)',
                      (user['username'], user['username'], '', text, now))
            db.commit()
            db.close()
            for admin in ADMINS:
                await send_to_user(admin, {'type': 'support_message_received', 'ticket_id': user['username']})
            await ws.send(json.dumps({'type': 'support_sent', 'success': True}))
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT 1 FROM users WHERE username=?', (to_user,))
        if not c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'error', 'error': 'Пользователь не найден'}))
            return
        
        c.execute('INSERT INTO private_messages (from_user, to_user, text, time) VALUES (?,?,?,?)',
                  (user['username'], to_user, text, now))
        msg_id = c.lastrowid
        
        c.execute('INSERT OR REPLACE INTO private_chats (user1, user2, last_message, last_time) VALUES (?,?,?,?)',
                  (user['username'], to_user, text[:50], now))
        c.execute('INSERT OR REPLACE INTO private_chats (user1, user2, last_message, last_time) VALUES (?,?,?,?)',
                  (to_user, user['username'], text[:50], now))
        db.commit()
        db.close()
        
        pm = {'type': 'private_message', 'id': msg_id, 'from': user['username'], 'to': to_user, 'text': text, 'time': now}
        await ws.send(json.dumps(pm, ensure_ascii=False))
        await send_to_user(to_user, pm)
        
        for client_ws, client_user in clients.items():
            if client_user and client_user.get('username') == to_user:
                await send_private_chats(client_ws, to_user)

    # ===== GET PRIVATE HISTORY =====
    elif t == 'get_private_history':
        if not clients.get(ws):
            return
        user = clients[ws]
        with_user = msg.get('with', '').lower()
        
        db = get_db()
        c = db.cursor()
        c.execute('''SELECT id, from_user, to_user, text, time FROM private_messages 
                     WHERE (from_user=? AND to_user=?) OR (from_user=? AND to_user=?)
                     ORDER BY id DESC LIMIT 100''',
                  (user['username'], with_user, with_user, user['username']))
        messages = [{'id': r[0], 'from': r[1], 'to': r[2], 'text': r[3], 'time': r[4]} for r in c.fetchall()]
        db.close()
        
        messages.reverse()
        await ws.send(json.dumps({'type': 'private_history', 'with': with_user, 'messages': messages}, ensure_ascii=False))

    # ===== ADD REACTION =====
    elif t == 'add_reaction':
        if not clients.get(ws):
            return
        user = clients[ws]
        message_id = msg.get('message_id')
        chat_id = msg.get('chat_id', '')
        emoji = msg.get('emoji', '')
        is_private = 1 if msg.get('is_private') else 0
        
        if not message_id or not emoji:
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('DELETE FROM reactions WHERE message_id=? AND username=? AND is_private=?', (message_id, user['username'], is_private))
        c.execute('INSERT INTO reactions (message_id, username, emoji, is_private) VALUES (?,?,?,?)',
                  (message_id, user['username'], emoji, is_private))
        db.commit()
        db.close()
        
        reaction_msg = {'type': 'reaction_added', 'message_id': message_id, 'emoji': emoji, 'username': user['username']}
        
        if is_private:
            await ws.send(json.dumps(reaction_msg))
            await send_to_user(chat_id, reaction_msg)
        else:
            db = get_db()
            c = db.cursor()
            c.execute('SELECT username FROM chat_members WHERE chat_id=?', (chat_id,))
            members = [r[0] for r in c.fetchall()]
            db.close()
            for member in members:
                await send_to_user(member, reaction_msg)

    # ===== DELETE MESSAGE =====
    elif t == 'delete_message':
        if not clients.get(ws):
            return
        user = clients[ws]
        message_id = msg.get('message_id')
        chat_id = msg.get('chat_id', '')
        is_private = msg.get('is_private', False)
        
        if not message_id:
            return
        
        db = get_db()
        c = db.cursor()
        if is_private:
            c.execute('UPDATE private_messages SET text="[Удалено]" WHERE id=? AND from_user=?', (message_id, user['username']))
        else:
            c.execute('UPDATE chat_messages SET text="[Удалено]" WHERE id=? AND from_user=?', (message_id, user['username']))
        db.commit()
        db.close()
        
        delete_msg = {'type': 'message_deleted', 'message_id': message_id, 'chat_id': chat_id}
        if is_private:
            await ws.send(json.dumps(delete_msg))
            await send_to_user(chat_id, delete_msg)
        else:
            db = get_db()
            c = db.cursor()
            c.execute('SELECT username FROM chat_members WHERE chat_id=?', (chat_id,))
            members = [r[0] for r in c.fetchall()]
            db.close()
            for member in members:
                await send_to_user(member, delete_msg)


    # ===== SEARCH =====
    elif t == 'search':
        query = msg.get('query', '').lower().strip().replace('@', '')
        results = {'users': [], 'chats': []}
        
        if query == 'helper':
            results['users'].append({
                'username': 'HELPER', 'display_name': 'Поддержка Velora',
                'bio': 'Официальная поддержка', 'avatar_color': '#22c55e',
                'is_verified': True, 'is_support': True
            })
            await ws.send(json.dumps({'type': 'search_results', 'results': results}, ensure_ascii=False))
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT username, display_name, bio, avatar_color, premium, is_verified, is_deleted FROM users WHERE username LIKE ? LIMIT 20', (f'%{query}%',))
        for row in c.fetchall():
            if not row[6]:
                results['users'].append({
                    'username': row[0], 'display_name': row[1], 'bio': row[2] or '',
                    'avatar_color': row[3], 'premium': row[4], 'is_verified': row[5]
                })
        
        c.execute('SELECT owner FROM user_aliases WHERE alias LIKE ?', (f'%{query}%',))
        for row in c.fetchall():
            owner = row[0]
            if not any(u['username'] == owner for u in results['users']):
                c.execute('SELECT username, display_name, bio, avatar_color, premium, is_verified FROM users WHERE username=?', (owner,))
                urow = c.fetchone()
                if urow:
                    results['users'].append({
                        'username': urow[0], 'display_name': urow[1], 'bio': urow[2] or '',
                        'avatar_color': urow[3], 'premium': urow[4], 'is_verified': urow[5]
                    })
        db.close()
        
        await ws.send(json.dumps({'type': 'search_results', 'results': results}, ensure_ascii=False))

    # ===== GET USER PROFILE =====
    elif t == 'get_user_profile':
        username = msg.get('username', '').lower()
        
        if username == 'helper':
            await ws.send(json.dumps({'type': 'user_profile', 'user': {
                'username': 'HELPER', 'display_name': 'Поддержка Velora',
                'bio': 'Официальная поддержка', 'avatar_color': '#22c55e',
                'is_verified': True, 'is_support': True
            }}, ensure_ascii=False))
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT username, display_name, bio, avatar_color, crystals, premium, is_verified, nft_uses FROM users WHERE username=?', (username,))
        row = c.fetchone()
        
        aliases = []
        if row:
            c.execute('SELECT alias FROM user_aliases WHERE owner=?', (username,))
            aliases = [r[0] for r in c.fetchall()]
        db.close()
        
        if row:
            await ws.send(json.dumps({'type': 'user_profile', 'user': {
                'username': row[0], 'display_name': row[1], 'bio': row[2] or '',
                'avatar_color': row[3], 'crystals': row[4], 'premium': row[5],
                'is_verified': row[6], 'nft_uses': row[7], 'aliases': aliases
            }}, ensure_ascii=False))

    # ===== UPDATE PROFILE =====
    elif t == 'update_profile':
        if not clients.get(ws):
            return
        user = clients[ws]
        
        display_name = msg.get('display_name', user.get('display_name', ''))
        bio = msg.get('bio', '')
        avatar_color = msg.get('avatar_color', user.get('avatar_color', '#a855f7'))
        avatar_data = msg.get('avatar_data', '')
        
        db = get_db()
        c = db.cursor()
        c.execute('UPDATE users SET display_name=?, bio=?, avatar_color=?, avatar_data=? WHERE username=?',
                  (display_name, bio, avatar_color, avatar_data, user['username']))
        db.commit()
        db.close()
        
        user['display_name'] = display_name
        user['bio'] = bio
        user['avatar_color'] = avatar_color
        user['avatar_data'] = avatar_data
        clients[ws] = user
        
        await ws.send(json.dumps({'type': 'profile_updated', 'success': True, 'user': user}, ensure_ascii=False))


    # ===== SUPPORT MESSAGE =====
    elif t == 'support_message':
        text = msg.get('text', '')
        username = msg.get('username')
        email = msg.get('email', '')
        
        if not text:
            return
        
        now = datetime.now().isoformat()
        ticket_id = username or email or f'guest_{now}'
        
        db = get_db()
        c = db.cursor()
        c.execute('INSERT INTO support_messages (ticket_id, from_user, email, text, is_admin, created_at) VALUES (?,?,?,?,0,?)',
                  (ticket_id, username or 'Гость', email, text, now))
        db.commit()
        db.close()
        
        for admin in ADMINS:
            await send_to_user(admin, {'type': 'support_message_received', 'ticket_id': ticket_id})
        
        await ws.send(json.dumps({'type': 'support_sent', 'success': True}))

    # ===== GET MY SUPPORT MESSAGES =====
    elif t == 'get_my_support_messages':
        if not clients.get(ws):
            return
        user = clients[ws]
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT from_user, text, is_admin, created_at FROM support_messages WHERE ticket_id=? ORDER BY id', (user['username'],))
        messages = [{'from': r[0] if not r[2] else 'Поддержка', 'text': r[1], 'is_mine': not r[2], 'time': r[3]} for r in c.fetchall()]
        db.close()
        
        await ws.send(json.dumps({'type': 'support_messages', 'messages': messages}, ensure_ascii=False))

    # ===== GET SUPPORT TICKETS (ADMINS) =====
    elif t == 'get_support_tickets':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('''SELECT ticket_id, from_user, email, text, created_at FROM support_messages 
                    WHERE id IN (SELECT MAX(id) FROM support_messages GROUP BY ticket_id)
                    ORDER BY created_at DESC''')
        tickets = [{'id': r[0], 'username': r[1] if r[1] != 'Гость' else None, 'email': r[2], 
                   'last_message': r[3][:50] if r[3] else '', 'last_time': r[4]} for r in c.fetchall()]
        db.close()
        
        await ws.send(json.dumps({'type': 'support_tickets', 'tickets': tickets}, ensure_ascii=False))

    # ===== GET TICKET MESSAGES (ADMINS) =====
    elif t == 'get_ticket_messages':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        ticket_id = msg.get('ticket_id', '')
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT from_user, text, is_admin, created_at FROM support_messages WHERE ticket_id=? ORDER BY id', (ticket_id,))
        messages = [{'from': r[0], 'text': r[1], 'is_admin': r[2], 'time': r[3]} for r in c.fetchall()]
        db.close()
        
        await ws.send(json.dumps({'type': 'ticket_messages', 'messages': messages}, ensure_ascii=False))

    # ===== SUPPORT REPLY (ADMINS) =====
    elif t == 'support_reply':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        ticket_id = msg.get('ticket_id', '')
        text = msg.get('text', '')
        now = datetime.now().isoformat()
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT email FROM support_messages WHERE ticket_id=? LIMIT 1', (ticket_id,))
        row = c.fetchone()
        email = row[0] if row else ''
        
        c.execute('INSERT INTO support_messages (ticket_id, from_user, email, text, is_admin, created_at) VALUES (?,?,?,?,1,?)',
                  (ticket_id, user['username'], email, text, now))
        db.commit()
        db.close()
        
        await send_to_user(ticket_id, {'type': 'support_reply_received', 'from': 'Поддержка', 'text': text, 'time': now})
        await ws.send(json.dumps({'type': 'reply_sent', 'success': True}))


    # ===== ADMIN ACTION =====
    elif t == 'admin_action':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        action = msg.get('action', '')
        target = msg.get('target', '').lower()
        
        db = get_db()
        c = db.cursor()
        result = 'Выполнено'
        
        if action == 'freeze':
            c.execute('UPDATE users SET is_frozen=1 WHERE username=?', (target,))
            result = f'@{target} заморожен'
        elif action == 'unfreeze':
            c.execute('UPDATE users SET is_frozen=0 WHERE username=?', (target,))
            result = f'@{target} разморожен'
        elif action == 'ban':
            c.execute('UPDATE users SET is_banned=1 WHERE username=?', (target,))
            result = f'@{target} забанен'
        elif action == 'unban':
            c.execute('UPDATE users SET is_banned=0 WHERE username=?', (target,))
            result = f'@{target} разбанен'
        elif action == 'delete':
            reason = msg.get('reason', 'Нарушение правил')
            c.execute('UPDATE users SET is_deleted=1, delete_reason=? WHERE username=?', (reason, target))
            result = f'@{target} удалён'
        elif action == 'give_premium':
            c.execute('UPDATE users SET premium=1 WHERE username=?', (target,))
            result = f'@{target} получил Premium'
            await send_to_user(target, {'type': 'premium_activated'})
        elif action == 'remove_premium':
            c.execute('UPDATE users SET premium=0 WHERE username=?', (target,))
            result = f'@{target} лишён Premium'
        elif action == 'give_crystals':
            amount = msg.get('amount', 0)
            c.execute('UPDATE users SET crystals=crystals+? WHERE username=?', (amount, target))
            result = f'@{target} получил {amount} кристаллов'
            c.execute('SELECT crystals FROM users WHERE username=?', (target,))
            row = c.fetchone()
            if row:
                await send_to_user(target, {'type': 'crystals_update', 'crystals': row[0]})
        elif action == 'reset_crystals':
            c.execute('UPDATE users SET crystals=0 WHERE username=?', (target,))
            result = f'@{target} кристаллы обнулены'
            await send_to_user(target, {'type': 'crystals_update', 'crystals': 0})
        elif action == 'verify':
            c.execute('UPDATE users SET is_verified=1 WHERE username=?', (target,))
            result = f'@{target} верифицирован'
        elif action == 'unverify':
            c.execute('UPDATE users SET is_verified=0 WHERE username=?', (target,))
            result = f'@{target} снята верификация'
        elif action == 'change_name':
            new_name = msg.get('new_name', '')
            c.execute('UPDATE users SET display_name=? WHERE username=?', (new_name, target))
            result = f'@{target} имя изменено на {new_name}'
        elif action == 'change_username':
            new_username = msg.get('new_username', '').lower()
            c.execute('SELECT 1 FROM users WHERE username=?', (new_username,))
            if c.fetchone():
                result = f'@{new_username} уже занят'
            else:
                c.execute('UPDATE users SET username=? WHERE username=?', (new_username, target))
                c.execute('UPDATE private_messages SET from_user=? WHERE from_user=?', (new_username, target))
                c.execute('UPDATE private_messages SET to_user=? WHERE to_user=?', (new_username, target))
                result = f'@{target} -> @{new_username}'
        elif action == 'reset_avatar':
            c.execute('UPDATE users SET avatar_data="" WHERE username=?', (target,))
            result = f'@{target} аватар сброшен'
        elif action == 'push_update':
            update_url = msg.get('update_url', '')
            version = msg.get('version', '1.0.1')
            for client_ws in clients:
                try:
                    await client_ws.send(json.dumps({'type': 'update_available', 'url': update_url, 'version': version}))
                except:
                    pass
            result = f'Обновление {version} отправлено всем'
        
        db.commit()
        db.close()
        
        await ws.send(json.dumps({'type': 'admin_response', 'message': result}, ensure_ascii=False))


    # ===== ADMIN GIVE NFT =====
    elif t == 'admin_give_nft':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        target = msg.get('target', '').lower()
        aliases = msg.get('aliases', [])
        
        if not target or not aliases:
            await ws.send(json.dumps({'type': 'admin_response', 'message': 'Укажите пользователя и юзернеймы'}))
            return
        
        db = get_db()
        c = db.cursor()
        
        c.execute('SELECT 1 FROM users WHERE username=?', (target,))
        if not c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'admin_response', 'message': f'@{target} не найден'}))
            return
        
        now = datetime.now().isoformat()
        added = []
        for alias in aliases:
            alias = alias.lower().strip()
            if len(alias) < 3:
                continue
            c.execute('SELECT 1 FROM users WHERE username=?', (alias,))
            if c.fetchone():
                continue
            c.execute('SELECT 1 FROM user_aliases WHERE alias=?', (alias,))
            if c.fetchone():
                continue
            c.execute('INSERT INTO user_aliases (alias, owner, created_at) VALUES (?,?,?)', (alias, target, now))
            added.append(alias)
        
        c.execute('UPDATE users SET nft_uses=nft_uses+? WHERE username=?', (len(added), target))
        db.commit()
        db.close()
        
        if added:
            await ws.send(json.dumps({'type': 'admin_response', 'message': f'@{target} получил NFT Uses: @' + ', @'.join(added)}, ensure_ascii=False))
        else:
            await ws.send(json.dumps({'type': 'admin_response', 'message': 'Не удалось добавить юзернеймы'}))

    # ===== GET MY ALIASES =====
    elif t == 'get_my_aliases':
        if not clients.get(ws):
            return
        user = clients[ws]
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT alias, created_at FROM user_aliases WHERE owner=?', (user['username'],))
        aliases = [{'alias': r[0], 'created_at': r[1]} for r in c.fetchall()]
        c.execute('SELECT nft_uses FROM users WHERE username=?', (user['username'],))
        row = c.fetchone()
        nft_uses = row[0] if row else 0
        db.close()
        
        available = nft_uses - len(aliases)
        await ws.send(json.dumps({'type': 'my_aliases', 'aliases': aliases, 'nft_uses': nft_uses, 'available': max(0, available)}, ensure_ascii=False))

    # ===== ADD ALIAS =====
    elif t == 'add_alias':
        if not clients.get(ws):
            return
        user = clients[ws]
        alias = msg.get('alias', '').lower().strip()
        
        if len(alias) < 3:
            await ws.send(json.dumps({'type': 'alias_response', 'success': False, 'error': 'Минимум 3 символа'}))
            return
        
        db = get_db()
        c = db.cursor()
        
        c.execute('SELECT nft_uses FROM users WHERE username=?', (user['username'],))
        row = c.fetchone()
        nft_uses = row[0] if row else 0
        
        c.execute('SELECT COUNT(*) FROM user_aliases WHERE owner=?', (user['username'],))
        current_count = c.fetchone()[0]
        
        if current_count >= nft_uses:
            db.close()
            await ws.send(json.dumps({'type': 'alias_response', 'success': False, 'error': 'Нет доступных слотов NFT Uses'}))
            return
        
        c.execute('SELECT 1 FROM users WHERE username=?', (alias,))
        if c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'alias_response', 'success': False, 'error': f'@{alias} уже занят'}))
            return
        
        c.execute('SELECT 1 FROM user_aliases WHERE alias=?', (alias,))
        if c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'alias_response', 'success': False, 'error': f'@{alias} уже занят'}))
            return
        
        now = datetime.now().isoformat()
        c.execute('INSERT INTO user_aliases (alias, owner, created_at) VALUES (?,?,?)', (alias, user['username'], now))
        db.commit()
        db.close()
        
        await ws.send(json.dumps({'type': 'alias_response', 'success': True, 'message': f'@{alias} добавлен!'}))

    # ===== REMOVE ALIAS =====
    elif t == 'remove_alias':
        if not clients.get(ws):
            return
        user = clients[ws]
        alias = msg.get('alias', '').lower()
        
        db = get_db()
        c = db.cursor()
        c.execute('DELETE FROM user_aliases WHERE alias=? AND owner=?', (alias, user['username']))
        db.commit()
        db.close()
        
        await ws.send(json.dumps({'type': 'alias_response', 'success': True, 'message': f'@{alias} удалён'}))


    # ===== ADMIN GET STATS =====
    elif t == 'admin_get_stats':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM users WHERE premium=1')
        premium_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM users WHERE is_frozen=1')
        frozen_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM users WHERE is_banned=1')
        banned_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM private_messages')
        total_messages = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM chats')
        total_chats = c.fetchone()[0]
        db.close()
        
        online_users = len([c for c in clients.values() if c])
        
        await ws.send(json.dumps({
            'type': 'admin_stats',
            'total_users': total_users,
            'online_users': online_users,
            'total_chats': total_chats,
            'total_messages': total_messages,
            'premium_users': premium_users,
            'frozen_users': frozen_users,
            'banned_users': banned_users
        }))

    # ===== SEND GIFT =====
    elif t == 'send_gift':
        if not clients.get(ws):
            return
        user = clients[ws]
        to_user = msg.get('to', '').lower()
        gift_id = msg.get('gift_id', '')
        price = msg.get('price', 0)
        
        if not to_user or not gift_id:
            return
        
        db = get_db()
        c = db.cursor()
        
        c.execute('SELECT crystals FROM users WHERE username=?', (user['username'],))
        row = c.fetchone()
        if not row or row[0] < price:
            db.close()
            await ws.send(json.dumps({'type': 'error', 'error': 'Недостаточно кристаллов'}))
            return
        
        c.execute('UPDATE users SET crystals=crystals-? WHERE username=?', (price, user['username']))
        
        now = datetime.now().isoformat()
        c.execute('INSERT INTO gifts (to_user, from_user, gift_id, created_at) VALUES (?,?,?,?)',
                  (to_user, user['username'], gift_id, now))
        db.commit()
        
        c.execute('SELECT crystals FROM users WHERE username=?', (user['username'],))
        new_balance = c.fetchone()[0]
        db.close()
        
        await ws.send(json.dumps({'type': 'crystals_update', 'crystals': new_balance}))
        await send_to_user(to_user, {'type': 'gift_received', 'from': user['username'], 'gift_id': gift_id})

    # ===== TRANSFER CRYSTALS =====
    elif t == 'transfer_crystals':
        if not clients.get(ws):
            return
        user = clients[ws]
        to_user = msg.get('to', '').lower()
        amount = msg.get('amount', 0)
        
        if not to_user or amount < 1:
            return
        
        db = get_db()
        c = db.cursor()
        
        c.execute('SELECT crystals FROM users WHERE username=?', (user['username'],))
        row = c.fetchone()
        if not row or row[0] < amount:
            db.close()
            await ws.send(json.dumps({'type': 'error', 'error': 'Недостаточно кристаллов'}))
            return
        
        c.execute('SELECT 1 FROM users WHERE username=?', (to_user,))
        if not c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'error', 'error': 'Пользователь не найден'}))
            return
        
        c.execute('UPDATE users SET crystals=crystals-? WHERE username=?', (amount, user['username']))
        c.execute('UPDATE users SET crystals=crystals+? WHERE username=?', (amount, to_user))
        db.commit()
        
        c.execute('SELECT crystals FROM users WHERE username=?', (user['username'],))
        new_balance = c.fetchone()[0]
        c.execute('SELECT crystals FROM users WHERE username=?', (to_user,))
        to_balance = c.fetchone()[0]
        db.close()
        
        await ws.send(json.dumps({'type': 'crystals_update', 'crystals': new_balance}))
        await send_to_user(to_user, {'type': 'crystals_update', 'crystals': to_balance})


    # ===== PREMIUM PAYMENT REQUEST =====
    elif t == 'premium_payment_request':
        if not clients.get(ws):
            return
        user = clients[ws]
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT premium FROM users WHERE username=?', (user['username'],))
        row = c.fetchone()
        if row and row[0]:
            db.close()
            await ws.send(json.dumps({'type': 'error', 'error': 'У вас уже есть Premium'}))
            return
        
        c.execute('SELECT 1 FROM premium_requests WHERE username=? AND status="pending"', (user['username'],))
        if c.fetchone():
            db.close()
            await ws.send(json.dumps({'type': 'error', 'error': 'Заявка уже отправлена, ожидайте'}))
            return
        
        now = datetime.now().isoformat()
        c.execute('INSERT INTO premium_requests (username, status, created_at) VALUES (?, "pending", ?)',
                  (user['username'], now))
        db.commit()
        db.close()
        
        for admin in ADMINS:
            await send_to_user(admin, {'type': 'premium_request_received', 'username': user['username']})
        
        await ws.send(json.dumps({'type': 'payment_request_sent', 'success': True}))

    # ===== GET PREMIUM REQUESTS (ADMIN) =====
    elif t == 'get_premium_requests':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT username, created_at FROM premium_requests WHERE status="pending" ORDER BY created_at DESC')
        requests = [{'username': r[0], 'created_at': r[1]} for r in c.fetchall()]
        db.close()
        
        await ws.send(json.dumps({'type': 'premium_requests', 'requests': requests}, ensure_ascii=False))

    # ===== APPROVE PREMIUM (ADMIN) =====
    elif t == 'approve_premium':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        target = msg.get('target', '').lower()
        
        db = get_db()
        c = db.cursor()
        c.execute('UPDATE premium_requests SET status="approved" WHERE username=? AND status="pending"', (target,))
        c.execute('UPDATE users SET premium=1 WHERE username=?', (target,))
        db.commit()
        db.close()
        
        await send_to_user(target, {'type': 'premium_activated'})
        await ws.send(json.dumps({'type': 'admin_response', 'message': f'Premium выдан @{target}'}))

    # ===== REJECT PREMIUM (ADMIN) =====
    elif t == 'reject_premium':
        if not clients.get(ws):
            return
        user = clients[ws]
        if user['username'] not in ADMINS:
            return
        
        target = msg.get('target', '').lower()
        
        db = get_db()
        c = db.cursor()
        c.execute('UPDATE premium_requests SET status="rejected" WHERE username=? AND status="pending"', (target,))
        db.commit()
        db.close()
        
        await send_to_user(target, {'type': 'premium_rejected', 'message': 'Заявка на Premium отклонена'})
        await ws.send(json.dumps({'type': 'admin_response', 'message': f'Заявка @{target} отклонена'}))


# ===== MAIN =====
async def main():
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Velora server on port {port}...")
    
    async with websockets.serve(handle_client, "0.0.0.0", port):
        print(f"Server running on ws://0.0.0.0:{port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
