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

# --- FSM for waiter onboarding ---
class WaiterOnboard(StatesGroup):
    ENTER_NAME = State()

# --- Command to open personal calendar ---
@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    """
    Точка входа для официанта: показывает его личный календарь.
    Если официант новый — запрашивает имя.
    """
    record = get_waiter_by_tg(message.from_user.id)
    if not record:
        # Новый официант, добавляем без имени
        add_waiter(message.from_user.id)
        await message.answer("Пожалуйста, введите ваше имя:")
        await state.set_state(WaiterOnboard.ENTER_NAME)
        return
    waiter_id, name = record
    if not name:
        await message.answer("Пожалуйста, введите ваше имя:")
        await state.set_state(WaiterOnboard.ENTER_NAME)
        return
    # Отображаем календарь
    await _show_personal_calendar(message, waiter_id)

@calendar_router.message(F.state(WaiterOnboard.ENTER_NAME))
async def process_onboard_name(message: Message, state: FSMContext):
    """
    Сохраняем введённое имя и показываем календарь.
    """
    name = message.text.strip()
    tg_id = message.from_user.id
    # Обновляем имя в базе
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg_id))
    base.commit()
    await message.answer(f"Спасибо, {name}! Вот ваш календарь:")
    waiter_id = get_waiter_id_by_tg(tg_id)
    await state.clear()
    await _show_personal_calendar(message, waiter_id)

async def _show_personal_calendar(source, waiter_id: int, year: int = None, month: int = None):
    """
    Формирует и отправляет личный календарь официанту.
    """
    today = datetime.today()
    year = year or today.year
    month = month or today.month
    shifts = get_shifts_for(waiter_id)  # dict {date: {'hours', 'tasks'}}
    marked = set(shifts.keys())
    cal_markup = make_calendar(year, month, marked)
    await source.answer("Ваш личный календарь. Выберите дату:", reply_markup=cal_markup)

# --- Handler for waiter navigation and selecting day ---
@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_"))
async def personal_calendar_handler(query: CallbackQuery, state: FSMContext):
    """
    Обработка нажатий обычного официанта на календарь.
    Поддерживает prev/next и выбор дня.
    """
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
                month = 12
                year -= 1
        else:
            month += 1
            if month == 13:
                month = 1
                year += 1
        shifts = get_shifts_for(waiter_id)
        await query.message.edit_text(
            "Ваш личный календарь. Выберите дату:",
            reply_markup=make_calendar(year, month, set(shifts.keys()))
        )
        return
    # Выбор дня
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
            text = "На эту дату нет смен."
        await query.message.delete()
        await query.message.answer(text)
