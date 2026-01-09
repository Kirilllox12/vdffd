import asyncio
import websockets
import json
import sqlite3
import os
from datetime import datetime

db_path = '/tmp/velora.db'

def get_db():
    return sqlite3.connect(db_path)

def init_db():
    db = get_db()
    c = db.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        display_name TEXT,
        crystals INTEGER DEFAULT 100,
        premium INTEGER DEFAULT 0
    )''')
    db.commit()
    db.close()

init_db()
clients = {}

async def handle_client(websocket):
    print("Client connected")
    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                response = await process_message(msg, websocket)
                if response:
                    await websocket.send(json.dumps(response))
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
    
    if t == 'register':
        username = msg.get('username', '').lower().strip()
        password = msg.get('password', '')
        display_name = msg.get('display_name', username)
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT 1 FROM users WHERE username=?', (username,))
        if c.fetchone():
            db.close()
            return {'type': 'register_response', 'success': False, 'error': 'Имя занято'}
        
        c.execute('INSERT INTO users VALUES (?,?,?,100,0)', (username, password, display_name))
        db.commit()
        db.close()
        
        user = {'username': username, 'display_name': display_name, 'crystals': 100, 'premium': False}
        clients[ws] = user
        return {'type': 'register_response', 'success': True, 'user': user}
    
    elif t == 'login':
        username = msg.get('username', '').lower().strip()
        password = msg.get('password', '')
        
        db = get_db()
        c = db.cursor()
        c.execute('SELECT username, display_name, crystals, premium FROM users WHERE username=? AND password=?', (username, password))
        row = c.fetchone()
        db.close()
        
        if not row:
            return {'type': 'login_response', 'success': False, 'error': 'Неверные данные'}
        
        user = {'username': row[0], 'display_name': row[1], 'crystals': row[2], 'premium': bool(row[3])}
        clients[ws] = user
        return {'type': 'login_response', 'success': True, 'user': user}
    
    return None

async def main():
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}")
    async with websockets.serve(handle_client, "0.0.0.0", port):
        print("Server running!")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
