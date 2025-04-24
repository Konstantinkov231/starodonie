# app/calendar_router.py

import os
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.sqlite_db import (
    add_waiter,
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    get_shifts_for,
)
from app.utils.calendar import make_calendar

calendar_router = Router()

# Локальный список админов, чтобы кнопки не мешались им
ADMIN_IDS = [2015462319, 1773695867]
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# FSM для ввода имени официанта
class FillName(StatesGroup):
    waiting_for_name = State()

# FSM для прогноза смены
class Forecast(StatesGroup):
    ChoosingDate        = State()
    ConfirmAvailability = State()

@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    waiter = get_waiter_by_tg(message.from_user.id)
    # Если новый официант или имя не задано
    if not waiter or not waiter[1]:
        if not waiter:
            add_waiter(message.from_user.id)
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return

    # Показываем календарь его смен
    waiter_id, _ = waiter
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    # Добавляем кнопку прогноза смены
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📅 Прогнозировать смену", callback_data="FORECAST_START")
    ])
    await message.answer("Ваш календарь смен:", reply_markup=kb)

@calendar_router.message(FillName.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    tg = message.from_user.id
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg))
    base.commit()

    await message.answer(f"Спасибо, {name}! Вот ваш календарь смен:")
    waiter_id = get_waiter_id_by_tg(tg)
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📅 Прогнозировать смену", callback_data="FORECAST_START")
    ])
    await state.clear()
    await message.answer("", reply_markup=kb)

# Навигация по месяцам (для официанта)
@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_PREV|"))
async def prev_month(query: CallbackQuery):
    _, y, m = query.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0:
        y, m = y - 1, 12
    waiter_id = get_waiter_id_by_tg(query.from_user.id)
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(y, m, set(shifts.keys()))
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📅 Прогнозировать смену", callback_data="FORECAST_START")
    ])
    await query.message.edit_text("Ваш календарь смен:", reply_markup=kb)

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_NEXT|"))
async def next_month(query: CallbackQuery):
    _, y, m = query.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13:
        y, m = y + 1, 1
    waiter_id = get_waiter_id_by_tg(query.from_user.id)
    shifts = get_shifts_for(waiter_id)
    kb = make_calendar(y, m, set(shifts.keys()))
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📅 Прогнозировать смену", callback_data="FORECAST_START")
    ])
    await query.message.edit_text("Ваш календарь смен:", reply_markup=kb)

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data == "CAL_CANCEL")
async def cancel_calendar(query: CallbackQuery):
    await query.message.delete()

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_DAY|"))
async def show_shift_info(query: CallbackQuery):
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

# --- Прогнозирование смены ---
@calendar_router.callback_query(F.data == "FORECAST_START")
async def forecast_start(query: CallbackQuery, state: FSMContext):
    from app.utils.calendar import make_calendar
    today = datetime.today()
    kb = make_calendar(today.year, today.month, set())
    await state.set_state(Forecast.ChoosingDate)
    await query.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)

@calendar_router.callback_query(F.data.startswith("CAL_DAY|"), F.state == Forecast.ChoosingDate)
async def forecast_choose_day(query: CallbackQuery, state: FSMContext):
    _, date_str = query.data.split("|", 1)
    await state.update_data(forecast_date=date_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Смогу", callback_data="FORECAST_YES")],
        [InlineKeyboardButton(text="❌ Не смогу", callback_data="FORECAST_NO")],
    ])
    await state.set_state(Forecast.ConfirmAvailability)
    await query.message.edit_text(f"Дата: {date_str}\nВы сможете выйти?", reply_markup=kb)

@calendar_router.callback_query(F.data.in_(["FORECAST_YES", "FORECAST_NO"]), F.state == Forecast.ConfirmAvailability)
async def forecast_result(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    date_str = data['forecast_date']
    available = (query.data == "FORECAST_YES")
    user = query.from_user

    admin_chat = os.getenv("CHAT_ID")
    text = (
        f"📣 Прогноз смены:\n"
        f"Официант: {user.full_name} (@{user.username})\n"
        f"Дата: {date_str}\n"
        f"{'✅ Смогу выйти' if available else '❌ Не смогу выйти'}"
    )
    await query.bot.send_message(admin_chat, text)
    await query.message.answer("Спасибо! Прогноз отправлен админу.")
    await state.clear()
