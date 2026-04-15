# app.py
import eventlet
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import random
import time
import threading
import uuid
import sqlite3
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from game.generator import *
from game.scoring import calculate_score

eventlet.monkey_patch()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

socketio = SocketIO(app,
                   cors_allowed_origins="*",
                   async_mode='eventlet',
                   logger=False,
                   engineio_logger=False)
app.config['SESSION_TYPE'] = 'filesystem'


DATABASE = 'brain_trainer.db'
ROUND_TIME = 30
BOT_NAMES = ["NeuroBot", "QuantumMind", "LogicMaster", "BrainWave", "SynapseX",
             "CortexPrime", "NeuralNet", "DeepThink", "MindStorm", "Cerebro"]


# ============== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==============
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Пользователи
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP,
        is_online BOOLEAN DEFAULT 0,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        elo INTEGER DEFAULT 1200,
        perfect_runs INTEGER DEFAULT 0,
        max_combo INTEGER DEFAULT 0,
        duel_wins INTEGER DEFAULT 0,
        duel_losses INTEGER DEFAULT 0,
        avatar_color TEXT DEFAULT '#ef4444',
        avatar_icon TEXT DEFAULT 'fa-user-astronaut',
        skin TEXT DEFAULT '#ef4444'
    )''')

    # Рекорды пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS user_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_mode TEXT NOT NULL,
        score INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(user_id, game_mode)
    )''')

    # История игр
    c.execute('''CREATE TABLE IF NOT EXISTS game_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_mode TEXT NOT NULL,
        score INTEGER DEFAULT 0,
        correct_answers INTEGER DEFAULT 0,
        wrong_answers INTEGER DEFAULT 0,
        max_combo INTEGER DEFAULT 0,
        played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # Достижения
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        achievement_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        icon TEXT
    )''')

    # Достижения пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS user_achievements (
        user_id INTEGER NOT NULL,
        achievement_id TEXT NOT NULL,
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        PRIMARY KEY (user_id, achievement_id)
    )''')

    # Друзья
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (friend_id) REFERENCES users (id),
        UNIQUE(user_id, friend_id)
    )''')

    # Боты
    c.execute('''CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        elo INTEGER DEFAULT 1200,
        difficulty TEXT DEFAULT 'medium',
        accuracy REAL DEFAULT 0.8,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        skin TEXT DEFAULT '#3b82f6'
    )''')

    # Дуэли
    c.execute('''CREATE TABLE IF NOT EXISTS duels (
        id TEXT PRIMARY KEY,
        player1_id INTEGER NOT NULL,
        player2_id INTEGER,
        player2_bot_id INTEGER,
        game_mode TEXT DEFAULT 'math',
        player1_score INTEGER DEFAULT 0,
        player2_score INTEGER DEFAULT 0,
        current_round INTEGER DEFAULT 0,
        max_rounds INTEGER DEFAULT 5,
        status TEXT DEFAULT 'pending',
        winner_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP,
        FOREIGN KEY (player1_id) REFERENCES users (id),
        FOREIGN KEY (player2_id) REFERENCES users (id),
        FOREIGN KEY (player2_bot_id) REFERENCES bots (id)
    )''')

    # Приглашения в дуэль
    c.execute('''CREATE TABLE IF NOT EXISTS duel_invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER NOT NULL,
        to_user_id INTEGER NOT NULL,
        game_mode TEXT DEFAULT 'math',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        duel_id TEXT,
        FOREIGN KEY (from_user_id) REFERENCES users (id),
        FOREIGN KEY (to_user_id) REFERENCES users (id)
    )''')

    # Вставляем базовые достижения
    achievements_data = [
        ('first_win', '🎯 Первая победа', 'Завершите первый раунд', 'fa-trophy'),
        ('math_master', '🧮 Математик', 'Наберите 1000 очков в математике', 'fa-calculator'),
        ('perfect_run', '💯 Идеально', 'Пройдите раунд без ошибок', 'fa-star'),
        ('combo_king', '🔥 Король комбо', 'Достигните комбо x10', 'fa-fire'),
        ('memory_guru', '🧠 Мастер памяти', 'Наберите 500 очков в играх на память', 'fa-brain'),
        ('logic_genius', '🔮 Гений логики', 'Наберите 500 очков в логических играх', 'fa-puzzle-piece'),
        ('duel_winner', '⚔️ Дуэлянт', 'Выиграйте 5 дуэлей', 'fa-crosshairs'),
        ('social_butterfly', '🦋 Социальный', 'Добавьте 3 друзей', 'fa-users')
    ]

    for ach in achievements_data:
        c.execute('''INSERT OR IGNORE INTO achievements (achievement_id, name, description, icon) 
                     VALUES (?, ?, ?, ?)''', ach)

    # Вставляем ботов если их нет
    c.execute('SELECT COUNT(*) FROM bots')
    if c.fetchone()[0] == 0:
        colors = ["#ef4444", "#f97316", "#fbbf24", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899"]
        for name in BOT_NAMES:
            difficulty = random.choice(["easy", "medium", "hard"])
            if difficulty == "easy":
                accuracy = random.uniform(0.5, 0.7)
                elo = random.randint(800, 1100)
            elif difficulty == "medium":
                accuracy = random.uniform(0.7, 0.85)
                elo = random.randint(1100, 1400)
            else:
                accuracy = random.uniform(0.85, 0.95)
                elo = random.randint(1400, 1800)
            c.execute('''INSERT INTO bots (name, elo, difficulty, accuracy, skin) 
                         VALUES (?, ?, ?, ?, ?)''',
                      (name, elo, difficulty, accuracy, random.choice(colors)))

    conn.commit()
    conn.close()


init_db()


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ БД ==============
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_username(username):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user


def create_user(username, password, avatar_color='#ef4444', avatar_icon='fa-user-astronaut'):
    conn = get_db()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO users (username, password_hash, avatar_color, avatar_icon, skin) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (username, password_hash.decode('utf-8'), avatar_color, avatar_icon, avatar_color))
        conn.commit()
        user_id = c.lastrowid

        # Создаем записи рекордов для всех режимов
        modes = ['math', 'math_chain', 'math_compare', 'memory_digits', 'memory_words',
                 'memory_positions', 'logic_sequences', 'logic_analogies', 'logic_sets']
        for mode in modes:
            c.execute('INSERT INTO user_records (user_id, game_mode, score) VALUES (?, ?, 0)',
                      (user_id, mode))
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def verify_password(username, password):
    user = get_user_by_username(username)
    if not user:
        return False
    return bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8'))


def update_user_online(user_id, is_online):
    conn = get_db()
    conn.execute('UPDATE users SET is_online = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?',
                 (1 if is_online else 0, user_id))
    conn.commit()
    conn.close()


def get_user_stats(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    records = {}
    records_rows = conn.execute('SELECT * FROM user_records WHERE user_id = ?', (user_id,)).fetchall()
    for row in records_rows:
        records[row['game_mode']] = row['score']

    history = conn.execute('''SELECT * FROM game_history WHERE user_id = ? 
                              ORDER BY played_at DESC LIMIT 10''', (user_id,)).fetchall()

    achievements = conn.execute('''SELECT a.* FROM achievements a 
                                   JOIN user_achievements ua ON a.achievement_id = ua.achievement_id 
                                   WHERE ua.user_id = ?''', (user_id,)).fetchall()

    conn.close()
    return {
        'user': dict(user) if user else None,
        'records': records,
        'history': [dict(h) for h in history],
        'achievements': [dict(a) for a in achievements]
    }


def get_level(xp):
    return xp // 100 + 1


def calculate_elo_change(winner_elo, loser_elo, k=32):
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))
    winner_new = round(winner_elo + k * (1 - expected_winner))
    loser_new = round(loser_elo + k * (0 - expected_loser))
    return winner_new, loser_new


def get_random_bot():
    conn = get_db()
    bot = conn.execute('SELECT * FROM bots ORDER BY RANDOM() LIMIT 1').fetchone()
    conn.close()
    return dict(bot) if bot else None


def get_bot_by_elo(target_elo):
    conn = get_db()
    bots = conn.execute('SELECT * FROM bots').fetchall()
    conn.close()
    if not bots:
        return None
    best_bot = min(bots, key=lambda b: abs(b['elo'] - target_elo))
    return dict(best_bot)


def check_and_award_achievements(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    records = conn.execute('SELECT * FROM user_records WHERE user_id = ?', (user_id,)).fetchall()

    # Проверяем все достижения
    all_achievements = conn.execute('SELECT * FROM achievements').fetchall()
    new_achievements = []

    for ach in all_achievements:
        existing = conn.execute('SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?',
                                (user_id, ach['achievement_id'])).fetchone()
        if existing:
            continue

        awarded = False
        if ach['achievement_id'] == 'first_win':
            games_played = conn.execute('SELECT COUNT(*) as count FROM game_history WHERE user_id = ?',
                                        (user_id,)).fetchone()['count']
            awarded = games_played >= 1
        elif ach['achievement_id'] == 'math_master':
            math_score = sum(r['score'] for r in records if r['game_mode'] in ['math', 'math_chain', 'math_compare'])
            awarded = math_score >= 1000
        elif ach['achievement_id'] == 'perfect_run':
            awarded = user['perfect_runs'] >= 1
        elif ach['achievement_id'] == 'combo_king':
            awarded = user['max_combo'] >= 10
        elif ach['achievement_id'] == 'memory_guru':
            memory_score = sum(r['score'] for r in records if 'memory' in r['game_mode'])
            awarded = memory_score >= 500
        elif ach['achievement_id'] == 'logic_genius':
            logic_score = sum(r['score'] for r in records if 'logic' in r['game_mode'])
            awarded = logic_score >= 500
        elif ach['achievement_id'] == 'duel_winner':
            awarded = user['duel_wins'] >= 5
        elif ach['achievement_id'] == 'social_butterfly':
            friends_count = \
            conn.execute('SELECT COUNT(*) as count FROM friends WHERE user_id = ? AND status = "accepted"',
                         (user_id,)).fetchone()['count']
            awarded = friends_count >= 3

        if awarded:
            conn.execute('INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)',
                         (user_id, ach['achievement_id']))
            new_achievements.append(dict(ach))

    conn.commit()
    conn.close()
    return new_achievements


# ============== ДЕКОРАТОРЫ ==============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# ============== МАРШРУТЫ АВТОРИЗАЦИИ ==============
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('menu'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if verify_password(username, password):
            user = get_user_by_username(username)
            session['user_id'] = user['id']
            session['username'] = user['username']
            update_user_online(user['id'], True)
            return jsonify({'success': True, 'redirect': url_for('menu')})
        return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'})

    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email', '')
    avatar_color = data.get('avatar_color', '#ef4444')
    avatar_icon = data.get('avatar_icon', 'fa-user-astronaut')

    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Имя пользователя должно быть не менее 3 символов'})
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль должен быть не менее 6 символов'})

    user_id = create_user(username, password, avatar_color, avatar_icon)
    if user_id:
        session['user_id'] = user_id
        session['username'] = username
        update_user_online(user_id, True)
        return jsonify({'success': True, 'redirect': url_for('menu')})
    return jsonify({'success': False, 'error': 'Пользователь с таким именем уже существует'})


@app.route('/logout')
def logout():
    if 'user_id' in session:
        update_user_online(session['user_id'], False)
    session.clear()
    return redirect(url_for('login'))


# ============== ОСНОВНЫЕ МАРШРУТЫ ==============
@app.route('/menu')
@login_required
def menu():
    user_id = session['user_id']
    username = session.get('username', 'Пользователь')  # Получаем имя из сессии

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user:
        session.clear()
        return redirect(url_for('login'))

    # Получаем рекорды
    records = {}
    records_rows = conn.execute('SELECT * FROM user_records WHERE user_id = ?', (user_id,)).fetchall()
    for row in records_rows:
        records[row['game_mode']] = row['score']

    # Получаем историю
    history = conn.execute('''SELECT * FROM game_history WHERE user_id = ? 
                              ORDER BY played_at DESC LIMIT 10''', (user_id,)).fetchall()

    # Получаем достижения
    achievements = conn.execute('''SELECT a.* FROM achievements a 
                                   JOIN user_achievements ua ON a.achievement_id = ua.achievement_id 
                                   WHERE ua.user_id = ?''', (user_id,)).fetchall()
    conn.close()

    user_dict = dict(user)
    level = get_level(user_dict.get('xp', 0))
    xp = user_dict.get('xp', 0)

    return render_template('menu.html',
                           name=username,  # ← Передаем имя
                           user=user_dict,
                           records=records,
                           history=[dict(h) for h in history],
                           achievements=[dict(a) for a in achievements],
                           level=level,
                           xp=xp)


@app.route('/game/<mode>')
@login_required
def game(mode):
    session['mode'] = mode
    session['score'] = 0
    session['combo'] = 1
    session['max_combo'] = 1
    session['correct'] = 0
    session['wrong'] = 0
    session['times'] = []

    names = {
        "math": "⚡ Быстрый счёт",
        "math_chain": "🔗 Цепочки",
        "math_compare": "⚖️ Сравнение",
        "memory_digits": "🔢 Цифры",
        "memory_words": "📝 Слова",
        "memory_positions": "🗺️ Позиции",
        "logic_sequences": "📊 Последовательности",
        "logic_analogies": "🔄 Аналогии",
        "logic_sets": "🎯 Множества"
    }
    return render_template('game.html', mode=mode, title=names.get(mode, "Игра"), round_time=ROUND_TIME)


@app.route('/task/<mode>')
@login_required
def task(mode):
    tasks = {
        "math": generate_math,
        "math_chain": generate_math_chain,
        "math_compare": generate_math_compare,
        "memory_digits": generate_memory_digits,
        "memory_words": generate_memory_words,
        "memory_positions": generate_memory_positions,
        "logic_sequences": generate_logic,
        "logic_analogies": generate_logic_analogies,
        "logic_sets": generate_logic_sets
    }
    return jsonify(tasks.get(mode, lambda: {"error": "Unknown mode"})())


@app.route('/check', methods=['POST'])
@login_required
def check():
    d = request.json
    correct = str(d["answer"]).strip().lower() == str(d["correct"]).strip().lower()
    time_taken = float(d["time"])
    combo = session.get('combo', 1)
    score = calculate_score(correct, time_taken, combo)

    session['times'] = session.get('times', []) + [time_taken]
    if correct:
        session['correct'] = session.get('correct', 0) + 1
        session['combo'] = combo + 1
        if session['combo'] > session.get('max_combo', 1):
            session['max_combo'] = session['combo']
    else:
        session['wrong'] = session.get('wrong', 0) + 1
        session['combo'] = 1
    session['score'] = max(0, session.get('score', 0) + score)
    session.modified = True

    return jsonify({"score": session['score'], "combo": session['combo'], "correct": correct})


@app.route('/result')
@login_required
def result():
    user_id = session['user_id']
    mode = session.get('mode', 'math')
    score = session.get('score', 0)
    correct = session.get('correct', 0)
    wrong = session.get('wrong', 0)
    times = session.get('times', [])
    max_combo = session.get('max_combo', 1)

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    # Обновляем рекорд
    current_record = conn.execute('SELECT score FROM user_records WHERE user_id = ? AND game_mode = ?',
                                  (user_id, mode)).fetchone()
    is_record = False
    if current_record and score > current_record['score']:
        conn.execute(
            'UPDATE user_records SET score = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND game_mode = ?',
            (score, user_id, mode))
        is_record = True

    # Добавляем в историю
    conn.execute('''INSERT INTO game_history (user_id, game_mode, score, correct_answers, wrong_answers, max_combo) 
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (user_id, mode, score, correct, wrong, max_combo))

    # Обновляем статистику пользователя
    xp_gain = max(score // 2, 1)
    new_xp = user['xp'] + xp_gain
    new_level = get_level(new_xp)
    new_perfect_runs = user['perfect_runs'] + (1 if wrong == 0 and correct > 0 else 0)
    new_max_combo = max(user['max_combo'], max_combo)

    conn.execute('''UPDATE users SET xp = ?, level = ?, perfect_runs = ?, max_combo = ? 
                    WHERE id = ?''',
                 (new_xp, new_level, new_perfect_runs, new_max_combo, user_id))
    conn.commit()
    conn.close()

    # Проверяем достижения
    new_achievements = check_and_award_achievements(user_id)

    total = correct + wrong
    accuracy = round((correct / total * 100) if total > 0 else 0, 1)
    avg_time = round(sum(times) / len(times), 2) if times else 0

    feedback = "🌟 Идеально!" if wrong == 0 else ("👍 Хорошо!" if wrong <= 3 else "🎮 Продолжай!")

    for k in ['mode', 'score', 'combo', 'max_combo', 'correct', 'wrong', 'times']:
        session.pop(k, None)

    return render_template("result.html",
                           score=score,
                           correct=correct,
                           wrong=wrong,
                           accuracy=accuracy,
                           avg_time=avg_time,
                           mode=mode,
                           xp_gain=xp_gain,
                           is_record=is_record,
                           max_combo=max_combo,
                           feedback=feedback,
                           new_achievements=new_achievements)


@app.route('/duel')
@login_required
def duel():
    return render_template("duel.html")


@app.route('/duel/<mode>')
@login_required
def duel_with_mode(mode):
    return render_template("duel_game.html", mode=mode)


# ============== API ДРУЗЕЙ ==============
@app.route('/api/friends')
@login_required
def get_friends():
    user_id = session['user_id']
    conn = get_db()

    # Получаем друзей
    friends = conn.execute('''
        SELECT u.id, u.username, u.level, u.xp, u.avatar_color, u.avatar_icon, u.is_online,
               u.elo, u.duel_wins, u.duel_losses, f.status
        FROM friends f
        JOIN users u ON (f.friend_id = u.id AND f.user_id = ?) 
                     OR (f.user_id = u.id AND f.friend_id = ?)
        WHERE f.status = 'accepted'
    ''', (user_id, user_id)).fetchall()

    # Получаем входящие заявки
    incoming = conn.execute('''
        SELECT f.id, u.id as user_id, u.username, u.level, u.avatar_color, u.avatar_icon, f.created_at
        FROM friends f
        JOIN users u ON f.user_id = u.id
        WHERE f.friend_id = ? AND f.status = 'pending'
    ''', (user_id,)).fetchall()

    # Получаем исходящие заявки
    outgoing = conn.execute('''
        SELECT f.id, u.id as user_id, u.username, u.level, u.avatar_color, u.avatar_icon, f.created_at
        FROM friends f
        JOIN users u ON f.friend_id = u.id
        WHERE f.user_id = ? AND f.status = 'pending'
    ''', (user_id,)).fetchall()

    conn.close()

    return jsonify({
        'friends': [dict(f) for f in friends],
        'incoming': [dict(i) for i in incoming],
        'outgoing': [dict(o) for o in outgoing]
    })


@app.route('/api/friends/search', methods=['GET'])
@login_required
def search_users():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])

    user_id = session['user_id']
    conn = get_db()
    users = conn.execute('''
        SELECT id, username, level, avatar_color, avatar_icon, is_online
        FROM users 
        WHERE username LIKE ? AND id != ?
        LIMIT 20
    ''', (f'%{query}%', user_id)).fetchall()
    conn.close()

    return jsonify([dict(u) for u in users])


@app.route('/api/friends/add', methods=['POST'])
@login_required
def add_friend():
    user_id = session['user_id']
    data = request.json
    friend_id = data.get('friend_id')

    if user_id == friend_id:
        return jsonify({'success': False, 'error': 'Нельзя добавить себя в друзья'})

    conn = get_db()

    # Проверяем существование пользователя
    friend = conn.execute('SELECT id FROM users WHERE id = ?', (friend_id,)).fetchone()
    if not friend:
        conn.close()
        return jsonify({'success': False, 'error': 'Пользователь не найден'})

    # Проверяем существующую дружбу
    existing = conn.execute('''
        SELECT * FROM friends 
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (user_id, friend_id, friend_id, user_id)).fetchone()

    if existing:
        conn.close()
        return jsonify({'success': False, 'error': 'Заявка уже существует'})

    # Создаем заявку
    conn.execute('INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, "pending")',
                 (user_id, friend_id))
    conn.commit()
    conn.close()

    # Отправляем уведомление через сокеты
    socketio.emit('friend_request', {
        'from_user_id': user_id,
        'from_username': session['username']
    }, room=f'user_{friend_id}')

    return jsonify({'success': True})


@app.route('/api/friends/accept', methods=['POST'])
@login_required
def accept_friend():
    user_id = session['user_id']
    data = request.json
    request_id = data.get('request_id')

    conn = get_db()
    conn.execute('UPDATE friends SET status = "accepted" WHERE id = ? AND friend_id = ?',
                 (request_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/friends/reject', methods=['POST'])
@login_required
def reject_friend():
    user_id = session['user_id']
    data = request.json
    request_id = data.get('request_id')

    conn = get_db()
    conn.execute('DELETE FROM friends WHERE id = ? AND friend_id = ?',
                 (request_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/friends/remove', methods=['POST'])
@login_required
def remove_friend():
    user_id = session['user_id']
    data = request.json
    friend_id = data.get('friend_id')

    conn = get_db()
    conn.execute('DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)',
                 (user_id, friend_id, friend_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/user/<int:user_id>')
@login_required
def get_user_profile(user_id):
    user_data = get_user_stats(user_id)
    if not user_data['user']:
        return jsonify({'error': 'User not found'}), 404

    # Проверяем статус дружбы
    current_user_id = session['user_id']
    conn = get_db()
    friendship = conn.execute('''
        SELECT status FROM friends 
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (current_user_id, user_id, user_id, current_user_id)).fetchone()
    conn.close()

    return jsonify({
        'user': user_data['user'],
        'records': user_data['records'],
        'achievements': user_data['achievements'],
        'friendship_status': friendship['status'] if friendship else None
    })


# ============== API ДУЭЛЕЙ ==============
@app.route('/api/duel/queue', methods=['POST'])
@login_required
def duel_queue():
    user_id = session['user_id']
    data = request.json or {}
    game_mode = data.get('mode', 'math')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    # Ищем бота для дуэли (заглушка на 3 секунды поиска)
    time.sleep(3)  # Имитация поиска

    bot = get_bot_by_elo(user['elo'])

    if bot:
        duel_id = f"duel_{int(time.time())}_{user_id}_{bot['id']}"
        conn.execute('''
            INSERT INTO duels (id, player1_id, player2_bot_id, game_mode, status, max_rounds)
            VALUES (?, ?, ?, ?, 'active', 5)
        ''', (duel_id, user_id, bot['id'], game_mode))
        conn.commit()

        return jsonify({
            'status': 'matched',
            'duel_id': duel_id,
            'player': {
                'id': user['id'],
                'name': user['username'],
                'elo': user['elo'],
                'skin': user['skin']
            },
            'opponent': {
                'id': bot['id'],
                'name': bot['name'],
                'elo': bot['elo'],
                'skin': bot['skin'],
                'is_bot': True
            }
        })

    conn.close()
    return jsonify({'status': 'waiting'})


@app.route('/api/duel/invite', methods=['POST'])
@login_required
def invite_to_duel():
    user_id = session['user_id']
    data = request.json
    friend_id = data.get('friend_id')
    game_mode = data.get('mode', 'math')

    conn = get_db()

    # Проверяем дружбу
    friendship = conn.execute('''
        SELECT 1 FROM friends 
        WHERE ((user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?))
        AND status = 'accepted'
    ''', (user_id, friend_id, friend_id, user_id)).fetchone()

    if not friendship:
        conn.close()
        return jsonify({'success': False, 'error': 'Пользователь не в друзьях'})

    # Проверяем, нет ли активного приглашения
    existing = conn.execute('''
        SELECT id FROM duel_invites 
        WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'
    ''', (user_id, friend_id)).fetchone()

    if existing:
        conn.close()
        return jsonify({'success': False, 'error': 'Приглашение уже отправлено'})

    # Создаем приглашение
    invite_id = conn.execute('''
        INSERT INTO duel_invites (from_user_id, to_user_id, game_mode)
        VALUES (?, ?, ?)
    ''', (user_id, friend_id, game_mode)).lastrowid
    conn.commit()
    conn.close()

    # Отправляем уведомление
    socketio.emit('duel_invite', {
        'invite_id': invite_id,
        'from_user_id': user_id,
        'from_username': session['username'],
        'game_mode': game_mode
    }, room=f'user_{friend_id}')

    return jsonify({'success': True, 'invite_id': invite_id})


@app.route('/api/duel/invite/<int:invite_id>/accept', methods=['POST'])
@login_required
def accept_duel_invite(invite_id):
    user_id = session['user_id']

    conn = get_db()
    invite = conn.execute('''
        SELECT * FROM duel_invites 
        WHERE id = ? AND to_user_id = ? AND status = 'pending'
    ''', (invite_id, user_id)).fetchone()

    if not invite:
        conn.close()
        return jsonify({'success': False, 'error': 'Приглашение не найдено'})

    # Создаем дуэль
    duel_id = f"duel_{int(time.time())}_{invite['from_user_id']}_{user_id}"
    conn.execute('''
        INSERT INTO duels (id, player1_id, player2_id, game_mode, status, max_rounds)
        VALUES (?, ?, ?, ?, 'active', 5)
    ''', (duel_id, invite['from_user_id'], user_id, invite['game_mode']))

    # Обновляем статус приглашения
    conn.execute('UPDATE duel_invites SET status = "accepted", duel_id = ? WHERE id = ?',
                 (duel_id, invite_id))
    conn.commit()
    conn.close()

    # Уведомляем обоих игроков
    socketio.emit('duel_start', {'duel_id': duel_id}, room=f'user_{invite["from_user_id"]}')
    socketio.emit('duel_start', {'duel_id': duel_id}, room=f'user_{user_id}')

    return jsonify({'success': True, 'duel_id': duel_id})


@app.route('/api/duel/invite/<int:invite_id>/reject', methods=['POST'])
@login_required
def reject_duel_invite(invite_id):
    user_id = session['user_id']

    conn = get_db()
    conn.execute('UPDATE duel_invites SET status = "rejected" WHERE id = ? AND to_user_id = ?',
                 (invite_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/api/duel/<duel_id>/status')
@login_required
def duel_status(duel_id):
    conn = get_db()
    duel = conn.execute('SELECT * FROM duels WHERE id = ?', (duel_id,)).fetchone()
    if not duel:
        conn.close()
        return jsonify({'error': 'Duel not found'}), 404

    player1 = conn.execute('SELECT * FROM users WHERE id = ?', (duel['player1_id'],)).fetchone()

    opponent = None
    if duel['player2_id']:
        opponent = conn.execute('SELECT * FROM users WHERE id = ?', (duel['player2_id'],)).fetchone()
    elif duel['player2_bot_id']:
        opponent = conn.execute('SELECT * FROM bots WHERE id = ?', (duel['player2_bot_id'],)).fetchone()

    conn.close()

    return jsonify({
        'id': duel['id'],
        'game_mode': duel['game_mode'],
        'player1_score': duel['player1_score'],
        'player2_score': duel['player2_score'],
        'current_round': duel['current_round'],
        'max_rounds': duel['max_rounds'],
        'status': duel['status'],
        'winner_id': duel['winner_id'],
        'player1': dict(player1) if player1 else None,
        'opponent': dict(opponent) if opponent else None
    })


@app.route('/api/duel/<duel_id>/task')
@login_required
def duel_task(duel_id):
    # Генерируем задание для дуэли
    task_type = random.choice(["math", "math_chain", "math_compare", "logic"])
    if task_type == "math":
        task = generate_math()
    elif task_type == "math_chain":
        task = generate_math_chain()
    elif task_type == "math_compare":
        task = generate_math_compare()
    else:
        task = generate_logic()

    return jsonify({'task': task})


@app.route('/api/duel/<duel_id>/answer', methods=['POST'])
@login_required
def duel_answer(duel_id):
    user_id = session['user_id']
    data = request.json
    answer = str(data.get('answer', '')).strip().lower()

    conn = get_db()
    duel = conn.execute('SELECT * FROM duels WHERE id = ?', (duel_id,)).fetchone()

    if not duel:
        conn.close()
        return jsonify({'error': 'Duel not found'}), 404

    # Здесь логика обработки ответа в дуэли
    # Для простоты возвращаем заглушку
    is_correct = random.choice([True, False])

    if user_id == duel['player1_id']:
        new_score = duel['player1_score'] + (10 if is_correct else 0)
        conn.execute('UPDATE duels SET player1_score = ? WHERE id = ?', (new_score, duel_id))
    else:
        new_score = duel['player2_score'] + (10 if is_correct else 0)
        conn.execute('UPDATE duels SET player2_score = ? WHERE id = ?', (new_score, duel_id))

    new_round = duel['current_round'] + 1
    finished = new_round >= duel['max_rounds']

    if finished:
        # Определяем победителя
        p1_score = duel['player1_score'] if user_id == duel['player1_id'] else new_score
        p2_score = duel['player2_score'] if user_id != duel['player1_id'] else new_score

        if p1_score > p2_score:
            winner_id = duel['player1_id']
            # Обновляем ELO
            winner_new, loser_new = calculate_elo_change(
                duel['player1_id'],
                duel['player2_id'] or duel['player2_bot_id']
            )
        elif p2_score > p1_score:
            winner_id = duel['player2_id'] or -duel['player2_bot_id']
        else:
            winner_id = 0  # Ничья

        conn.execute('''UPDATE duels SET current_round = ?, status = "finished", 
                        winner_id = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?''',
                     (new_round, winner_id, duel_id))
    else:
        conn.execute('UPDATE duels SET current_round = ? WHERE id = ?', (new_round, duel_id))

    conn.commit()

    result = {
        'correct': is_correct,
        'player1_score': duel['player1_score'],
        'player2_score': duel['player2_score'],
        'round': new_round,
        'finished': finished
    }

    if finished:
        result['winner'] = 'player' if winner_id == user_id else 'opponent'

    conn.close()
    return jsonify(result)


# ============== API ЛИДЕРБОРДА ==============
@app.route('/leaderboard')
def leaderboard():
    conn = get_db()
    users = conn.execute('''
        SELECT username, xp, level, avatar_color, avatar_icon
        FROM users 
        ORDER BY xp DESC 
        LIMIT 20
    ''').fetchall()
    conn.close()

    return jsonify([dict(u) for u in users])


# ============== SOCKET.IO СОБЫТИЯ ==============
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user_id = session['user_id']
        join_room(f'user_{user_id}')
        update_user_online(user_id, True)
        emit('online_status', {'user_id': user_id, 'online': True}, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = session['user_id']
        update_user_online(user_id, False)
        emit('online_status', {'user_id': user_id, 'online': False}, broadcast=True)


@socketio.on('join_duel')
def handle_join_duel(data):
    duel_id = data.get('duel_id')
    join_room(f'duel_{duel_id}')


@socketio.on('duel_answer')
def handle_duel_answer(data):
    duel_id = data.get('duel_id')
    answer = data.get('answer')
    # Обработка ответа в реальном времени
    emit('opponent_answer', {'answer': answer}, room=f'duel_{duel_id}', include_self=False)


# ============== ЗАПУСК ==============
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app,
                debug=False,
                host='0.0.0.0',
                port=port,
                allow_unsafe_werkzeug=True)