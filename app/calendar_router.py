from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from app.database.sqlite_db import (
    add_waiter,
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    get_shifts_for,
    # админ-функции здесь не нужны
)
from app.utils.calendar import make_calendar

calendar_router = Router()

# Локальный список админов, чтобы не импортировать из admin.py и не порождать цикл
ADMIN_IDS = [2015462319, 1773695867]
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Состояния для ввода имени официанта
class FillName(StatesGroup):
    waiting_for_name = State()

@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    """
    /calendar → создаём официанта без имени или спрашиваем имя, если его нет.
    Иначе показываем календарь с его сменами.
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

    # Всё есть — показываем календарь
    await _show_calendar(message, waiter_id)

@calendar_router.message(FillName.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """
    После ввода имени сохраняем его и сразу показываем календарь.
    """
    name = message.text.strip()
    tg_id = message.from_user.id

    # напрямую обновляем имя в БД
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg_id))
    base.commit()

    await message.answer(f"Спасибо, {name}! Вот ваш личный календарь:")
    waiter_id = get_waiter_id_by_tg(tg_id)
    await state.clear()
    await _show_calendar(message, waiter_id)

async def _show_calendar(event_source, waiter_id: int, year: int = None, month: int = None):
    """
    Общая отрисовка inline-календаря для официанта.
    Навигация, отметки смен и Отмена.
    """
    today = datetime.today()
    year = year or today.year
    month = month or today.month

    shifts = get_shifts_for(waiter_id)  # { "YYYY-MM-DD": {...}, ... }
    kb = make_calendar(year, month, set(shifts.keys()))

    await event_source.answer("Выберите дату:", reply_markup=kb)

# Листание и выбор дня — ТОЛЬКО для НЕ-админов
@calendar_router.callback_query(
    lambda q: (not is_admin(q.from_user.id)) and q.data.startswith("CAL_PREV|")
)
async def prev_month(query: CallbackQuery):
    _, y, m = query.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0:
        y -= 1; m = 12
    waiter_id = get_waiter_id_by_tg(query.from_user.id)
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(y, m, set(shifts.keys()))
    await query.message.edit_text("Выберите дату:", reply_markup=kb)

@calendar_router.callback_query(
    lambda q: (not is_admin(q.from_user.id)) and q.data.startswith("CAL_NEXT|")
)
async def next_month(query: CallbackQuery):
    _, y, m = query.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13:
        y += 1; m = 1
    waiter_id = get_waiter_id_by_tg(query.from_user.id)
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(y, m, set(shifts.keys()))
    await query.message.edit_text("Выберите дату:", reply_markup=kb)

@calendar_router.callback_query(
    lambda q: (not is_admin(q.from_user.id)) and q.data == "CAL_CANCEL"
)
async def cancel_calendar(query: CallbackQuery):
    await query.message.delete()

@calendar_router.callback_query(
    lambda q: (not is_admin(q.from_user.id)) and q.data.startswith("CAL_DAY|")
)
async def show_shift_info(query: CallbackQuery):
    """
    Официант кликнул на дату — показываем его смену и задачи.
    """
    _, date_str = query.data.split("|", 1)
    waiter_id = get_waiter_id_by_tg(query.from_user.id)
    shifts = get_shifts_for(waiter_id)
    info = shifts.get(date_str)
    if info:
        hours = info.get("hours", 0)
        tasks = info.get("tasks", "")
        text = (
            f"📅 Смена на {date_str}\n"
            f"⏱️ Отработано: {hours} ч.\n"
            f"📋 Задачи:\n{tasks or '— нет задач'}"
        )
    else:
        text = "На эту дату нет смен и задач."
    await query.message.delete()
    await query.message.answer(text)
