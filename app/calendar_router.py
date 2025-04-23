from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from app.admin import user_is_admin
from app.database.sqlite_db import (
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    add_waiter,
    get_shifts_for,
    add_shift,
    set_shift_hours
)
from app.utils.calendar import make_calendar

calendar_router = Router()

# Состояния для ввода имени официанта
class FillName(StatesGroup):
    waiting_for_name = State()

# Состояния для админа при вводе часов
class AdminStates(StatesGroup):
    waiting_hours = State()

@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    """
    Точка входа: пользователь вводит /calendar.
    Если официанта нет в БД — просим ввести имя.
    Иначе показываем календарь.
    """
    waiter = get_waiter_by_tg(message.from_user.id)
    if not waiter:
        # создаём запись официанта без имени
        add_waiter(message.from_user.id)
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return

    waiter_id, name = waiter
    if not name:
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return

    # показываем текущий календарь
    await _show_calendar(message, waiter_id)

@calendar_router.message(FillName.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """
    Получаем имя официанта, сохраняем и показываем календарь.
    """
    name = message.text.strip()
    tg_id = message.from_user.id
    # обновляем имя официанта
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg_id))
    base.commit()

    await message.answer(f"Спасибо, {name}! Вот ваш личный календарь:")
    waiter_id = get_waiter_id_by_tg(tg_id)
    await state.clear()
    await _show_calendar(message, waiter_id)

async def _show_calendar(event_source, waiter_id: int, year: int = None, month: int = None):
    """
    Отрисовка inline-календаря с пометками дней, где есть смены.
    """
    today = datetime.today()
    year = year or today.year
    month = month or today.month
    shifts = get_shifts_for(waiter_id)  # dict: {date_str: {"hours": ..., "tasks": ...}}
    kb = make_calendar(year, month, set(shifts.keys()))
    await event_source.answer("Выберите дату записи:", reply_markup=kb)

# Хендлер для админа: установка смены и запрос часов
@calendar_router.callback_query(lambda q: user_is_admin(q.from_user.id) and q.data.startswith("CAL_DAY"))
async def admin_set_shift(query: CallbackQuery, state: FSMContext):
    """
    Админ нажал на конкретную дату — создаём смену и просим ввести часы.
    """
    _, date_str = query.data.split("|")  # "CAL_DAY|YYYY-MM-DD"
    waiter_id = get_waiter_id_by_tg(query.from_user.id)
    # создаём смену, если ещё не было
    add_shift(waiter_id, date_str)
    await query.message.edit_text(
        f"Смена на {date_str} добавлена!\nПожалуйста, введите, сколько часов отработано:",
    )
    # сохраняем данные в state
    await state.update_data(admin_shift={"waiter_id": waiter_id, "date": date_str})
    await state.set_state(AdminStates.waiting_hours)

@calendar_router.message(AdminStates.waiting_hours)
async def process_admin_hours(message: Message, state: FSMContext):
    """
    Админ вводит количество часов — сохраняем и подтверждаем.
    """
    text = message.text.strip().replace(",", ".")
    try:
        hours = float(text)
    except ValueError:
        await message.answer("Нужно ввести число. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    ws = data.get("admin_shift", {})
    waiter_id = ws.get("waiter_id")
    date_str = ws.get("date")
    set_shift_hours(waiter_id, date_str, hours)
    await message.answer(f"Часы сохранены: {hours} ч. для смены {date_str}.")
    await state.clear()

# Общий хендлер для навигации по календарю и просмотра смен пользователя
@calendar_router.callback_query(F.data.startswith("CAL_"))
async def calendar_handler(query: CallbackQuery):
    """
    Обработка переходов между месяцами и кликов по дню для обычного официанта.
    """
    parts = query.data.split("|")
    action = parts[0]
    waiter_id = get_waiter_id_by_tg(query.from_user.id)

    # отмена
    if action == "CAL_CANCEL":
        await query.message.delete()
        return

    # листаем месяц
    if action in ("CAL_PREV", "CAL_NEXT"):
        year, month = map(int, parts[1:])
        if action == "CAL_PREV":
            month -= 1
            if month == 0:
                month, year = 12, year - 1
        else:
            month += 1
            if month == 13:
                month, year = 1, year + 1
        shifts = get_shifts_for(waiter_id)
        await query.message.edit_text(
            "Выберите дату записи:",
            reply_markup=make_calendar(year, month, set(shifts.keys()))
        )
        return

    # клик по дню обычным пользователем
    if action == "CAL_DAY":
        date_str = parts[1]
        shifts = get_shifts_for(waiter_id)
        info = shifts.get(date_str)
        if info:
            hours = info.get("hours", 0)
            tasks = info.get("tasks", "")
            text = (
                f"Смена на {date_str}:\n"
                f"⏱ Отработано: {hours} ч.\n"
                f"📋 Задачи:\n{tasks or 'нет задач'}"
            )
        else:
            text = "На эту дату нет смен и задач."
        await query.message.delete()
        await query.message.answer(text)
