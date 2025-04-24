# calendar_router.py
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from app.admin import is_admin
from app.database.sqlite_db import (
    get_waiter_by_tg,
    get_waiter_id_by_tg,
    add_waiter,
    get_shifts_for,
)
from app.utils.calendar import make_calendar

calendar_router = Router()

class FillName(StatesGroup):
    waiting_for_name = State()

@calendar_router.message(Command("calendar"))
async def cmd_calendar(message: Message, state: FSMContext):
    waiter = get_waiter_by_tg(message.from_user.id)
    if not waiter:
        add_waiter(message.from_user.id)
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return
    wid, name = waiter
    if not name:
        await message.answer("Пожалуйста, введите ваше имя для личного календаря:")
        await state.set_state(FillName.waiting_for_name)
        return
    await _show_calendar(message, wid)

@calendar_router.message(FillName.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    tg = message.from_user.id
    from app.database.sqlite_db import cur, base
    cur.execute("UPDATE waiters SET name=? WHERE tg_id=?", (name, tg))
    base.commit()
    await message.answer(f"Спасибо, {name}! Вот ваш календарь:")
    wid = get_waiter_id_by_tg(tg)
    await state.clear()
    await _show_calendar(message, wid)

async def _show_calendar(src, wid: int, year=None, month=None):
    today = datetime.today()
    year = year or today.year
    month = month or today.month
    shifts = get_shifts_for(wid)
    kb = make_calendar(year, month, set(shifts.keys()))
    await src.answer("Выберите дату:", reply_markup=kb)

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_"))
async def calendar_handler(query: CallbackQuery, state: FSMContext):
    parts = query.data.split("|")
    act = parts[0]
    wid = get_waiter_id_by_tg(query.from_user.id)
    if act=="CAL_CANCEL": await query.message.delete(); return
    if act in ("CAL_PREV","CAL_NEXT"):
        y,m = map(int, parts[1:])
        if act=="CAL_PREV": m,y = (m-1 or 12),(y-1 if m==12 else y)
        else: m,y = (m+1 if m<12 else 1),(y+1 if m==12 else y)
        shifts = get_shifts_for(wid)
        await query.message.edit_text("Выберите дату:", reply_markup=make_calendar(y,m,set(shifts.keys())))
        return
    if act=="CAL_DAY":
        date = parts[1]
        info = get_shifts_for(wid).get(date)
        if info:
            text = f"Смена {date}: {info['hours']} ч.\nЗадачи: {info['tasks'] or 'нет'}"
        else: text = "Нет смен на эту дату."
        await query.message.delete()
        await query.message.answer(text)
