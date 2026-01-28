import customtkinter as ctk
import requests
import json
import os
from tkinter import messagebox
import threading
from PIL import Image
import socketio

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = 'vox_config.json'
SERVER_URL = 'http://localhost:5000'

class VoxMessenger:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Vox Messenger")
        self.root.geometry("1000x700")
        
        self.token = None
        self.username = None
        self.user_id = None
        self.role = None
        self.verified = False
        
        self.language = 'ru'
        self.bg_color = '#1a1a1a'
        
        self.sio = socketio.Client()
        self.setup_socketio()
        
        self.load_config()
        
        if self.token:
            if self.auto_login():
                self.show_main_screen()
            else:
                self.show_login_screen()
        else:
            self.show_login_screen()
    
    def setup_socketio(self):
        @self.sio.on('new_message')
        def on_new_message(data):
            self.show_desktop_notification(f"Новое сообщение", data['content'])
    
    def show_desktop_notification(self, title, message):
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name='Vox Messenger',
                timeout=5
            )
        except:
            pass
    
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.token = config.get('token')
                self.language = config.get('language', 'ru')
                self.bg_color = config.get('bg_color', '#1a1a1a')
    
    def save_config(self):
        config = {
            'token': self.token,
            'language': self.language,
            'bg_color': self.bg_color
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f)
    
    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def auto_login(self):
        try:
            response = requests.post(f'{SERVER_URL}/api/auto_login', 
                                    json={'token': self.token},
                                    timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    self.username = data['username']
                    self.user_id = data['user_id']
                    self.role = data['role']
                    self.verified = data['verified']
                    return True
            elif response.status_code == 403:
                data = response.json()
                if data.get('error') == 'banned':
                    self.show_ban_notification(data.get('reason', 'Нарушение правил'))
            return False
        except:
            return False
    
    def show_ban_notification(self, reason):
        self.clear_window()
        
        frame = ctk.CTkFrame(self.root)
        frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="⚠️ Ваш аккаунт заблокирован", 
                    font=("Arial", 24, "bold"), text_color="red").pack(pady=20)
        
        ctk.CTkLabel(frame, text=f"Причина: {reason}", 
                    font=("Arial", 16)).pack(pady=10)
        
        ctk.CTkLabel(frame, text="Вы можете обжаловать блокировку в разделе Поддержка", 
                    font=("Arial", 14)).pack(pady=10)
        
        ctk.CTkButton(frame, text="Перейти в Поддержку", 
                     command=self.show_support_screen,
                     width=200, height=40).pack(pady=20)
        
        ctk.CTkButton(frame, text="Выйти", 
                     command=self.logout,
                     width=200, height=40).pack(pady=10)
    
    def show_login_screen(self):
        self.clear_window()
        
        frame = ctk.CTkFrame(self.root)
        frame.pack(expand=True)
        
        ctk.CTkLabel(frame, text="Vox Messenger", 
                    font=("Arial", 32, "bold")).pack(pady=20)
        
        self.login_username = ctk.CTkEntry(frame, placeholder_text="Юзернейм (мин. 4 символа)", 
                                          width=300, height=40)
        self.login_username.pack(pady=10)
        
        self.login_password = ctk.CTkEntry(frame, placeholder_text="Пароль", 
                                          width=300, height=40, show="*")
        self.login_password.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="Войти", command=self.login,
                     width=140, height=40).pack(side='left', padx=5)
        
        ctk.CTkButton(btn_frame, text="Регистрация", command=self.register,
                     width=140, height=40).pack(side='left', padx=5)
    
    def login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get()
        
        if not username or not password:
            messagebox.showerror("Ошибка", "Заполните все поля")
            return
        
        try:
            response = requests.post(f'{SERVER_URL}/api/login',
                                    json={'username': username, 'password': password},
                                    timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    self.token = data['token']
                    self.username = data['username']
                    self.user_id = data['user_id']
                    self.role = data['role']
                    self.verified = data['verified']
                    self.save_config()
                    self.show_main_screen()
            elif response.status_code == 403:
                data = response.json()
                if data.get('error') == 'banned':
                    self.show_ban_notification(data.get('reason', 'Нарушение правил'))
            else:
                data = response.json()
                messagebox.showerror("Ошибка", data.get('error', 'Ошибка входа'))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться к серверу: {e}")
    
    def register(self):
        username = self.login_username.get().strip()
        password = self.login_password.get()
        
        if len(username) < 4:
            messagebox.showerror("Ошибка", "Юзернейм должен быть минимум 4 символа")
            return
        
        if len(password) < 6:
            messagebox.showerror("Ошибка", "Пароль должен быть минимум 6 символов")
            return
        
        try:
            response = requests.post(f'{SERVER_URL}/api/register',
                                    json={'username': username, 'password': password},
                                    timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    self.token = data['token']
                    self.username = data['username']
                    self.user_id = data['user_id']
                    self.save_config()
                    messagebox.showinfo("Успех", "Регистрация успешна!")
                    self.show_main_screen()
            else:
                data = response.json()
                messagebox.showerror("Ошибка", data.get('error', 'Ошибка регистрации'))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться к серверу: {e}")
    
    def show_main_screen(self):
        self.clear_window()
        
        # Подключаемся к Socket.IO
        try:
            if not self.sio.connected:
                self.sio.connect(SERVER_URL)
        except:
            pass
        
        # Левая панель - меню
        left_panel = ctk.CTkFrame(self.root, width=200)
        left_panel.pack(side='left', fill='y', padx=5, pady=5)
        
        # Профиль
        profile_frame = ctk.CTkFrame(left_panel)
        profile_frame.pack(pady=10, padx=10, fill='x')
        
        username_text = self.username
        if self.verified:
            username_text += " ✓"
        if self.role == 'creator':
            username_text += " 👑"
        
        ctk.CTkLabel(profile_frame, text=username_text, 
                    font=("Arial", 14, "bold")).pack(pady=5)
        
        # Меню
        ctk.CTkButton(left_panel, text="💬 Чаты", 
                     command=self.show_chats,
                     width=180, height=40).pack(pady=5, padx=10)
        
        ctk.CTkButton(left_panel, text="🤖 Боты", 
                     command=self.show_bots,
                     width=180, height=40).pack(pady=5, padx=10)
        
        ctk.CTkButton(left_panel, text="💎 Премиум", 
                     command=self.show_premium,
                     width=180, height=40).pack(pady=5, padx=10)
        
        ctk.CTkButton(left_panel, text="🆘 Поддержка", 
                     command=self.show_support_screen,
                     width=180, height=40).pack(pady=5, padx=10)
        
        if self.role in ['creator', 'admin', 'moderator']:
            ctk.CTkButton(left_panel, text="⚙️ Админ панель", 
                         command=self.show_admin_panel,
                         width=180, height=40, fg_color="red").pack(pady=5, padx=10)
        
        ctk.CTkButton(left_panel, text="⚙️ Настройки", 
                     command=self.show_settings,
                     width=180, height=40).pack(pady=5, padx=10)
        
        ctk.CTkButton(left_panel, text="🚪 Выйти", 
                     command=self.logout,
                     width=180, height=40).pack(pady=5, padx=10, side='bottom')
        
        # Правая панель - контент
        self.content_frame = ctk.CTkFrame(self.root)
        self.content_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.show_chats()
    
    def show_chats(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.content_frame, text="Чаты", 
                    font=("Arial", 24, "bold")).pack(pady=20)
        
        try:
            response = requests.get(f'{SERVER_URL}/api/chats',
                                   params={'token': self.token},
                                   timeout=5)
            if response.status_code == 200:
                data = response.json()
                chats = data.get('chats', [])
                
                if not chats:
                    ctk.CTkLabel(self.content_frame, text="У вас пока нет чатов",
                                font=("Arial", 14)).pack(pady=20)
                else:
                    for chat in chats:
                        chat_btn = ctk.CTkButton(self.content_frame, 
                                                text=chat['name'],
                                                width=400, height=50)
                        chat_btn.pack(pady=5)
        except:
            ctk.CTkLabel(self.content_frame, text="Ошибка загрузки чатов",
                        font=("Arial", 14)).pack(pady=20)
    
    def show_bots(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.content_frame, text="Боты", 
                    font=("Arial", 24, "bold")).pack(pady=20)
        
        ctk.CTkLabel(self.content_frame, text="Создавайте и управляйте ботами",
                    font=("Arial", 14)).pack(pady=10)
        
        ctk.CTkButton(self.content_frame, text="Создать бота",
                     width=200, height=40).pack(pady=20)
    
    def show_premium(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.content_frame, text="💎 Vox Premium", 
                    font=("Arial", 24, "bold")).pack(pady=20)
        
        features = [
            "✓ Файлы до 4GB",
            "✓ Группы до 100,000 участников",
            "✓ Кастомные стикеры",
            "✓ Уникальные темы",
            "✓ Приоритетная поддержка",
            "✓ Безлимитная история",
            "✓ Значки и бейджи"
        ]
        
        for feature in features:
            ctk.CTkLabel(self.content_frame, text=feature,
                        font=("Arial", 14)).pack(pady=5)
        
        ctk.CTkButton(self.content_frame, text="Купить Premium - 299₽/мес",
                     width=300, height=50, fg_color="gold", 
                     text_color="black").pack(pady=30)
    
    def show_support_screen(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.content_frame, text="🆘 Поддержка", 
                    font=("Arial", 24, "bold")).pack(pady=20)
        
        ctk.CTkLabel(self.content_frame, text="Тема обращения:",
                    font=("Arial", 14)).pack(pady=5)
        
        subject_entry = ctk.CTkEntry(self.content_frame, width=400, height=40)
        subject_entry.pack(pady=5)
        
        ctk.CTkLabel(self.content_frame, text="Сообщение:",
                    font=("Arial", 14)).pack(pady=5)
        
        message_text = ctk.CTkTextbox(self.content_frame, width=400, height=200)
        message_text.pack(pady=5)
        
        def send_ticket():
            subject = subject_entry.get()
            message = message_text.get("1.0", "end-1c")
            
            if not subject or not message:
                messagebox.showerror("Ошибка", "Заполните все поля")
                return
            
            try:
                response = requests.post(f'{SERVER_URL}/api/support/create',
                                        json={'token': self.token, 'subject': subject, 'message': message},
                                        timeout=5)
                if response.status_code == 200:
                    messagebox.showinfo("Успех", "Обращение отправлено!")
                    subject_entry.delete(0, 'end')
                    message_text.delete("1.0", "end")
            except:
                messagebox.showerror("Ошибка", "Не удалось отправить обращение")
        
        ctk.CTkButton(self.content_frame, text="Отправить",
                     command=send_ticket,
                     width=200, height=40).pack(pady=20)
    
    def show_admin_panel(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.content_frame, text="⚙️ Админ панель", 
                    font=("Arial", 24, "bold")).pack(pady=20)
        
        ctk.CTkButton(self.content_frame, text="Управление пользователями",
                     width=300, height=50).pack(pady=10)
        
        ctk.CTkButton(self.content_frame, text="Модерация контента",
                     width=300, height=50).pack(pady=10)
        
        ctk.CTkButton(self.content_frame, text="Обращения в поддержку",
                     width=300, height=50).pack(pady=10)
        
        ctk.CTkButton(self.content_frame, text="Статистика",
                     width=300, height=50).pack(pady=10)
    
    def show_settings(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.content_frame, text="⚙️ Настройки", 
                    font=("Arial", 24, "bold")).pack(pady=20)
        
        # Язык
        ctk.CTkLabel(self.content_frame, text="Язык:",
                    font=("Arial", 14)).pack(pady=5)
        
        lang_var = ctk.StringVar(value=self.language)
        lang_menu = ctk.CTkOptionMenu(self.content_frame, 
                                      values=["ru", "en", "uk"],
                                      variable=lang_var,
                                      width=200)
        lang_menu.pack(pady=5)
        
        # Цвет фона
        ctk.CTkLabel(self.content_frame, text="Цвет фона:",
                    font=("Arial", 14)).pack(pady=5)
        
        color_var = ctk.StringVar(value=self.bg_color)
        color_menu = ctk.CTkOptionMenu(self.content_frame,
                                       values=["#1a1a1a", "#2b2b2b", "#0d1117", "#1e1e2e"],
                                       variable=color_var,
                                       width=200)
        color_menu.pack(pady=5)
        
        def save_settings():
            self.language = lang_var.get()
            self.bg_color = color_var.get()
            self.save_config()
            messagebox.showinfo("Успех", "Настройки сохранены!")
        
        ctk.CTkButton(self.content_frame, text="Сохранить",
                     command=save_settings,
                     width=200, height=40).pack(pady=20)
    
    def logout(self):
        try:
            requests.post(f'{SERVER_URL}/api/logout',
                         json={'token': self.token},
                         timeout=5)
        except:
            pass
        
        self.token = None
        self.username = None
        self.user_id = None
        self.save_config()
        
        if self.sio.connected:
            self.sio.disconnect()
        
        self.show_login_screen()
    
    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = VoxMessenger()
    app.run()
