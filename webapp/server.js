from flask import Flask, render_template, jsonify
from datetime import datetime

app = Flask(__name__)

# Пример данных о рабочих сменах официантов.
# В реальном проекте, вероятно, данные будут извлекаться из базы данных.
# Формат даты ISO: "ГГГГ-ММ-ДДTHH:MM:SS"
schedule = [
    {
        "id": 1,
        "title": "Иван (Официант)",
        "start": "2025-04-16T08:00:00",
        "end": "2025-04-16T16:00:00"
    },
    {
        "id": 2,
        "title": "Пётр (Официант)",
        "start": "2025-04-16T12:00:00",
        "end": "2025-04-16T20:00:00"
    },
    {
        "id": 3,
        "title": "Мария (Официант)",
        "start": "2025-04-17T09:30:00",
        "end": "2025-04-17T17:30:00"
    }
]

@app.route('/')
def index():
    # Главная страница с календарем
    return render_template('index.html')

@app.route('/api/schedule')
def api_schedule():
    # Возвращаем данные в формате JSON для FullCalendar
    return jsonify(schedule)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
