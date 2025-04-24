from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from app.admin import user_is_admin
from app.database.sqlite_db import (
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    add_waiter,
    get_shifts_for
)
from app.utils.calendar import make_calendar

calendar_router = Router()

# Состояния для ввода имени официанта
class FillName(StatesGroup):
    waiting_for_name = State()

# Состояния для официанта при работе с календарем (только просмотр)

# Точка входа: пользователь вводит /calendar
@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    """
    Запуск личного календаря официанта.
    Если нет записи в БД, просим ввести имя.
    """
    waiter = get_waiter_by_tg(message.from_user.id)
    if not waiter:
        add_waiter(message.from_user.id)
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return

    waiter_id, name = waiter
    if not name:
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return

    # Показать календарь официанта
    await _show_calendar(message, waiter_id)

@calendar_router.message(FillName.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    tg_id = message.from_user.id
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg_id))
    base.commit()
    await message.answer(f"Спасибо, {name}! Вот ваш личный календарь:")
    waiter_id = get_waiter_id_by_tg(tg_id)
    await state.clear()
    await _show_calendar(message, waiter_id)

async def _show_calendar(event_source, waiter_id: int, year: int = None, month: int = None):
    today = datetime.today()
    year = year or today.year
    month = month or today.month
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(year, month, set(shifts.keys()))
    await event_source.answer("Выберите дату записи:", reply_markup=kb)

# --- Обработчики только для официанта: навигация и просмотр кадастра ---
@calendar_router.callback_query(lambda q: not user_is_admin(q.from_user.id) and q.data.startswith("CAL_"))
async def calendar_handler(query: CallbackQuery, state: FSMContext):
    parts = query.data.split("|")
    action = parts[0]
    waiter_id = get_waiter_id_by_tg(query.from_user.id)

    # Отмена
    if action == "CAL_CANCEL":
        await query.message.delete()
        return

    # Переход между месяцами
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

    # Просмотр смены
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
