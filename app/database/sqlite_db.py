import logging
import sqlite3
from datetime import datetime

from aiogram import Router

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
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
    base = sqlite3.connect('starodonie.db')
    cur = base.cursor()
    if base:
        print("Database connected OK!")

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
            name TEXT DEFAULT "",
            employee_id INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    ''')

    # Migration: Add employee_id column if it doesn't exist
    try:
        cur.execute("ALTER TABLE waiters ADD COLUMN employee_id INTEGER")
        base.commit()
    except sqlite3.OperationalError:
        # Column already exists, ignore the error
        pass

    # Migration: Add foreign key constraint if not present
    try:
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA foreign_key_check")
        base.commit()
    except sqlite3.OperationalError:
        pass  # Foreign key already set or not supported in older SQLite

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

    # Таблица сотрудников (для часовки)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            role TEXT NOT NULL,
            rate FLOAT
        )
    ''')

    # Migration: Add rate column if it doesn't exist
    try:
        cur.execute("ALTER TABLE employees ADD COLUMN rate FLOAT")
        base.commit()
    except sqlite3.OperationalError as e:
        # If the column already exists, this will raise an error like "duplicate column name"; we can safely ignore it
        if "duplicate column name" not in str(e):
            raise  # Re-raise if it's a different error

    # Таблица учёта отработанных часов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS work_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            hours REAL NOT NULL,
            UNIQUE(employee_id, date),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
    ''')

    # tips
    cur.execute("""
            CREATE TABLE IF NOT EXISTS tips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waiter_id INTEGER,
                date TEXT,
                amount REAL,
                UNIQUE(waiter_id, date),
                FOREIGN KEY(waiter_id) REFERENCES waiters(id)
            )
        """)

    base.commit()

# ================== users_start ==================
def add_user_start(tg_id: int, username: str | None):
    cur.execute(
        "INSERT INTO users_start (tg_id, username, start_date) VALUES (?,?,?)",
        (tg_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
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
    cur = base.cursor()
    cur.execute("""
        SELECT w.id AS waiter_id, 
               COALESCE(e.first_name || ' ' || e.last_name, w.name) AS name, 
               s.date, 
               s.hours, 
               s.tasks
        FROM shifts s
        JOIN waiters w ON s.waiter_id = w.id
        LEFT JOIN employees e ON w.employee_id = e.id
        ORDER BY s.date
    """)
    return cur.fetchall()

# ─────────────────────────────────────────────
# TIPS  ← нужные функции!
# ─────────────────────────────────────────────
def add_tip(waiter_id: int, date: str, amount: float):
    """Добавить или обновить сумму чаевых за дату."""
    cur.execute(
        """
        INSERT INTO tips (waiter_id, date, amount)
        VALUES (?,?,?)
        ON CONFLICT(waiter_id, date)
        DO UPDATE SET amount=excluded.amount
        """,
        (waiter_id, date, amount),
    )
    base.commit()

def get_month_tips(waiter_id: int, ym: str) -> float:
    """Вернуть сумму чаевых за месяц (ym = 'YYYY-MM')."""
    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM tips WHERE waiter_id=? AND date LIKE ?",
        (waiter_id, f"{ym}-%"),
    )
    return cur.fetchone()[0]

def clear_month_tips(waiter_id: int, ym: str):
    """Обнулить чаевые за указанный месяц."""
    cur.execute(
        "DELETE FROM tips WHERE waiter_id=? AND date LIKE ?",
        (waiter_id, f"{ym}-%"),
    )
    base.commit()

# ================== employees ==================
def add_employee(last_name: str, first_name: str, role: str, rate: float = None):
    cur = base.cursor()
    cur.execute(
        "INSERT INTO employees (last_name, first_name, role, rate) VALUES (?, ?, ?, ?)",
        (last_name, first_name, role, rate)
    )
    base.commit()

def get_all_employees() -> list[tuple[int, str, str, str]]:
    """Возвращает список (id, last_name, first_name, role)."""
    cur.execute('SELECT id, last_name, first_name, role FROM employees')
    return cur.fetchall()

# ================== work_hours ==================
def set_work_hours(employee_id: int, date: str, hours: float):
    """Записать или обновить часы для сотрудника на дату."""
    cur.execute(
        'INSERT INTO work_hours (employee_id, date, hours) VALUES (?,?,?) '
        'ON CONFLICT(employee_id, date) DO UPDATE SET hours=excluded.hours',
        (employee_id, date, hours)
    )
    base.commit()

def get_work_hours(employee_id: int, date: str) -> float:
    """Вернуть часы (0.0, если нет записи)."""
    cur.execute(
        'SELECT hours FROM work_hours WHERE employee_id=? AND date=?',
        (employee_id, date)
    )
    row = cur.fetchone()
    return row[0] if row else 0.0

def get_all_work_hours_dates() -> list[str]:
    """Список всех дат, где есть часы (для отметок в календаре)."""
    cur.execute('SELECT DISTINCT date FROM work_hours')
    return [r[0] for r in cur.fetchall()]

def get_employee_by_id(emp_id: int):
    cur = base.cursor()
    cur.execute("SELECT id, last_name, first_name, role, rate FROM employees WHERE id = ?", (emp_id,))
    return cur.fetchone()

def set_waiter_name(tg_id: int, name: str):
    cur = base.cursor()
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg_id))
    base.commit()


def get_employees_with_shifts():
    global base
    if not base:
        sql_start()  # Initialize connection if not already done

    cur = base.cursor()
    # Query 1: Get waiters with their employee details (if linked)
    cur.execute("""
        SELECT 
            w.id AS waiter_id,
            COALESCE(e.first_name || ' ' || e.last_name, w.name, 'Без имени') AS name
        FROM waiters w
        LEFT JOIN employees e ON w.employee_id = e.id
        LEFT JOIN shifts s ON w.id = s.waiter_id
        GROUP BY w.id, name
    """)
    waiters_result = []
    for row in cur.fetchall():
        try:
            waiters_result.append((row['waiter_id'], row['name']))
        except TypeError:
            waiters_result.append((row[0], row[1]))  # Fallback to tuple indices (0 for waiter_id, 1 for name)

    # Query 2: Get employees not linked to waiters
    cur.execute("""
        SELECT 
            e.id AS waiter_id,
            COALESCE(e.first_name || ' ' || e.last_name, 'Без имени') AS name
        FROM employees e
        LEFT JOIN waiters w ON e.id = w.employee_id
        LEFT JOIN shifts s ON e.id = s.waiter_id
        WHERE w.employee_id IS NULL
        GROUP BY e.id, name
    """)
    employees_result = []
    for row in cur.fetchall():
        try:
            employees_result.append((row['waiter_id'], row['name']))
        except TypeError:
            employees_result.append((row[0], row[1]))  # Fallback to tuple indices

    # Combine results and remove duplicates
    combined_result = waiters_result + employees_result
    unique_result = list(dict.fromkeys(combined_result))  # Remove duplicates based on (waiter_id, name)

    logger.debug("get_employees_with_shifts result: %s", unique_result)
    return unique_result