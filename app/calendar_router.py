# calendar_router.py
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from app.admin import is_admin
from app.database.sqlite_db import (
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    add_waiter,
    get_shifts_for
)
from app.utils.calendar import make_calendar

calendar_router = Router()

# --- FSM states for onboarding waiter ---
class WaiterOnboard(StatesGroup):
    ENTER_NAME = State()

# --- Command to open personal calendar ---
@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    # Check if waiter exists
    data = get_waiter_by_tg(message.from_user.id)
    if not data:
        # New waiter, add and ask name
        add_waiter(message.from_user.id)
        await message.answer("Пожалуйста, введите ваше имя:")
        await state.set_state(WaiterOnboard.ENTER_NAME)
        return
    waiter_id, name = data
    if not name:
        await message.answer("Пожалуйста, введите ваше имя:")
        await state.set_state(WaiterOnboard.ENTER_NAME)
        return
    # Show calendar
    await _show_personal_calendar(message, waiter_id)

@calendar_router.message(F.state(WaiterOnboard.ENTER_NAME))
async def process_onboard_name(message: Message, state: FSMContext):
    name = message.text.strip()
    tg_id = message.from_user.id
    # Update name in DB
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg_id))
    base.commit()
    await message.answer(f"Спасибо, {name}! Вот ваш календарь:")
    waiter_id = get_waiter_id_by_tg(tg_id)
    await state.clear()
    await _show_personal_calendar(message, waiter_id)

async def _show_personal_calendar(source, waiter_id: int, year: int=None, month: int=None):
    """
    Display personal calendar with marks on days with shifts.
    """
    today = datetime.today()
    year = year or today.year
    month = month or today.month
    shifts = get_shifts_for(waiter_id)
    marked = set(shifts.keys())
    cal_kb = make_calendar(year, month, marked)
    await source.answer("Ваш календарь, выберите дату:", reply_markup=cal_kb)

# --- Personal calendar handlers (non-admin) ---
@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_"))
async def personal_calendar_handler(query: CallbackQuery, state: FSMContext):
    parts = query.data.split("|")
    action = parts[0]
    waiter_id = get_waiter_id_by_tg(query.from_user.id)

    # Cancel
    if action == "CAL_CANCEL":
        await query.message.delete()
        return

    # Prev/Next month
    if action in ("CAL_PREV", "CAL_NEXT"):
        year, month = map(int, parts[1:])
        if action == "CAL_PREV":
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        else:
            month += 1
            if month == 13:
                month = 1
                year += 1
        shifts = get_shifts_for(waiter_id)
        await query.message.edit_text(
            "Выберите дату:",
            reply_markup=make_calendar(year, month, set(shifts.keys()))
        )
        return

    # Day selected
    if action == "CAL_DAY":
        date_str = parts[1]
        shifts = get_shifts_for(waiter_id)
        info = shifts.get(date_str)
        if info:
            hours = info.get("hours", 0)
            tasks = info.get("tasks", "")
            text = (
                f"Смена {date_str}:\n"
                f"⏱ Часы: {hours}\n"
                f"📋 Задачи: {tasks or 'нет задач'}"
            )
        else:
            text = "На эту дату нет смен."
        await query.message.delete()
        await query.message.answer(text)

# --- Admin calendar is handled in admin.py, no overlap here ---
