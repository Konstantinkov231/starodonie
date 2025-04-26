"""
Waiter-side calendar, forecast & tips for «Стародонье».
"""

from __future__ import annotations

import calendar
import os
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
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

router = Router()

calendar_router = router
ADMIN_IDS = [2015462319, 1773695867]

def is_admin(uid: int) -> bool: return uid in ADMIN_IDS

# ───── меню официанта ─────
WAITER_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📆 Просмотреть график работы", callback_data="W_CALENDAR")],
    [InlineKeyboardButton(text="📅 Прогнозировать график работы", callback_data="FORECAST_START")],
    [InlineKeyboardButton(text="💵 Подсчёт чаевых", callback_data="TIPS_START")],
])

@router.message(Command("menu"))
async def waiter_menu(msg: Message): await msg.answer("Меню официанта:", reply_markup=WAITER_MENU)

@router.callback_query(F.data == "W_MENU")
async def waiter_menu_cb(q: CallbackQuery): await q.message.edit_text("Меню официанта:", reply_markup=WAITER_MENU)

# ───── календарь ─────
def make_calendar(year: int, month: int, marked: set[str]) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="‹", callback_data=f"CAL_PREV|{year}|{month}"),
            InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
            InlineKeyboardButton(text="›", callback_data=f"CAL_NEXT|{year}|{month}"),
        ],
        [InlineKeyboardButton(text=d, callback_data="IGNORE") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]],
    ]
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row=[]
        for day in week:
            if day==0:
                row.append(InlineKeyboardButton(text=" ", callback_data="IGNORE"))
            else:
                ds=f"{year:04d}-{month:02d}-{day:02d}"
                mark="✓" if ds in marked else ""
                row.append(InlineKeyboardButton(text=f"{day}{mark}", callback_data=f"CAL_DAY|{ds}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="CAL_CANCEL")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def _send_calendar(m, uid: int, edit=False):
    wid = get_waiter_id_by_tg(uid)
    shifts = get_shifts_for(wid)
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    if edit: await m.edit_text("Ваш календарь:", reply_markup=kb)
    else:    await m.answer("Ваш календарь:", reply_markup=kb)

@router.callback_query(F.data == "W_CALENDAR")
async def waiter_calendar(q: CallbackQuery): await _send_calendar(q.message, q.from_user.id, True)

@router.callback_query(F.data == "IGNORE")
async def _ignore(q: CallbackQuery): await q.answer()

# ───── /calendar (первый запуск) ─────
class FillName(StatesGroup):
    waiting = State()

@router.message(Command("calendar"))
async def cmd_calendar(msg: Message, state: FSMContext):
    waiter = get_waiter_by_tg(msg.from_user.id)
    if not waiter or not waiter[1]:
        if not waiter: add_waiter(msg.from_user.id)
        await msg.answer("Введите своё имя для календаря:")
        await state.set_state(FillName.waiting)
        return
    await _send_calendar(msg, msg.from_user.id)

@router.message(FillName.waiting)
async def save_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name=? WHERE tg_id=?", (name, msg.from_user.id))
    base.commit()
    await msg.answer(f"Спасибо, {name}!")
    await _send_calendar(msg, msg.from_user.id)
    await state.clear()

# ───── навигация мес. вперёд/назад ─────
@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_PREV|"))
async def prev_month(q: CallbackQuery):
    _, y, m = q.data.split("|"); y, m = int(y), int(m)-1
    if m==0: y,m=y-1,12
    wid=get_waiter_id_by_tg(q.from_user.id)
    kb=make_calendar(y,m,set(get_shifts_for(wid).keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)

@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_NEXT|"))
async def next_month(q: CallbackQuery):
    _,y,m=q.data.split("|"); y,m=int(y),int(m)+1
    if m==13:y,m=y+1,1
    wid=get_waiter_id_by_tg(q.from_user.id)
    kb=make_calendar(y,m,set(get_shifts_for(wid).keys()))
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await q.message.edit_text("Ваш календарь:", reply_markup=kb)

@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data == "CAL_CANCEL")
async def cancel_cal(q: CallbackQuery): await q.message.delete()

# ───── показать смену ─────
@router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_DAY|"))
async def show_shift(q: CallbackQuery):
    _,ds=q.data.split("|",1)
    info=get_shifts_for(get_waiter_id_by_tg(q.from_user.id)).get(ds)
    text=f"📅 {ds}\n⏱️ {info['hours']} ч\n📋 {info['tasks'] or '—'}" if info else "Нет смен."
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")]])
    await q.message.delete()
    await q.message.answer(text, reply_markup=kb)

# ───── FORECAST (смогу/не смогу) ─────
class Forecast(StatesGroup):
    choose_date = State()
    confirm     = State()

@router.callback_query(F.data == "FORECAST_START")
async def forecast_start(q: CallbackQuery, state:FSMContext):
    kb=make_calendar(datetime.today().year, datetime.today().month,set())
    kb.inline_keyboard.append([InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")])
    await state.set_state(Forecast.choose_date)
    await q.message.edit_text("Выберите дату для прогноза:", reply_markup=kb)

@router.callback_query(F.data.startswith("CAL_DAY|"), Forecast.choose_date)
async def forecast_choose(q: CallbackQuery, state:FSMContext):
    _,ds=q.data.split("|",1)
    await state.update_data(date=ds)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Смогу", callback_data="FORECAST_YES")],
        [InlineKeyboardButton(text="❌ Не смогу", callback_data="FORECAST_NO")],
    ])
    await state.set_state(Forecast.confirm)
    await q.message.edit_text(f"Дата: {ds}\nСможете выйти?", reply_markup=kb)

@router.callback_query(F.data.in_(["FORECAST_YES","FORECAST_NO"]), Forecast.confirm)
async def forecast_send(q: CallbackQuery, state:FSMContext):
    ds=(await state.get_data())["date"]
    ok=q.data=="FORECAST_YES"
    admin_chat=os.getenv("CHAT_ID")
    txt=f"📣 Прогноз:\nОфициант: {q.from_user.full_name} (@{q.from_user.username})\nДата: {ds}\n{'✅ Смогу' if ok else '❌ Не смогу'}"
    await q.bot.send_message(admin_chat,txt)
    await q.message.answer("Спасибо! Отправлено админу.", reply_markup=WAITER_MENU)
    await state.clear()

# ───── TIPS ─────
class TipsState(StatesGroup):
    input = State()

@router.callback_query(F.data == "TIPS_START")
async def tips_start(q:CallbackQuery,state:FSMContext):
    today=datetime.today().strftime("%Y-%m-%d")
    wid=get_waiter_id_by_tg(q.from_user.id)
    await state.update_data(wid=wid,date=today)
    await state.set_state(TipsState.input)
    await q.message.edit_text(f"Введите сумму чаевых за {today} (руб):")

@router.message(TipsState.input)
async def tips_save(msg:Message,state:FSMContext):
    data=await state.get_data()
    try:
        amount=float(msg.text.replace(",",".")); assert amount>=0
    except Exception:
        return await msg.reply("Введите корректное число, например 1234.50")
    add_tip(data["wid"],data["date"],amount)
    ym=data["date"][:7]; total=get_month_tips(data["wid"],ym)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Обнулить чаевые за месяц", callback_data=f"TIPS_CLEAR|{ym}")],
        [InlineKeyboardButton(text="⏪ В меню", callback_data="W_MENU")],
    ])
    await msg.answer(f"Записано {amount:.2f} ₽.\nВсего за {ym}: {total:.2f} ₽", reply_markup=kb)
    await state.clear()

@router.callback_query(F.data.startswith("TIPS_CLEAR|"))
async def tips_clear(q:CallbackQuery):
    _,ym=q.data.split("|",1)
    clear_month_tips(get_waiter_id_by_tg(q.from_user.id),ym)
    await q.answer("Чаевые за месяц обнулены!", show_alert=True)
    await q.message.edit_text("Чаевые сброшены.", reply_markup=WAITER_MENU)
