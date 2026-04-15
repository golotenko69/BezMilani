let currentAnswer = null;
let startTime = Date.now();

async function loadTask() {
    let mode = window.location.pathname.split("/").pop();

    let res = await fetch(`/task/${mode}`);
    let data = await res.json();

    let task = document.getElementById("task");
    task.innerText = "";

    // 🟢 МАТЕМАТИКА
    if (data.type === "math") {
        task.innerText = data.q;
        currentAnswer = data.a;
    }


    // 🟣 СРАВНЕНИЕ
    else if (data.type === "compare") {
        task.innerText = data.q + " (>, <, =)";
        currentAnswer = data.a;
    }

    // 🔵 ПАМЯТЬ
    else if (data.type === "memory") {
        task.innerText = data.seq.join(" ");
        currentAnswer = data.a;

        setTimeout(() => {
            task.innerText = "???";
        }, 2000);
    }

    // 🟡 ЛОГИКА
    else if (data.type === "logic") {
        task.innerText = data.seq.join(", ") + ", ?";
        currentAnswer = data.a;
    }

    // 🔥 2-BACK
    else if (data.type === "2back") {
        task.innerText = data.seq.join(" ");
        currentAnswer = data.a;
    }

    // 🚀 MULTI
    else if (data.type === "multi") {
        task.innerText = data.math_q + " | " + data.seq.join(" ");
        currentAnswer = data.a;
    }

    // ❗ fallback (если что-то пошло не так)
    else {
        task.innerText = "Ошибка генерации";
        console.log("UNKNOWN TYPE:", data);
    }

    startTime = Date.now();
}

async function send() {
    let answer = document.getElementById("answer").value;
    let time = (Date.now() - startTime) / 1000;

    let res = await fetch("/check", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            answer: answer,
            correct: currentAnswer,
            time: time
        })
    });

    let data = await res.json();

document.getElementById("score").innerText = data.score;

let combo = data.combo;
let comboBox = document.getElementById("comboBox");
let comboText = document.getElementById("comboText");

comboText.innerText = "x" + combo;

// сброс классов
comboBox.className = "combo-box";

// уровни комбо
if (combo < 3) {
    comboBox.classList.add("combo-low");
}
else if (combo < 6) {
    comboBox.classList.add("combo-mid");
}
else if (combo < 10) {
    comboBox.classList.add("combo-high");
}
else {
    comboBox.classList.add("combo-god");
}

    animate(data.correct);

    document.getElementById("answer").value = "";
    loadTask();
}
comboBox.style.transform = "scale(1.2)";
setTimeout(() => comboBox.style.transform = "scale(1)", 150);

function animate(correct) {
    let body = document.body;

    if (correct) {
        body.style.background = "#064e3b";
    } else {
        body.style.background = "#7f1d1d";
    }

    setTimeout(() => body.style.background = "#0f172a", 200);
}
let timerInterval;
let timeLeft = 60; // ROUND_TIME

function startTimer() {
    timerInterval = setInterval(() => {
        timeLeft--;
        document.getElementById('timer').textContent = timeLeft;

        if (timeLeft <= 0) {
            endGame();
        }
    }, 1000);
}

function endGame() {
    clearInterval(timerInterval);
    window.location.href = '/result';
}

// Вызвать при загрузке
startTimer();

document.getElementById("answer").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        send();
    }
});



loadTask();