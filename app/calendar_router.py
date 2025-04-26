"""
Waiter‑side calendar, forecast & tips for «Стародонье».
"""

from __future__ import annotations

import calendar
import os
from datetime import datetime
from decimal import Decimal
from typing import Set

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.database.sqlite_db import (
    add_waiter,
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    get_shifts_for,
    add_tip,
    get_month_tips,
    clear_month_tips,
)

# ────────────────────────────────────────────────────────────────
# Globals & constants
# ────────────────────────────────────────────────────────────────
router = Router()
calendar_router = router  # alias used elsewhere

ADMIN_IDS = [2015462319, 1773695867]
CHAT_ID = os.getenv("CHAT_ID")  # групповой чат админов


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

# ────────────────────────────────────────────────────────────────
# FSM blocks
# ────────────────────────────────────────────────────────────────

class FillName(StatesGroup):
    waiting = State()


class ForecastStates(StatesGroup):
    choose_date = State()
    confirm = State()


class TipsState(StatesGroup):
    input = State()

# ────────────────────────────────────────────────────────────────
# Helper UI builders
# ────────────────────────────────────────────────────────────────

def make_calendar(year: int, month: int, marked: Set[str]) -> InlineKeyboardMarkup:
    """Генерирует inline‑календарь на указанный месяц."""
    kb: list[list[InlineKeyboardButton]] = []

    kb.append([
        InlineKeyboardButton(text="‹", callback_data=f"CAL_PREV|{year}|{month}"),
        InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
        InlineKeyboardButton(text="›", callback_data=f"CAL_NEXT|{year}|{month}"),
    ])

    kb.append([
        InlineKeyboardButton(text=d, callback_data="IGNORE")
        for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ])

    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="IGNORE"))
            else:
                ds = f"{year:04d}-{month:02d}-{day:02d}"
                mark = "✓" if ds in marked else ""
                row.append(InlineKeyboardButton(text=f"{day}{mark}", callback_data=f"CAL_DAY|{ds}"))
        kb.append(row)

    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="CAL_CANCEL")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# waiter main menu
WAITER_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📆 Просмотреть график работы", callback_data="W_CALENDAR")],
        [InlineKeyboardButton(text="📅 Прогнозировать график работы", callback_data="FORECAST_START")],
        [InlineKeyboardButton(text="💵 Подсчёт чаевых", callback_data="TIPS_START")],
    ]
)

# ────────────────────────────────────────────────────────────────
# Waiter menu commands
# ────────────────────────────────────────────────────────────────

@router.message(Command("menu"))
async def waiter_menu(msg: Message):
    await msg.answer("Меню официанта:", reply_markup=WAITER_MENU)


@router.callback_query(F.data == "W_MENU")
async def waiter_menu_cb(q: CallbackQuery):
    await q.message.edit_text("Меню официанта:", reply_markup=WAITER_MENU)

# ────────────────────────────────────────────────────────────────
# Calendar display helpers
# ────────────────────────────────────────────────────────────────

async def _send_calendar(m: Message, uid: int, edit: bool = False):
    wid = get_waiter_id_by_tg(uid)
    shifts = get_shifts_for(wid)
    marked = set(shifts.keys())
    kb = make_calendar(datetime.today().year, datetime.today().month, marked)
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])

    try:
        if edit:
            await m.edit_text("Ваш календарь:", reply_markup=kb)
        else:
            await m.answer("Ваш календарь:", reply_markup=kb)
    except TelegramBadRequest:
        # Сообщение уже изменено/удалено – отправим новое
        await m.answer("Ваш календарь:", reply_markup=kb)

# ────────────────────────────────────────────────────────────────
# /calendar – first run (fill name) and show calendar
# ────────────────────────────────────────────────────────────────

@router.message(Command("calendar"))
async def cmd_calendar(msg: Message, state: FSMContext):
    waiter = get_waiter_by_tg(msg.from_user.id)
    if not waiter or not waiter[1]:  # имени нет
        if not waiter:
            add_waiter(msg.from_user.id)
        await msg.answer("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting)
        return
    await _send_calendar(msg, msg.from_user.id)


@router.message(StateFilter(FillName.waiting))
async def save_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    from app.database.sqlite_db import cur, base

    cur.execute("UPDATE waiters SET name=? WHERE tg_id=?", (name, msg.from_user.id))
    base.commit()

    await msg.answer(f"Спасибо, {name}!")
    await _send_calendar(msg, msg.from_user.id)
    await state.clear()

# ────────────────────────────────────────────────────────────────
# Calendar navigation (waiter view)
# ────────────────────────────────────────────────────────────────

@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_PREV|"))
async def prev_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0:
        y, m = y - 1, 12
    wid = get_waiter_id_by_tg(q.from_user.id)
    kb = make_calendar(y, m, set(get_shifts_for(wid).keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)


@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_NEXT|"))
async def next_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13:
        y, m = y + 1, 1
    wid = get_waiter_id_by_tg(q.from_user.id)
    kb = make_calendar(y, m, set(get_shifts_for(wid).keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)


@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data == "CAL_CANCEL")
async def cancel_cal(q: CallbackQuery):
    await q.message.delete()

# ────────────────────────────────────────────────────────────────
# Show shift details
# ────────────────────────────────────────────────────────────────

@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_DAY|"))
async def show_shift(q: CallbackQuery):
    _, ds = q.data.split("|", 1)
    info = get_shifts_for(get_waiter_id_by_tg(q.from_user.id)).get(ds)
    text = (
        f"📅 {ds}\n⏱️ {info['hours']} ч\n📋 {info['tasks'] or '—'}" if info else "Нет смен."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")]]
    )
    await q.message.delete()
    await q.message.answer(text, reply_markup=kb)

# ────────────────────────────────────────────────────────────────
# FORECAST BLOCK
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "FORECAST_START")
async def forecast_start(q: CallbackQuery, state: FSMContext):
    kb = make_calendar(datetime.today().year, datetime.today().month, set())
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])

    await state.set_state(ForecastStates.choose_date)
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@router.callback_query(StateFilter(ForecastStates.choose_date), F.data.startswith("CAL_DAY|"))
async def forecast_choose(q: CallbackQuery, state: FSMContext):
    _, ds = q.data.split("|", 1)
    await state.update_data(date=ds)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Смогу", callback_data="FORECAST_YES")],
            [InlineKeyboardButton(text="❌ Не смогу", callback_data="FORECAST_NO")],
        ]
    )
    await state.set_state(ForecastStates.confirm)
    await q.message.edit_text(f"Дата: {ds}\nСможете выйти?", reply_markup=kb)


@router.callback_query(StateFilter(ForecastStates.choose_date), F.data == "CAL_CANCEL")
async def forecast_cancel(q: CallbackQuery, state: FSMContext):
    await state.clear()
    await waiter_menu_cb(q)


@router.callback_query(StateFilter(ForecastStates.choose_date), F.data.startswith("CAL_PREV|"))
async def forecast_prev_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0:
        y, m = y - 1, 12
    kb = make_calendar(y, m, set())
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@router.callback_query(StateFilter(ForecastStates.choose_date), F.data.startswith("CAL_NEXT|"))
async def forecast_next_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13:
        y, m = y + 1, 1
    kb = make_calendar(y, m, set())
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@router.callback_query(
    StateFilter(ForecastStates.confirm),
    F.data.in_({"FORECAST_YES", "FORECAST_NO"})
)
async def forecast_send(q: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ds = data["date"]
    ok = q.data == "FORECAST_YES"

    if not CHAT_ID:
        await q.answer("CHAT_ID не настроен", show_alert=True)
        await waiter_menu_cb(q)
        await state.clear()
        return

    txt = (
        "📣 Прогноз:\n"
        f"Официант: {q.from_user.full_name} (@{q.from_user.username or 'нет'})\n"
        f"Дата: {ds}\n"
        f"{'✅ Смогу' if ok else '❌ Не смогу'}"
    )

    try:
        await q.bot.send_message(CHAT_ID, txt)
    except Exception:
        pass

    await q.message.edit_text("Спасибо! Отправлено админу.", reply_markup=WAITER_MENU)
    await state.clear()

# ────────────────────────────────────────────────────────────────
# TIPS BLOCK
# ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "TIPS_START")
async def tips_start(q: CallbackQuery, state: FSMContext):
    today = datetime.today().strftime("%Y-%m-%d")
    wid = get_waiter_id_by_tg(q.from_user.id)
    await state.update_data(wid=wid, date=today)
    await state.set_state(TipsState.input)
    await q.message.edit_text(f"Введите сумму чаевых за {today} (руб):")


@router.message(StateFilter(TipsState.input))
async def tips_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    try:
        amount = Decimal(msg.text.replace(",", "."))
        assert amount >= 0
    except Exception:
        await msg.reply("Введите корректное число, например 1234.50")
        return

    add_tip(data["wid"], data["date"], float(amount))
    ym = data["date"][:7]
    total = get_month_tips(data["wid"], ym) or 0.0

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Обнулить чаевые за месяц", callback_data=f"TIPS_CLEAR|{ym}")],
            [InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")],
        ]
    )
    await msg.answer(
        f"Записано {amount:.2f} ₽.\nВсего за {ym}: {total:.2f} ₽", reply_markup=kb
    )
    await state.clear()


@router.callback_query(F.data.startswith("TIPS_CLEAR|"))
async def tips_clear(q: CallbackQuery):
    _, ym = q.data.split("|", 1)
    clear_month_tips(get_waiter_id_by_tg(q.from_user.id), ym)
    await q.answer("Чаевые за месяц обнулены!", show_alert=True)
    await q.message.edit_text("Чаевые сброшены.", reply_markup=WAITER_MENU)
