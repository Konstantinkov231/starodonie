# app/calendar_router.py

import calendar
import os
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app.database.sqlite_db import (
    add_waiter,
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    get_shifts_for,
)

calendar_router = Router()
ADMIN_IDS = [2015462319, 1773695867]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# === Utility: build inline calendar ===
def make_calendar(year: int, month: int, marked: set[str]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []

    # Header
    keyboard.append([
        InlineKeyboardButton(text="‹", callback_data=f"CAL_PREV|{year}|{month}"),
        InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
        InlineKeyboardButton(text="›", callback_data=f"CAL_NEXT|{year}|{month}"),
    ])
    # Weekdays
    keyboard.append([
        InlineKeyboardButton(text=d, callback_data="IGNORE")
        for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])
    # Days
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="IGNORE"))
            else:
                ds = f"{year:04d}-{month:02d}-{day:02d}"
                mark = "✓" if ds in marked else ""
                row.append(InlineKeyboardButton(text=f"{day}{mark}", callback_data=f"CAL_DAY|{ds}"))
        keyboard.append(row)
    # Cancel
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="CAL_CANCEL")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# 1) IGNORE handler
@calendar_router.callback_query(F.data == "IGNORE")
async def _ignore(query: CallbackQuery):
    await query.answer()


# 2) /calendar
class FillName(StatesGroup):
    waiting_for_name = State()

@calendar_router.message(Command("calendar"))
async def cmd_calendar(msg: Message, state: FSMContext):
    waiter = get_waiter_by_tg(msg.from_user.id)
    if not waiter or not waiter[1]:
        if not waiter:
            add_waiter(msg.from_user.id)
        await msg.answer("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting_for_name)
        return

    wid, _ = waiter
    shifts = get_shifts_for(wid)
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📅 Прогноз смены", callback_data="FORECAST_START")
    ])
    await msg.answer("Ваш календарь:", reply_markup=kb)


@calendar_router.message(FillName.waiting_for_name)
async def process_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    tg = msg.from_user.id
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name = ? WHERE tg_id = ?", (name, tg))
    base.commit()

    await msg.answer(f"Спасибо, {name}! Вот календарь:")
    wid = get_waiter_id_by_tg(tg)
    shifts = get_shifts_for(wid)
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📅 Прогноз смены", callback_data="FORECAST_START")
    ])
    await state.clear()
    await msg.answer("", reply_markup=kb)


# 3) Non-admin navigation & show shift
@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_PREV|"))
async def prev_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0: y, m = y - 1, 12
    wid = get_waiter_id_by_tg(q.from_user.id)
    shifts = get_shifts_for(wid)
    kb = make_calendar(y, m, set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="📅 Прогноз смены", callback_data="FORECAST_START")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)


@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_NEXT|"))
async def next_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13: y, m = y + 1, 1
    wid = get_waiter_id_by_tg(q.from_user.id)
    shifts = get_shifts_for(wid)
    kb = make_calendar(y, m, set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="📅 Прогноз смены", callback_data="FORECAST_START")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)


@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data == "CAL_CANCEL")
async def cancel_calendar(q: CallbackQuery):
    await q.message.delete()


@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_DAY|"))
async def show_shift(q: CallbackQuery):
    _, ds = q.data.split("|", 1)
    wid = get_waiter_id_by_tg(q.from_user.id)
    info = get_shifts_for(wid).get(ds)
    if info:
        text = f"📅 {ds}\n⏱️ {info['hours']} ч\n📋 {info['tasks'] or '—'}"
    else:
        text = "Нет смен."
    await q.message.delete()
    await q.message.answer(text)


# 4) Forecast flow
class Forecast(StatesGroup):
    ChoosingDate        = State()
    ConfirmAvailability = State()


@calendar_router.callback_query(F.data == "FORECAST_START")
async def forecast_start(q: CallbackQuery, state: FSMContext):
    kb = make_calendar(datetime.today().year, datetime.today().month, set())
    await state.set_state(Forecast.ChoosingDate)
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@calendar_router.callback_query(F.data.startswith("CAL_PREV|"), F.state == Forecast.ChoosingDate)
async def forecast_prev(q: CallbackQuery, state: FSMContext):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0: y, m = y - 1, 12
    kb = make_calendar(y, m, set())
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@calendar_router.callback_query(F.data.startswith("CAL_NEXT|"), F.state == Forecast.ChoosingDate)
async def forecast_next(q: CallbackQuery, state: FSMContext):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13: y, m = y + 1, 1
    kb = make_calendar(y, m, set())
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@calendar_router.callback_query(F.data.startswith("CAL_DAY|"), F.state == Forecast.ChoosingDate)
async def forecast_choose(q: CallbackQuery, state: FSMContext):
    _, ds = q.data.split("|", 1)
    await state.update_data(forecast_date=ds)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Смогу", callback_data="FORECAST_YES")],
        [InlineKeyboardButton(text="❌ Не смогу", callback_data="FORECAST_NO")],
    ])
    await state.set_state(Forecast.ConfirmAvailability)
    await q.message.edit_text(f"Дата: {ds}\nСможете выйти?", reply_markup=kb)


@calendar_router.callback_query(F.data.in_(["FORECAST_YES","FORECAST_NO"]), F.state == Forecast.ConfirmAvailability)
async def forecast_result(q: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ds = data["forecast_date"]
    ok = (q.data == "FORECAST_YES")
    admin_chat = os.getenv("CHAT_ID")
    u = q.from_user
    text = (
        f"📣 Прогноз:\n"
        f"Официант: {u.full_name} (@{u.username})\n"
        f"Дата: {ds}\n"
        f"{'✅ Смогу' if ok else '❌ Не смогу'}"
    )
    await q.bot.send_message(admin_chat, text)
    await q.message.answer("Спасибо! Отправлено админу.")
    await state.clear()
