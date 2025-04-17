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
    if "hash" not in data:
        return False

    received_hash = data.pop("hash")
    data_check_arr = [f"{key}={value}" for key, value in data.items()]
    data_check_arr.sort()
    data_check_string = "\n".join(data_check_arr)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return h == received_hash

# ----------------------------------------------------------------------------
# База данных
# ----------------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# другие вспомогательные функции работы с БД (get_user_role, fetch_schedules и т.д.)
# ... (оставляем без изменений) ...

# ----------------------------------------------------------------------------
# Маршруты
# ----------------------------------------------------------------------------
@app.route("/login/telegram", methods=["POST"])
def telegram_login():
    data = request.json.copy()
    bot_token = os.getenv("TOKEN", "")
    if not check_telegram_auth(data, bot_token):
        return jsonify({"ok": False, "error": "Invalid auth"}), 403

    session["tg_id"] = data.get("id")
    session["username"] = data.get("username", "")
    session["role"] = get_user_role(session["tg_id"])
    return jsonify({"ok": True, "role": session["role"]})

@app.route("/")
def index():
    if "tg_id" not in session:
        return render_template("index.html", telegram_not_authorized=True)
    role = session.get("role")
    if role == "waiter":
        return render_template("index.html", role="waiter")
    elif role == "admin":
        return redirect(url_for("admin_panel"))
    return render_template("index.html", role="unknown")

@app.route("/admin")
def admin_panel():
    if session.get("role") != "admin":
        return "Access denied", 403
    return render_template("admin.html")

@app.route("/api/calendar/events")
def api_get_events():
    return jsonify(fetch_schedules())

@app.route("/api/calendar/add", methods=["POST"])
def api_add_event():
    if "tg_id" not in session:
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    data = request.json
    add_schedule(session["tg_id"], data["date"], data.get("hours", ""), data.get("day_type", "approximate"))
    return jsonify({"ok": True})

@app.route("/api/calendar/update", methods=["POST"])
def api_update_event():
    if "tg_id" not in session:
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    data = request.json
    update_schedule(data["id"], data["date"], data.get("hours", ""), data.get("day_type", "approximate"))
    return jsonify({"ok": True})

@app.route("/api/calendar/delete", methods=["POST"])
def api_delete_event():
    if "tg_id" not in session:
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    delete_schedule(request.json.get("id"))
    return jsonify({"ok": True})

@app.route("/admin/report")
def download_report():
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM schedules").fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(["ID", "UserID", "Date", "Hours", "Type"])
    for row in rows:
        ws.append([row["id"], row["user_id"], row["date"], row["working_hours"], row["day_type"]])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return send_file(stream,
                     as_attachment=True,
                     download_name="schedule_report.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ----------------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # Отключаем debug и reloader, чтобы systemd корректно следил за процессом
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
