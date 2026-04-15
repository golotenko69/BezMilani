from flask import Flask, render_template, request, jsonify, session, redirect
import json, os, random, time, threading, uuid
from game.generator import *
from game.scoring import calculate_score

app = Flask(__name__)
app.secret_key = "secret"

DATA_FILE = "data/users.json"
DUEL_DATA_FILE = "data/duels.json"
BOTS_FILE = "data/bots.json"
ROUND_TIME = 30

BOT_NAMES = ["NeuroBot", "QuantumMind", "LogicMaster", "BrainWave", "SynapseX",
             "CortexPrime", "NeuralNet", "DeepThink", "MindStorm", "Cerebro"]


def get_level(xp):
    return xp // 100 + 1


def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding='utf-8') as f:
        users = json.load(f)
    for u in users:
        if "xp" not in users[u]:
            users[u]["xp"] = 0
        if "elo" not in users[u]:
            users[u]["elo"] = 1200
        if "duel_wins" not in users[u]:
            users[u]["duel_wins"] = 0
        if "duel_losses" not in users[u]:
            users[u]["duel_losses"] = 0
        if "skin" not in users[u]:
            colors = ["#ef4444", "#f97316", "#fbbf24", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899"]
            users[u]["skin"] = random.choice(colors)
        if "avatar" not in users[u]:
            icons = ["fa-user-astronaut", "fa-user-ninja", "fa-user-secret", "fa-user-tie",
                     "fa-user-graduate", "fa-user-pilot", "fa-music", "fa-crown"]
            users[u]["avatar"] = {"color": users[u]["skin"], "icon": random.choice(icons)}
    return users


def save_users(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_duels():
    if not os.path.exists(DUEL_DATA_FILE):
        return {"active_duels": {}, "queue": []}
    with open(DUEL_DATA_FILE, "r", encoding='utf-8') as f:
        return json.load(f)


def save_duels(data):
    os.makedirs(os.path.dirname(DUEL_DATA_FILE), exist_ok=True)
    with open(DUEL_DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_bots():
    if not os.path.exists(BOTS_FILE):
        bots = {}
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
            bots[name] = {
                "name": name, "elo": elo, "difficulty": difficulty,
                "accuracy": accuracy, "wins": 0, "losses": 0,
                "skin": random.choice(colors)
            }
        save_bots(bots)
        return bots
    with open(BOTS_FILE, "r", encoding='utf-8') as f:
        return json.load(f)


def save_bots(data):
    os.makedirs(os.path.dirname(BOTS_FILE), exist_ok=True)
    with open(BOTS_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_random_bot():
    bots = load_bots()
    return random.choice(list(bots.values()))


def get_bot_by_elo(target_elo):
    bots = load_bots()
    best_bot = None
    min_diff = float('inf')
    for bot_name, bot_data in bots.items():
        diff = abs(bot_data["elo"] - target_elo)
        if diff < min_diff:
            min_diff = diff
            best_bot = bot_data
    return best_bot


def calculate_elo_change(winner_elo, loser_elo, k=32):
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))
    winner_new = round(winner_elo + k * (1 - expected_winner))
    loser_new = round(loser_elo + k * (0 - expected_loser))
    return winner_new, loser_new


def bot_answer_task(task, bot_data):
    correct_answer = str(task.get("a", ""))
    if random.random() > bot_data["accuracy"]:
        if task["type"] in ["math", "math_chain", "math_compare", "logic"]:
            try:
                return str(int(correct_answer) + random.randint(-10, 10)), False
            except:
                return "0", False
        return "wrong", False
    return correct_answer, True


def generate_feedback(correct, wrong, score, mode):
    if wrong == 0:
        return "🌟 Идеально!"
    elif wrong <= 3:
        return "👍 Хорошо!"
    return "🎮 Продолжай!"


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        avatar_color = request.form.get("avatar_color", "#ef4444")
        avatar_icon = request.form.get("avatar_icon", "fa-user-astronaut")

        users = load_users()
        if username not in users:
            colors = ["#ef4444", "#f97316", "#fbbf24", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899"]
            users[username] = {
                "records": {
                    "math": 0, "math_chain": 0, "math_compare": 0,
                    "memory_digits": 0, "memory_words": 0, "memory_positions": 0,
                    "logic_sequences": 0, "logic_analogies": 0, "logic_sets": 0
                },
                "history": [], "xp": 0, "perfect_runs": 0, "max_combo": 0,
                "achievements": [], "elo": 1200, "duel_wins": 0, "duel_losses": 0,
                "skin": random.choice(colors),
                "avatar": {"color": avatar_color, "icon": avatar_icon}
            }
            save_users(users)
        session["user"] = username
        return redirect("/menu")
    return render_template("login.html")


@app.route("/menu")
def menu():
    if "user" not in session:
        return redirect("/")
    users = load_users()
    user = users[session["user"]]
    return render_template("menu.html", user=user, name=session["user"],
                           level=get_level(user.get("xp", 0)), xp=user.get("xp", 0))


@app.route("/duel")
def duel():
    if "user" not in session:
        return redirect("/")
    return render_template("duel.html", name=session["user"])


@app.route("/api/duel/queue", methods=["POST"])
def duel_queue():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session["user"]
    users = load_users()
    duels = load_duels()
    user_elo = users[username].get("elo", 1200)
    user_skin = users[username].get("skin", "#ef4444")

    if "queue" not in duels:
        duels["queue"] = []
    if "active_duels" not in duels:
        duels["active_duels"] = {}

    # Удаляем пользователя из очереди если он там есть
    duels["queue"] = [p for p in duels["queue"] if p.get("username") != username]

    # Проверяем, нет ли других игроков
    if len(duels["queue"]) > 0:
        opponent = duels["queue"].pop(0)
        opponent_name = opponent["username"]
        opponent_data = users.get(opponent_name, {"elo": 1200, "skin": "#3b82f6"})

        duel_id = f"duel_{int(time.time())}_{username}_{opponent_name}"
        duels["active_duels"][duel_id] = {
            "id": duel_id,
            "player": username,
            "player_elo": user_elo,
            "player_skin": user_skin,
            "player_score": 0,
            "opponent": opponent_name,
            "opponent_elo": opponent_data.get("elo", 1200),
            "opponent_skin": opponent_data.get("skin", "#3b82f6"),
            "opponent_score": 0,
            "round": 0,
            "max_rounds": 5,
            "status": "active",
            "is_bot": False,
            "current_task": None
        }
        save_duels(duels)
        return jsonify({
            "status": "matched",
            "duel_id": duel_id,
            "player": {"name": username, "elo": user_elo, "skin": user_skin},
            "opponent": {"name": opponent_name, "elo": opponent_data.get("elo", 1200),
                         "skin": opponent_data.get("skin", "#3b82f6")}
        })

    # Добавляем в очередь
    duels["queue"].append({
        "username": username,
        "elo": user_elo,
        "joined_at": time.time()
    })
    save_duels(duels)

    # Проверяем, не ждёт ли кто-то больше 5 секунд
    for i, p in enumerate(duels["queue"]):
        if p["username"] == username:
            wait_time = time.time() - p["joined_at"]
            if wait_time > 5:
                # Подключаем бота
                duels["queue"].pop(i)
                bot = get_bot_by_elo(user_elo)
                duel_id = f"duel_{int(time.time())}_{username}_{bot['name']}"
                duels["active_duels"][duel_id] = {
                    "id": duel_id,
                    "player": username,
                    "player_elo": user_elo,
                    "player_skin": user_skin,
                    "player_score": 0,
                    "opponent": bot["name"],
                    "opponent_elo": bot["elo"],
                    "opponent_skin": bot["skin"],
                    "opponent_score": 0,
                    "round": 0,
                    "max_rounds": 5,
                    "status": "active",
                    "is_bot": True,
                    "bot_data": bot,
                    "current_task": None
                }
                save_duels(duels)
                return jsonify({
                    "status": "matched",
                    "duel_id": duel_id,
                    "player": {"name": username, "elo": user_elo, "skin": user_skin},
                    "opponent": {"name": bot["name"], "elo": bot["elo"], "skin": bot["skin"]}
                })
            break

    return jsonify({"status": "waiting", "queue_length": len(duels["queue"])})


@app.route("/api/duel/<duel_id>/status")
def duel_status(duel_id):
    duels = load_duels()
    if duel_id not in duels["active_duels"]:
        return jsonify({"error": "Duel not found"}), 404

    duel = duels["active_duels"][duel_id]
    return jsonify({
        "player": {"name": duel["player"], "score": duel["player_score"], "elo": duel["player_elo"],
                   "skin": duel["player_skin"]},
        "opponent": {"name": duel["opponent"], "score": duel["opponent_score"], "elo": duel["opponent_elo"],
                     "skin": duel["opponent_skin"]},
        "round": duel["round"],
        "max_rounds": duel["max_rounds"],
        "status": duel["status"],
        "winner": duel.get("winner")
    })


@app.route("/api/duel/<duel_id>/task")
def duel_task(duel_id):
    duels = load_duels()
    if duel_id not in duels["active_duels"]:
        return jsonify({"error": "Duel not found"}), 404

    duel = duels["active_duels"][duel_id]

    if duel.get("current_task") and duel["current_task"].get("player_answered"):
        return jsonify({"waiting": True})

    # Генерируем задание
    task_type = random.choice(["math", "math_chain", "math_compare", "logic"])
    if task_type == "math":
        task = generate_math()
    elif task_type == "math_chain":
        task = generate_math_chain()
    elif task_type == "math_compare":
        task = generate_math_compare()
    else:
        task = generate_logic()

    duel["current_task"] = {
        "task": task,
        "player_answered": False,
        "opponent_answered": False
    }
    save_duels(duels)

    return jsonify({"task": task})


@app.route("/api/duel/<duel_id>/answer", methods=["POST"])
def duel_answer(duel_id):
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    username = session["user"]
    data = request.json
    answer = str(data.get("answer", "")).strip().lower()

    duels = load_duels()
    if duel_id not in duels["active_duels"]:
        return jsonify({"error": "Duel not found"}), 404

    duel = duels["active_duels"][duel_id]

    if not duel.get("current_task"):
        return jsonify({"error": "No active task"}), 400

    task = duel["current_task"]["task"]
    correct_answer = str(task.get("a", "")).lower()
    is_correct = answer == correct_answer

    # Очки игрока
    if is_correct:
        duel["player_score"] += 10

    duel["current_task"]["player_answered"] = True
    duel["current_task"]["player_correct"] = is_correct

    # Соперник (бот или другой игрок) отвечает
    opponent_correct = False
    if duel.get("is_bot"):
        bot_data = duel["bot_data"]
        opponent_correct = random.random() < bot_data["accuracy"]
    else:
        opponent_correct = random.random() < 0.7  # Для реальных игроков пока случайно

    if opponent_correct:
        duel["opponent_score"] += 10

    duel["current_task"]["opponent_answered"] = True
    duel["current_task"]["opponent_correct"] = opponent_correct

    duel["round"] += 1

    # Проверяем завершение
    finished = False
    winner = None

    if duel["round"] >= duel["max_rounds"]:
        duel["status"] = "finished"
        finished = True

        users = load_users()
        bots = load_bots()

        if duel["player_score"] > duel["opponent_score"]:
            winner = "player"
            if username in users:
                users[username]["duel_wins"] = users[username].get("duel_wins", 0) + 1
                new_player_elo, new_opponent_elo = calculate_elo_change(duel["player_elo"], duel["opponent_elo"])
                users[username]["elo"] = new_player_elo

                if duel.get("is_bot"):
                    bot_name = duel["opponent"]
                    if bot_name in bots:
                        bots[bot_name]["elo"] = new_opponent_elo
                        bots[bot_name]["losses"] = bots[bot_name].get("losses", 0) + 1
                else:
                    opponent_name = duel["opponent"]
                    if opponent_name in users:
                        users[opponent_name]["elo"] = new_opponent_elo
                        users[opponent_name]["duel_losses"] = users[opponent_name].get("duel_losses", 0) + 1
        else:
            winner = "opponent"
            if username in users:
                users[username]["duel_losses"] = users[username].get("duel_losses", 0) + 1
                new_opponent_elo, new_player_elo = calculate_elo_change(duel["opponent_elo"], duel["player_elo"])
                users[username]["elo"] = new_player_elo

                if duel.get("is_bot"):
                    bot_name = duel["opponent"]
                    if bot_name in bots:
                        bots[bot_name]["elo"] = new_opponent_elo
                        bots[bot_name]["wins"] = bots[bot_name].get("wins", 0) + 1
                else:
                    opponent_name = duel["opponent"]
                    if opponent_name in users:
                        users[opponent_name]["elo"] = new_opponent_elo
                        users[opponent_name]["duel_wins"] = users[opponent_name].get("duel_wins", 0) + 1

        duel["winner"] = winner
        save_users(users)
        if duel.get("is_bot"):
            save_bots(bots)

    duel["current_task"] = None
    save_duels(duels)

    return jsonify({
        "correct": is_correct,
        "player_score": duel["player_score"],
        "opponent_score": duel["opponent_score"],
        "round": duel["round"],
        "finished": finished,
        "winner": winner
    })


@app.route("/api/duel/<duel_id>/cancel", methods=["POST"])
def duel_cancel(duel_id):
    duels = load_duels()
    if duel_id in duels["active_duels"]:
        del duels["active_duels"][duel_id]
        save_duels(duels)
    return jsonify({"status": "cancelled"})


@app.route("/game/<mode>")
def game(mode):
    if "user" not in session:
        return redirect("/")
    session['mode'] = mode
    session['score'] = 0
    session['combo'] = 1
    session['max_combo'] = 1
    session['correct'] = 0
    session['wrong'] = 0
    session['times'] = []
    names = {
        "math": "⚡ Быстрый счёт", "math_chain": "🔗 Цепочки", "math_compare": "⚖️ Сравнение",
        "memory_digits": "🔢 Цифры", "memory_words": "📝 Слова", "memory_positions": "🗺️ Позиции",
        "logic_sequences": "📊 Последовательности", "logic_analogies": "🔄 Аналогии", "logic_sets": "🎯 Множества"
    }
    return render_template("game.html", mode=mode, title=names.get(mode, "Игра"), round_time=ROUND_TIME)


@app.route("/task/<mode>")
def task(mode):
    tasks = {
        "math": generate_math, "math_chain": generate_math_chain, "math_compare": generate_math_compare,
        "memory_digits": generate_memory_digits, "memory_words": generate_memory_words,
        "memory_positions": generate_memory_positions, "logic_sequences": generate_logic,
        "logic_analogies": generate_logic_analogies, "logic_sets": generate_logic_sets
    }
    return jsonify(tasks.get(mode, lambda: {"error": "Unknown mode"})())


@app.route("/check", methods=["POST"])
def check():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
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


@app.route("/result")
def result():
    if "user" not in session:
        return redirect("/")
    users = load_users()
    user = users[session['user']]
    mode = session.get('mode', 'math')
    score = session.get('score', 0)
    correct = session.get('correct', 0)
    wrong = session.get('wrong', 0)
    times = session.get('times', [])
    max_combo = session.get('max_combo', 1)

    is_record = False
    if mode in user['records'] and score > user['records'][mode]:
        user['records'][mode] = score
        is_record = True
    elif mode not in user['records']:
        user['records'][mode] = score
        is_record = True

    user['history'] = user.get('history', []) + [score]
    if max_combo > user.get('max_combo', 0):
        user['max_combo'] = max_combo
    if wrong == 0 and correct > 0:
        user['perfect_runs'] = user.get('perfect_runs', 0) + 1
    user['xp'] = user.get('xp', 0) + max(score // 2, 1)
    save_users(users)

    total = correct + wrong
    accuracy = round((correct / total * 100) if total > 0 else 0, 1)
    avg_time = round(sum(times) / len(times), 2) if times else 0
    feedback = generate_feedback(correct, wrong, score, mode)

    for k in ['mode', 'score', 'combo', 'max_combo', 'correct', 'wrong', 'times']:
        session.pop(k, None)

    return render_template("result.html", score=score, correct=correct, wrong=wrong,
                           accuracy=accuracy, avg_time=avg_time, mode=mode,
                           xp_gain=max(score // 2, 1), is_record=is_record,
                           max_combo=max_combo, feedback=feedback)


@app.route("/leaderboard")
def leaderboard():
    users = load_users()
    rating = [{"name": n, "xp": d.get("xp", 0), "level": get_level(d.get("xp", 0))}
              for n, d in users.items()]
    rating.sort(key=lambda x: x["xp"], reverse=True)
    return jsonify(rating[:10])


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    app.run(debug=True, host='127.0.0.1', port=5000)