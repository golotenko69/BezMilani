ACHIEVEMENTS = {
    "first_win": {
        "name": "🎯 Первая победа",
        "description": "Завершите первый раунд",
        "condition": lambda user: len(user.get("history", [])) >= 1
    },
    "math_master": {
        "name": "🧮 Математик",
        "description": "Наберите 1000 очков в математике",
        "condition": lambda user: user["records"].get("math", 0) >= 1000
    },
    "perfect_run": {
        "name": "💯 Идеально",
        "description": "Пройдите раунд без ошибок",
        "condition": lambda user: user.get("perfect_runs", 0) >= 1
    },
    "combo_king": {
        "name": "🔥 Король комбо",
        "description": "Достигните комбо x10",
        "condition": lambda user: user.get("max_combo", 0) >= 10
    }
}


def check_achievements(user_data):
    """Проверяет и выдаёт новые достижения"""
    if "achievements" not in user_data:
        user_data["achievements"] = []

    new_achievements = []
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id not in user_data["achievements"]:
            if ach["condition"](user_data):
                user_data["achievements"].append(ach_id)
                new_achievements.append(ach)

    return new_achievements