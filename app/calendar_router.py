"""
Waiter‑side calendar, forecast & tips for «Стародонье».
Все функции доступны любому пользователю.
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
    set_waiter_name,
)

# ────────────────────────────────
#   Globals
# ────────────────────────────────
router = Router()
calendar_router = router  # alias for main bot file

ADMIN_CHAT_IDS: list[int] = [
    int(x) for x in os.getenv("CHAT_IDS", "2015462319,1773695867").split(",") if x
]

# ────────────────────────────────
#   FSM‑states
# ────────────────────────────────

class FillName(StatesGroup):
    waiting = State()


class Forecast(StatesGroup):
    choose_date = State()
    confirm = State()


class TipsState(StatesGroup):
    input = State()


# ────────────────────────────────
#   UI builders
# ────────────────────────────────

def make_calendar(year: int, month: int, marked: Set[str]) -> InlineKeyboardMarkup:
    """Return an inline‑calendar with marked dates (buttons use named args)."""

    kb: list[list[InlineKeyboardButton]] = []

    # Header navigation
    kb.append([
        InlineKeyboardButton(text="‹", callback_data=f"CAL_PREV|{year}|{month}"),
        InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
        InlineKeyboardButton(text="›", callback_data=f"CAL_NEXT|{year}|{month}"),
    ])

    # Weekdays row
    kb.append([
        InlineKeyboardButton(text=d, callback_data="IGNORE")
        for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ])

    # Days grid
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

    # Footer
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="CAL_CANCEL")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


WAITER_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📆 Просмотреть график",   callback_data="W_CALENDAR")],
        [InlineKeyboardButton(text="📅 Прогнозировать график", callback_data="FORECAST_START")],
        [InlineKeyboardButton(text="💵 Подсчёт чаевых",       callback_data="TIPS_START")],
    ]
)

# ────────────────────────────────
#   Menu / Calendar
# ────────────────────────────────

@router.message(Command("menu"))
async def waiter_menu(msg: Message):
    await msg.answer("Меню официанта:", reply_markup=WAITER_MENU)


@router.callback_query(F.data == "W_MENU")
async def waiter_menu_cb(q: CallbackQuery):
    await q.message.edit_text("Меню официанта:", reply_markup=WAITER_MENU)


@router.callback_query(F.data == "W_MENU_DEL")
async def waiter_menu_del(q: CallbackQuery):
    await q.message.delete()
    await q.message.answer("Меню официанта:", reply_markup=WAITER_MENU)


async def _send_calendar(m: Message, uid: int, edit: bool = False):
    """Send or edit waiter calendar."""
    wid = get_waiter_id_by_tg(uid)
    shifts = get_shifts_for(wid) if wid else {}
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])

    try:
        if edit:
            await m.edit_text("Ваш календарь:", reply_markup=kb)
        else:
            await m.answer("Ваш календарь:", reply_markup=kb)
    except TelegramBadRequest:
        await m.answer("Ваш календарь:", reply_markup=kb)


@router.message(Command("calendar"))
async def cmd_calendar(msg: Message, state: FSMContext):
    # Check if the user exists in the waiters table
    waiter = get_waiter_by_tg(msg.from_user.id)
    if not waiter:
        # User doesn't exist, add them to the waiters table with name as NULL
        add_waiter(msg.from_user.id)
        await msg.answer("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting)
        return
    if not waiter[1]:  # waiter[1] is the name; prompt if it's NULL
        await msg.answer("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting)
        return
    await _send_calendar(msg, msg.from_user.id)


@router.message(StateFilter(FillName.waiting))
async def save_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    set_waiter_name(msg.from_user.id, name)
    await msg.answer(f"Спасибо, {name}!")
    await _send_calendar(msg, msg.from_user.id)
    await state.clear()


# ─────────── Quick calendar from menu button ───────────
@router.callback_query(F.data == "W_CALENDAR")
async def waiter_calendar_cb(q: CallbackQuery, state: FSMContext):
    """Показывает календарь при нажатии кнопки в главном меню."""
    # Check if the user exists in the waiters table
    waiter = get_waiter_by_tg(q.from_user.id)
    if not waiter:
        # User doesn't exist, add them to the waiters table with name as NULL
        add_waiter(q.from_user.id)
        await q.message.edit_text("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting)
        return
    if not waiter[1]:  # waiter[1] is the name; prompt if it's NULL
        await q.message.edit_text("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting)
        return
    await _send_calendar(q.message, q.from_user.id, True)


@router.callback_query(F.data == "IGNORE")
async def _ignore_cb(q: CallbackQuery):
    """Пустой клик — просто answer, чтобы убрать «часики»."""
    await q.answer()

# ─────────── Calendar navigation ───────────

@router.callback_query(StateFilter(None), F.data.startswith("CAL_PREV|"))
async def prev_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) - 1
    if m == 0:
        y, m = y - 1, 12
    wid = get_waiter_id_by_tg(q.from_user.id)
    kb = make_calendar(y, m, set(get_shifts_for(wid).keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)


@router.callback_query(StateFilter(None), F.data.startswith("CAL_NEXT|"))
async def next_month(q: CallbackQuery):
    _, y, m = q.data.split("|")
    y, m = int(y), int(m) + 1
    if m == 13:
        y, m = y + 1, 1
    wid = get_waiter_id_by_tg(q.from_user.id)
    kb = make_calendar(y, m, set(get_shifts_for(wid).keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)


@router.callback_query(StateFilter(None), F.data == "CAL_CANCEL")
async def cancel_cal(q: CallbackQuery):
    await q.message.delete()


@router.callback_query(StateFilter(None), F.data.startswith("CAL_DAY|"))
async def show_shift(q: CallbackQuery):
    _, ds = q.data.split("|", 1)
    info = get_shifts_for(get_waiter_id_by_tg(q.from_user.id)).get(ds)
    text = f"📅 {ds}\n⏱️ {info['hours']} ч\n📋 {info['tasks'] or '—'}" if info else "Нет смен."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")]])
    await q.message.delete()
    await q.message.answer(text, reply_markup=kb)

# ─────────── FORECAST ───────────
@router.callback_query(F.data == "FORECAST_START")
async def forecast_start(q: CallbackQuery, state: FSMContext):
    kb = make_calendar(datetime.today().year, datetime.today().month, set())
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await state.set_state(Forecast.choose_date)
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@router.callback_query(StateFilter(Forecast.choose_date), F.data.startswith("CAL_DAY|"))
async def forecast_choose(q: CallbackQuery, state: FSMContext):
    _, ds = q.data.split("|", 1)
    await state.update_data(date=ds)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Смогу", callback_data="FORECAST_YES")],
        [InlineKeyboardButton(text="❌ Не смогу", callback_data="FORECAST_NO")],
    ])
    await state.set_state(Forecast.confirm)
    await q.message.edit_text(f"Дата: {ds}\nСможете выйти?", reply_markup=kb)


@router.callback_query(StateFilter(Forecast.choose_date), F.data == "CAL_CANCEL")
async def forecast_cancel(q: CallbackQuery, state: FSMContext):
    await state.clear()
    await waiter_menu_cb(q)


for _t in ("CAL_PREV|", "CAL_NEXT|"):
    @router.callback_query(StateFilter(Forecast.choose_date), F.data.startswith(_t))
    async def _forecast_nav(q: CallbackQuery, state: FSMContext, _t=_t):  # noqa: B023
        _, y, m = q.data.split("|")
        y, m = int(y), int(m) + (-1 if _t == "CAL_PREV|" else 1)
        if m == 0:
            y, m = y - 1, 12
        if m == 13:
            y, m = y + 1, 1
        kb = make_calendar(y, m, set())
        kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
        await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)


@router.callback_query(StateFilter(Forecast.confirm), F.data.in_(["FORECAST_YES", "FORECAST_NO"]))
async def forecast_send(q: CallbackQuery, state: FSMContext):
    ds = (await state.get_data())["date"]
    ok = q.data == "FORECAST_YES"

    txt = (
        "📣 <b>Прогноз выхода</b>\n"
        f"Официант: {q.from_user.full_name} (@{q.from_user.username or 'N/A'})\n"
        f"Дата: {ds}\n"
        f"{'✅ Сможет выйти' if ok else '❌ Не сможет выйти'}"
    )

    delivered = False
    for chat_id in ADMIN_CHAT_IDS:
        try:
            await q.bot.send_message(chat_id, txt, parse_mode="HTML")
            delivered = True
        except Exception:
            continue

    await q.answer(
        "Прогноз отправлен администраторам ✅" if delivered else "❗️ Не удалось уведомить администраторов",
        show_alert=True,
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU_DEL")]])
    await q.message.edit_text("Спасибо! Ваш прогноз учтён.", reply_markup=kb)
    await state.clear()

# ─────────── TIPS ───────────
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

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Обнулить чаевые за месяц", callback_data=f"TIPS_CLEAR|{ym}")],
        [InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")],
    ])
    await msg.answer(f"Записано {amount:.2f} ₽. Всего за {ym}: {total:.2f} ₽", reply_markup=kb)
    await state.clear()


@router.callback_query(F.data.startswith("TIPS_CLEAR|"))
async def tips_clear(q: CallbackQuery):
    _, ym = q.data.split("|", 1)
    clear_month_tips(get_waiter_id_by_tg(q.from_user.id), ym)
    await q.answer("Чаевые за месяц обнулены!", show_alert=True)
    await q.message.edit_text("Чаевые сброшены.", reply_markup=WAITER_MENU)