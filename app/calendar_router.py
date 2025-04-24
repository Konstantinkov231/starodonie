# app/calendar_router.py

import os
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.sqlite_db import (
    add_waiter, get_waiter_by_tg, get_waiter_id_by_tg, get_shifts_for
)
from app.utils.calendar import make_calendar

calendar_router = Router()

ADMIN_IDS = [2015462319, 1773695867]
def is_admin(uid:int)->bool: return uid in ADMIN_IDS

class FillName(StatesGroup):
    waiting_for_name = State()

class Forecast(StatesGroup):
    ChoosingDate        = State()
    ConfirmAvailability = State()

@calendar_router.message(Command("calendar"))
async def cmd_calendar(msg: Message, state: FSMContext):
    w = get_waiter_by_tg(msg.from_user.id)
    if not w or not w[1]:
        if not w: add_waiter(msg.from_user.id)
        await msg.answer("Введите своё имя для календаря:")
        return await state.set_state(FillName.waiting_for_name)

    wid,name = w
    shifts = get_shifts_for(wid)
    kb = make_calendar(datetime.today().year, datetime.today().month, set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton("📅 Прогноз смены", callback_data="FORECAST_START")])
    await msg.answer("Ваш календарь:", reply_markup=kb)

@calendar_router.message(FillName.waiting_for_name)
async def proc_name(msg: Message, state: FSMContext):
    name=msg.text.strip(); tg=msg.from_user.id
    from app.database.sqlite_db import cur,base
    cur.execute("UPDATE waiters SET name=? WHERE tg_id=?", (name,tg))
    base.commit()
    await msg.answer(f"Спасибо, {name}! Вот календарь:")
    wid = get_waiter_id_by_tg(tg)
    shifts=get_shifts_for(wid)
    kb=make_calendar(datetime.today().year,datetime.today().month,set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton("📅 Прогноз смены", callback_data="FORECAST_START")])
    await state.clear()
    await msg.answer("",reply_markup=kb)

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_PREV|"))
async def prev(q:CallbackQuery):
    _,y,m=q.data.split("|"); y,m=int(y),int(m)-1
    if m==0: y,m=y-1,12
    wid=get_waiter_id_by_tg(q.from_user.id)
    shifts=get_shifts_for(wid)
    kb=make_calendar(y,m,set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton("📅 Прогноз смены", callback_data="FORECAST_START")])
    await q.message.edit_text("Ваш календарь:",reply_markup=kb)

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_NEXT|"))
async def nxt(q:CallbackQuery):
    _,y,m=q.data.split("|"); y,m=int(y),int(m)+1
    if m==13: y,m=y+1,1
    wid=get_waiter_id_by_tg(q.from_user.id)
    shifts=get_shifts_for(wid)
    kb=make_calendar(y,m,set(shifts.keys()))
    kb.inline_keyboard.append([InlineKeyboardButton("📅 Прогноз смены", callback_data="FORECAST_START")])
    await q.message.edit_text("Ваш календарь:",reply_markup=kb)

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data=="CAL_CANCEL")
async def cancel(q:CallbackQuery): await q.message.delete()

@calendar_router.callback_query(lambda q: not is_admin(q.from_user.id) and q.data.startswith("CAL_DAY|"))
async def show_shift(q:CallbackQuery):
    _,ds=q.data.split("|",1)
    wid=get_waiter_id_by_tg(q.from_user.id)
    info=get_shifts_for(wid).get(ds)
    if info:
        txt=f"📅 {ds}\n⏱️ {info['hours']} ч\n📋 {info['tasks'] or '—'}"
    else:
        txt="Нет смен."
    await q.message.delete(); await q.message.answer(txt)

@calendar_router.callback_query(F.data=="FORECAST_START")
async def fc_start(q:CallbackQuery, state:FSMContext):
    kb=make_calendar(datetime.today().year,datetime.today().month,set())
    await state.set_state(Forecast.ChoosingDate)
    await q.message.edit_text("Выберите дату для прогноза:",reply_markup=kb)

@calendar_router.callback_query(F.data.startswith("CAL_DAY|"), F.state==Forecast.ChoosingDate)
async def fc_choose(q:CallbackQuery, state:FSMContext):
    _,ds=q.data.split("|",1)
    await state.update_data(forecast_date=ds)
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Смогу",callback_data="FORECAST_YES")],
        [InlineKeyboardButton("❌ Не смогу",callback_data="FORECAST_NO")],
    ])
    await state.set_state(Forecast.ConfirmAvailability)
    await q.message.edit_text(f"Дата: {ds}\nСможете выйти?",reply_markup=kb)

@calendar_router.callback_query(F.data.in_(["FORECAST_YES","FORECAST_NO"]), F.state==Forecast.ConfirmAvailability)
async def fc_result(q:CallbackQuery, state:FSMContext):
    data=await state.get_data(); ds=data['forecast_date']
    ok=(q.data=="FORECAST_YES")
    u=q.from_user
    admin_chat=os.getenv("CHAT_ID")
    txt=(f"📣 Прогноз:\nОфициант: {u.full_name} (@{u.username})\n"
         f"Дата: {ds}\n{'✅ Смогу' if ok else '❌ Не смогу'}")
    await q.bot.send_message(admin_chat, txt)
    await q.message.answer("Спасибо! Отправлено админу.")
    await state.clear()
