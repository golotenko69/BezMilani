def calculate_score(correct, time_taken, combo):
    """
    Вычисляет очки за один ответ
    """
    if correct:
        base_score = 10

        if time_taken <= 1:
            speed_bonus = 10
        elif time_taken <= 2:
            speed_bonus = 8
        elif time_taken <= 3:
            speed_bonus = 6
        elif time_taken <= 4:
            speed_bonus = 4
        elif time_taken <= 5:
            speed_bonus = 2
        else:
            speed_bonus = 0

        combo_multiplier = min(combo, 10)
        total = (base_score + speed_bonus) * combo_multiplier
        return total
    else:
        return -5


def apply_score(current_score, points):
    """
    Применяет изменение счёта, не позволяя уйти в минус
    """
    new_score = current_score + points
    return max(0, new_score)


def calculate_bonus_for_round(correct_answers, total_questions, avg_time):
    """
    Бонус за завершение раунда
    """
    bonus = 0

    if total_questions > 0:
        accuracy = correct_answers / total_questions
        if accuracy >= 0.9:
            bonus += 100
        elif accuracy >= 0.7:
            bonus += 50
        elif accuracy >= 0.5:
            bonus += 25

    if avg_time > 0:
        if avg_time <= 2:
            bonus += 50
        elif avg_time <= 3:
            bonus += 30
        elif avg_time <= 4:
            bonus += 15

    return bonus