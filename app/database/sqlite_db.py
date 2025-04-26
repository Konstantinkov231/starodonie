import sqlite3
from datetime import datetime

from aiogram import Router

# Router для отладочных SQL-команд
SQL = Router()

# Глобальные переменные для базы и курсора
base: sqlite3.Connection | None = None
cur: sqlite3.Cursor | None = None

def sql_start():
    """
    Инициализируем базу и создаём необходимые таблицы.
    """
    global base, cur
    base = sqlite3.connect('user.db')
    cur = base.cursor()

    # Таблица пользователей (users_start)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users_start (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            username TEXT,
            start_date TEXT
        )
    ''')

    # Таблица карточек гостей (guest_cards)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS guest_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            name TEXT,
            phone TEXT,
            photo TEXT,
            food TEXT,
            alerg TEXT
        )
    ''')

    # Таблица официантов (waiters)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS waiters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            name TEXT DEFAULT ""
        )
    ''')

    # Таблица результатов тестов (test_results)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            tg_id INTEGER PRIMARY KEY,
            score INTEGER,
            total INTEGER,
            timestamp TEXT
        )
    ''')

    # Таблица смен/графика (shifts)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waiter_id INTEGER,
            date TEXT,
            hours REAL DEFAULT 0,
            tasks TEXT DEFAULT "",
            FOREIGN KEY (waiter_id) REFERENCES waiters(id)
        )
    ''')

    # tips
    cur.execute("""
            CREATE TABLE IF NOT EXISTS tips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waiter_id INTEGER, date TEXT, amount REAL,
                UNIQUE(waiter_id,date),
                FOREIGN KEY(waiter_id) REFERENCES waiters(id)
            )
        """)

    base.commit()

# ================== users_start ==================
def add_user_start(tg_id: int, username: str):
    """Сохраняем запись о запуске бота пользователем"""
    start_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        'INSERT INTO users_start (tg_id, username, start_date) VALUES (?, ?, ?)',
        (tg_id, username, start_date)
    )
    base.commit()

def get_all_starts():
    """Возвращает все записи из users_start"""
    cur.execute('SELECT * FROM users_start')
    return cur.fetchall()

# ================== guest_cards ==================
async def sql_add_guest_card(state):
    """Сохраняем карточку гостя из FSM Context"""
    data = await state.get_data()
    cur.execute(
        'INSERT INTO guest_cards (name, phone, photo, food, alerg) VALUES (?, ?, ?, ?, ?)',
        (
            data.get('name'),
            data.get('number'),
            data.get('photo'),
            data.get('food'),
            data.get('alerg'),
        )
    )
    base.commit()

def get_all_guest_cards():
    """Возвращает все карточки гостей"""
    cur.execute('SELECT * FROM guest_cards')
    return cur.fetchall()

def update_guest_tg_id(user_id: int):
    """Обновляем tg_id для последней карточки гостя"""
    cur.execute(
        'UPDATE guest_cards SET tg_id = ? WHERE id = (SELECT MAX(id) FROM guest_cards)',
        (user_id,)
    )
    base.commit()

# ================== waiters ==================
def add_waiter(tg_id: int):
    """Добавляем официанта по tg_id, если ещё нет"""
    cur.execute(
        'INSERT OR IGNORE INTO waiters (tg_id) VALUES (?)',
        (tg_id,)
    )
    base.commit()

def get_all_waiters():
    """Возвращает список tg_id всех официантов"""
    cur.execute('SELECT tg_id FROM waiters')
    return [row[0] for row in cur.fetchall()]

def get_waiter_by_tg(tg_id: int):
    """Возвращает (id, name) официанта по tg_id"""
    cur.execute('SELECT id, name FROM waiters WHERE tg_id = ?', (tg_id,))
    return cur.fetchone()

def get_waiter_id_by_tg(tg_id: int) -> int | None:
    """Возвращает id официанта по tg_id или None"""
    row = get_waiter_by_tg(tg_id)
    return row[0] if row else None

# ================== test_results ==================
def add_test_result(tg_id: int, score: int, total: int):
    """Сохраняем или обновляем результат теста"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        'INSERT OR REPLACE INTO test_results (tg_id, score, total, timestamp) VALUES (?, ?, ?, ?)',
        (tg_id, score, total, timestamp)
    )
    base.commit()

def get_all_test_results_with_username():
    """Объединяет test_results с users_start, возвращает [(tg_id, username, score, total, timestamp), ...]"""
    cur.execute(
        '''
        SELECT tr.tg_id, us.username, tr.score, tr.total, tr.timestamp
        FROM test_results tr
        LEFT JOIN users_start us ON tr.tg_id = us.tg_id
        ORDER BY tr.timestamp DESC
        '''
    )
    return cur.fetchall()

def clear_test_results():
    """Очищает таблицу test_results"""
    cur.execute('DELETE FROM test_results')
    base.commit()
    return cur.rowcount

# ================== shifts ==================
def add_shift(waiter_id: int, date: str):
    """Создаёт запись смены, если её нет"""
    cur.execute(
        'INSERT OR IGNORE INTO shifts (waiter_id, date) VALUES (?, ?)',
        (waiter_id, date)
    )
    base.commit()

def set_shift_hours(waiter_id: int, date: str, hours: float):
    """Устанавливает количество часов для смены"""
    cur.execute(
        'UPDATE shifts SET hours = ? WHERE waiter_id = ? AND date = ?',
        (hours, waiter_id, date)
    )
    base.commit()

def set_shift_tasks(waiter_id: int, date: str, tasks: str):
    """Устанавливает задачи для смены"""
    cur.execute(
        'UPDATE shifts SET tasks = ? WHERE waiter_id = ? AND date = ?',
        (tasks, waiter_id, date)
    )
    base.commit()

def get_shifts_for(waiter_id: int) -> dict:
    """Возвращает словарь {date: {'hours': hours, 'tasks': tasks}}"""
    cur.execute(
        'SELECT date, hours, tasks FROM shifts WHERE waiter_id = ?',
        (waiter_id,)
    )
    return {row[0]: {'hours': row[1], 'tasks': row[2]} for row in cur.fetchall()}

def get_all_shifts():
    """Возвращает список [(name, date, hours, tasks), ...] для отчётов"""
    cur.execute(
        'SELECT w.name, s.date, s.hours, s.tasks FROM shifts s'
        ' JOIN waiters w ON s.waiter_id = w.id'
    )
    return cur.fetchall()
