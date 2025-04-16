import hashlib
import hmac
import io
import os
import sqlite3

from dotenv import load_dotenv
from flask import Flask, request, jsonify, session, render_template, redirect, url_for, send_file
from flask_session import Session
from openpyxl import Workbook

# Подтягиваем ENV-переменные (TOKEN, DATABASE_URL и т.п.)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'random_secret_key')

# Настройка сессий во Flask
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

DATABASE = os.path.join(os.path.dirname(__file__), '..', 'user.db')  # user.db лежит уровнем выше

# ----------------------------------------------------------------------------
# Вспомогательная функция для проверки Telegram авторизации
# ----------------------------------------------------------------------------
def check_telegram_auth(data: dict, bot_token: str) -> bool:
    """
    Проверяем подлинность данных, пришедших от Telegram WebApp.
    Документация: https://core.telegram.org/widgets/login#checking-authorization
    """
    # data: {
    #   "auth_date": "...",
    #   "first_name": "...",
    #   "id": 123456789,
    #   "last_name": "...",
    #   "photo_url": "...",
    #   "username": "...",
    #   "hash": "..."
    # }

    if "hash" not in data:
        return False

    received_hash = data["hash"]

    # Удаляем ключ 'hash' и формируем строку data_check_string
    data_check_arr = []
    for key, value in data.items():
        if key == "hash":
            continue
        data_check_arr.append(f"{key}={value}")
    data_check_arr.sort()
    data_check_string = "\n".join(data_check_arr)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return h == received_hash


# ----------------------------------------------------------------------------
# Вспомогательные функции для работы с базой данных
# ----------------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_role(tg_id: int) -> str:
    """
    Примитивная логика: проверяем, есть ли tg_id в таблице waiters, тогда роль "waiter",
    иначе — "admin". На практике надо расширять логику.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Пробуем найти в таблице waiters
    cur.execute("SELECT tg_id FROM waiters WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return "waiter"
    else:
        # Если не официант — допустим, админ
        return "admin"

def fetch_schedules():
    """
    Возвращаем все записи из таблицы schedules.
    Сама таблица: (id, user_id, date, working_hours, day_type)
    Для FullCalendar нужно поле start (YYYY-MM-DD), end (YYYY-MM-DD), color и т.д.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM schedules")
    rows = cur.fetchall()
    conn.close()

    events = []
    for row in rows:
        day_color = "#9E9E9E"  # серый по умолчанию
        if row["day_type"] == "fixed":
            day_color = "#4CAF50"  # зелёный
        elif row["day_type"] == "approximate":
            day_color = "#FFEB3B"  # жёлтый

        # FullCalendar событие
        events.append({
            "id": row["id"],
            "title": f"{row['working_hours'] or ''}",  # например "10:00-18:00"
            "start": row["date"],                     # дата в формате YYYY-MM-DD
            "color": day_color
        })
    return events

def add_schedule(user_id: int, date_str: str, hours: str, day_type: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO schedules (user_id, date, working_hours, day_type)
        VALUES (?, ?, ?, ?)
    """, (user_id, date_str, hours, day_type))
    conn.commit()
    conn.close()

def update_schedule(schedule_id: int, date_str: str, hours: str, day_type: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE schedules
        SET date = ?, working_hours = ?, day_type = ?
        WHERE id = ?
    """, (date_str, hours, day_type, schedule_id))
    conn.commit()
    conn.close()

def delete_schedule(schedule_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------------
# Роут для Telegram WebApp авторизации
# ----------------------------------------------------------------------------
@app.route("/login/telegram", methods=["POST"])
def telegram_login():
    data = request.json
    bot_token = os.getenv("TOKEN", "")  # Берём токен из .env
    if not check_telegram_auth(data, bot_token):
        return jsonify({"ok": False, "error": "Invalid auth"}), 403

    # Сохраняем данные пользователя в сессии
    tg_id = data.get("id")
    session["tg_id"] = tg_id
    session["username"] = data.get("username", "")
    # Определяем роль
    role = get_user_role(tg_id)
    session["role"] = role

    return jsonify({"ok": True, "role": role})

# ----------------------------------------------------------------------------
# Главная страница (официант или кто-то без авторизации)
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    # Если пользователь не залогинен, просим логиниться
    if "tg_id" not in session:
        return render_template("index.html", telegram_not_authorized=True)
    else:
        # Если залогинен, но роль waiter — показываем waiter-интерфейс
        role = session.get("role")
        if role == "waiter":
            return render_template("index.html", role="waiter")
        elif role == "admin":
            # Если админ, редиректим на /admin
            return redirect(url_for("admin_panel"))
        else:
            return render_template("index.html", role="unknown")

# ----------------------------------------------------------------------------
# Админ-панель
# ----------------------------------------------------------------------------
@app.route("/admin")
def admin_panel():
    if "tg_id" not in session or session.get("role") != "admin":
        return "Access denied", 403
    return render_template("admin.html")

# ----------------------------------------------------------------------------
# API-эндпоинты для работы с календарём
# ----------------------------------------------------------------------------
@app.route("/api/calendar/events")
def api_get_events():
    """
    Возвращает все события в формате JSON для FullCalendar.
    """
    events = fetch_schedules()
    return jsonify(events)

@app.route("/api/calendar/add", methods=["POST"])
def api_add_event():
    if "tg_id" not in session:
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.json
    date_str = data["date"]
    hours = data.get("hours", "")
    day_type = data.get("day_type", "approximate")  # по умолчанию approximate
    add_schedule(session["tg_id"], date_str, hours, day_type)
    return jsonify({"ok": True})

@app.route("/api/calendar/update", methods=["POST"])
def api_update_event():
    if "tg_id" not in session:
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.json
    schedule_id = data["id"]
    date_str = data["date"]
    hours = data.get("hours", "")
    day_type = data.get("day_type", "approximate")
    update_schedule(schedule_id, date_str, hours, day_type)
    return jsonify({"ok": True})

@app.route("/api/calendar/delete", methods=["POST"])
def api_delete_event():
    if "tg_id" not in session:
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    data = request.json
    schedule_id = data["id"]
    delete_schedule(schedule_id)
    return jsonify({"ok": True})

# ----------------------------------------------------------------------------
# Генерация Excel-отчёта
# ----------------------------------------------------------------------------
@app.route("/admin/report")
def download_report():
    if "tg_id" not in session or session.get("role") != "admin":
        return "Access denied", 403

    # Получаем расписание
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM schedules")
    rows = cur.fetchall()
    conn.close()

    # Формируем Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"

    # Заголовки
    headers = ["ID", "UserID (tg_id)", "Date", "Hours", "Type"]
    ws.append(headers)

    for row in rows:
        ws.append([row["id"], row["user_id"], row["date"], row["working_hours"], row["day_type"]])

    # Сохраняем в буфер
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    # Отправляем файл
    return send_file(
        file_stream,
        as_attachment=True,
        download_name="schedule_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ----------------------------------------------------------------------------
# Запуск
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # Можно запустить на порту 5000, например
    app.run(host="0.0.0.0", port=5000, debug=True)
