import random


def generate_math():
    ops = ['+', '-', '*', '/']
    op = random.choice(ops)

    if op == '/':
        b = random.randint(2, 10)
        a = b * random.randint(2, 10)
    else:
        a = random.randint(10, 100)
        b = random.randint(2, 20)

    q = f"{a} {op} {b}"
    return {"type": "math", "q": q, "a": int(eval(q))}


def generate_math_chain():
    a = random.randint(5, 20)
    b = random.randint(2, 10)
    c = random.randint(1, 5)
    q = f"{a} + {b} * {c}"
    return {"type": "math", "q": q, "a": int(eval(q))}


def generate_math_compare():
    a = random.randint(2, 10)
    b = random.randint(2, 10)
    c = random.randint(2, 10)
    d = random.randint(2, 10)

    left = a * b
    right = c * d

    if left > right:
        answer = ">"
    elif left < right:
        answer = "<"
    else:
        answer = "="

    return {"type": "compare", "q": f"{a}×{b} ? {c}×{d}", "a": answer}


def generate_memory_digits(level=1):
    length = min(3 + level, 9)
    seq = [random.randint(0, 9) for _ in range(length)]
    return {"type": "memory", "seq": seq, "a": "".join(map(str, seq)), "level": level}


def generate_memory_words():
    words = ["кот", "дом", "лес", "сон", "мир", "шар", "лук", "рот", "нос", "глаз", "мяч", "стул", "стол", "книга", "ручка"]
    seq = random.sample(words, 3)
    return {"type": "memory_words", "seq": seq, "a": ",".join(seq)}


def generate_memory_positions():
    # Генерируем 4 уникальные позиции на сетке 3x3
    positions = []
    used = set()
    while len(positions) < 4:
        x = random.randint(0, 2)
        y = random.randint(0, 2)
        pos = f"{x},{y}"
        if pos not in used:
            used.add(pos)
            positions.append(pos)
    return {"type": "memory_positions", "seq": positions, "a": ",".join(positions)}


def generate_logic():
    pattern_type = random.choice(["add", "multiply", "alternate", "progressive", "power"])
    seq = []

    if pattern_type == "add":
        start = random.randint(1, 20)
        step = random.randint(2, 10)
        seq = [start + i * step for i in range(5)]
        answer = seq[-1]

    elif pattern_type == "multiply":
        start = random.randint(1, 5)
        mult = random.randint(2, 4)
        seq = [start]
        for _ in range(4):
            seq.append(seq[-1] * mult)
        answer = seq[-1]

    elif pattern_type == "alternate":
        start = random.randint(1, 10)
        seq = [start]
        for i in range(4):
            if i % 2 == 0:
                seq.append(seq[-1] + random.randint(2, 5))
            else:
                seq.append(seq[-1] * 2)
        answer = seq[-1]

    elif pattern_type == "progressive":
        start = random.randint(1, 10)
        seq = [start]
        inc = 1
        for _ in range(4):
            seq.append(seq[-1] + inc)
            inc += 1
        answer = seq[-1]

    else:
        start = random.randint(1, 3)
        seq = [start]
        for _ in range(4):
            seq.append(seq[-1] * 2)
        answer = seq[-1]

    return {"type": "logic", "seq": seq[:-1], "a": answer}


def generate_logic_analogies():
    analogies = [
        {"pair": "кошка : котенок", "question": "собака : ?", "options": ["щенок", "кот", "пес"], "answer": "щенок"},
        {"pair": "утро : завтрак", "question": "вечер : ?", "options": ["обед", "ужин", "сон"], "answer": "ужин"},
        {"pair": "зима : холодно", "question": "лето : ?", "options": ["жарко", "тепло", "солнце"], "answer": "жарко"},
        {"pair": "птица : летать", "question": "рыба : ?", "options": ["плавать", "ходить", "прыгать"], "answer": "плавать"},
        {"pair": "врач : лечить", "question": "учитель : ?", "options": ["учить", "строить", "петь"], "answer": "учить"}
    ]
    a = random.choice(analogies)
    return {"type": "analogy", "q": a["question"], "options": a["options"], "a": a["answer"]}


def generate_logic_sets():
    sets = [
        {"items": ["яблоко", "банан", "апельсин", "огурец"], "answer": "огурец"},
        {"items": ["машина", "автобус", "поезд", "велосипед"], "answer": "велосипед"},
        {"items": ["красный", "синий", "зеленый", "квадрат"], "answer": "квадрат"},
        {"items": ["кошка", "собака", "корова", "стол"], "answer": "стол"},
        {"items": ["ручка", "карандаш", "линейка", "яблоко"], "answer": "яблоко"}
    ]
    s = random.choice(sets)
    return {"type": "sets", "items": s["items"], "a": s["answer"]}


def generate_multitask():
    m = generate_math()
    s = [random.choice(['A', 'B', 'C']) for _ in range(5)]
    a2 = "yes" if s[-1] == s[-3] else "no"
    return {"type": "multi", "math_q": m['q'], "seq": s, "a": f"{m['a']}|{a2}"}