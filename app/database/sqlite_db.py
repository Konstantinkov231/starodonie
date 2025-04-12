import sqlite3
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

SQL = Router()

def sql_start():
    """
    Инициализируем (или обновляем) базу данных и создаём нужные таблицы,
    если их ещё нет.
    """
    global base, cur
    base = sqlite3.connect('user.db')
    cur = base.cursor()

    # Таблица для данных, собранных при /start
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users_start (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            username TEXT,
            start_date TEXT
        )
    ''')

    # Таблица для карточек гостей
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

    # Новая таблица для официантов (waiters)
    cur.execute('''
            CREATE TABLE IF NOT EXISTS waiters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE
            )
        ''')

    # Таблица для результатов теста
    cur.execute('''
           CREATE TABLE IF NOT EXISTS test_results (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               tg_id INTEGER,
               score INTEGER,
               total INTEGER,
               timestamp TEXT
           )
       ''')

    base.commit()

def tG_id(user_id: int):
    # Обновляем поле tg_id в guest_cards для последней добавленной записи
    cur.execute("UPDATE guest_cards SET tg_id = ? WHERE id = (SELECT MAX(id) FROM guest_cards)", (user_id,))
    base.commit()

# =============== Функции для таблицы users_start ===============

def add_user_start(tg_id: int, username: str):
    """
    Сохраняем запись о том, что пользователь начал работу с ботом.
    """
    # Пример: записываем дату и время
    start_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('''
        INSERT INTO users_start (tg_id, username, start_date)
        VALUES (?, ?, ?)
    ''', (tg_id, username, start_date))
    base.commit()

def get_all_starts():
    """
    Получаем все записи из таблицы users_start.
    """
    cur.execute("SELECT * FROM users_start")
    return cur.fetchall()

# =============== Функции для таблицы guest_cards ===============

async def sql_add_guest_card(state):
    """
    Сохраняем карточку гостя из FSM-состояния.
    Предполагается, что в state лежат поля:
    name, number, photo, food, alerg.
    """
    data = await state.get_data()
    cur.execute('''
        INSERT INTO guest_cards (name, phone, photo, food, alerg)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data.get("name"),
        data.get("number"),
        data.get("photo"),
        data.get("food"),
        data.get("alerg"),
    ))
    base.commit()

def get_all_guest_cards():
    """
    Получаем все записи из таблицы guest_cards.
    """
    cur.execute("SELECT * FROM guest_cards")
    return cur.fetchall()

# Функция для таблицы waiters
def add_waiter(tg_id: int):
    try:
        cur.execute("INSERT OR IGNORE INTO waiters (tg_id) VALUES (?)", (tg_id,))
        base.commit()
        print(f"Официант с tg_id {tg_id} успешно добавлен.")
    except Exception as e:
        print("Ошибка при добавлении официанта:", e)

# Функция для тестовых результатов
def add_test_result(tg_id: int, score: int, total: int):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('''
        INSERT INTO test_results (tg_id, score, total, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (tg_id, score, total, timestamp))
    base.commit()

def get_all_test_results():
    cur.execute("SELECT * FROM test_results")
    return cur.fetchall()

def get_all_test_results_with_username():
    # Объединяем таблицы test_results и users_start по tg_id
    cur.execute('''
        SELECT tr.id, tr.tg_id, us.username, tr.score, tr.total, tr.timestamp
        FROM test_results AS tr
        LEFT JOIN users_start AS us ON tr.tg_id = us.tg_id
        ORDER BY tr.timestamp DESC
    ''')
    return cur.fetchall()

def clear_test_results():
    """
    Удаляет все записи из таблицы тестовых результатов
    и возвращает количество удалённых строк.
    """
    cur.execute("DELETE FROM test_results")
    base.commit()
    return cur.rowcount  # Вернёт число удалённых строк

# =============== Пример хендлера для /get_users (отладочный) ===============

@SQL.message(Command('get_users'))
async def get_users(message: Message):
    """
    Команда /get_users выводит информацию из таблицы guest_cards.
    Вместо вывода file_id фотографии, бот отправляет саму фотографию с подписью.
    """
    cur.execute("SELECT * FROM guest_cards")
    guest_cards = cur.fetchall()
    starts = get_all_starts()
    text = "=== Таблица users_start ===\n"
    for row in starts:
        # row: (id, tg_id, username, start_date)
        text += f"ID={row[0]}, TG_ID={row[1]}, USERNAME={row[2]}, START={row[3]}\n"

    if not guest_cards:
        await message.answer("База данных пуста.")
    else:
        for card in guest_cards:
            # Предполагается, что структура: (id, tg_id, name, phone, photo, food, alerg)
            caption = (
                f"Имя: {card[2]}\n"
                f"Номер: {card[3]}\n"
                f"Любимая еда: {card[5]}\n"
                f"Аллергии: {card[6]}"
            )
            # Отправляем фотографию с подписью
            await message.answer_photo(photo=card[4], caption=caption)

@SQL.message(Command('searchguest'))
async def search_guest(message: Message):
    """
    Команда /searchguest принимает поисковый запрос (имя или номер телефона) и ищет гостя в таблице guest_cards.
    Пример использования: /searchguest Иван или /searchguest 1234567890
    """
    # Извлекаем аргументы команды через partition
    query = message.text.partition(' ')[2].strip()
    if not query:
        await message.answer("Использование: /searchguest <имя или номер телефона>")
        return

    # Формируем запрос с поиском по имени и номеру (с использованием LIKE)
    sql_query = "SELECT * FROM guest_cards WHERE name LIKE ? OR phone LIKE ?"
    like_query = f"%{query}%"
    cur.execute(sql_query, (like_query, like_query))
    results = cur.fetchall()

    if not results:
        await message.answer("Гость не найден.")
    else:
        for card in results:
            # Структура карточки: (id, tg_id, name, phone, photo, food, alerg)
            caption = (
                f"Имя: {card[2]}\n"
                f"Номер: {card[3]}\n"
                f"Любимая еда: {card[5]}\n"
                f"Аллергии: {card[6]}"
            )
            await message.answer_photo(photo=card[4], caption=caption)

def add_waiter(tg_id: int):
    """
    Добавляет Telegram ID официанта в таблицу waiters,
    если запись с таким tg_id отсутствует.
    """
    try:
        cur.execute("INSERT OR IGNORE INTO waiters (tg_id) VALUES (?)", (tg_id,))
        base.commit()
        print(f"Официант с tg_id {tg_id} успешно добавлен.")
    except Exception as e:
        print("Ошибка при добавлении официанта:", e)