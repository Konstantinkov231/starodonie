import os
from datetime import datetime
from io import BytesIO

from aiogram import Router, F
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from openpyxl import Workbook

from app.database.sqlite_db import (
    get_all_waiters,
    add_shift,
    set_shift_hours,
    set_shift_tasks,
    get_all_shifts,
    get_shifts_for,
)
from app.utils.calendar import make_calendar

admin = Router()

# --- Admin IDs and filter ---
ADMIN_ID = [2015462319, 1773695867]

def user_is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID

class AdminProtect(Filter):
    async def __call__(self, message: Message) -> bool:
        return user_is_admin(message.from_user.id)

# --- FSM states ---
class AdminStates(StatesGroup):
    choose_hours_date = State()
    choose_waiter = State()
    choose_edit_date = State()
    waiting_hours = State()
    waiting_tasks = State()

# --- Main admin menu ---
@admin.message(Command("admin_menu"), AdminProtect())
async def cmd_admin_menu(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Установить часы", callback_data="AM_SET_HOURS")],
        [InlineKeyboardButton(text="🗓 Изменить график", callback_data="AM_EDIT_SCHEDULE")],
        [InlineKeyboardButton(text="💰 Рассчитать зарплату", callback_data="AM_CALC_SALARY")],
        [InlineKeyboardButton(text="📢 Информировать", callback_data="AM_NOTIFY")],
        [InlineKeyboardButton(text="📥 Скачать Excel", callback_data="AM_EXPORT")],
    ])
    await message.answer(text="<b>Меню администратора</b>", parse_mode="HTML", reply_markup=kb)

# --- Global calendar for hours (all staff) ---
@admin.callback_query(AdminProtect(), F.data == "AM_SET_HOURS")
async def on_set_hours(query: CallbackQuery, state: FSMContext):
    await state.clear()
    year, month = datetime.today().year, datetime.today().month
    cal = make_calendar(year, month, set())
    cal.inline_keyboard.append([
        InlineKeyboardButton(text="⏪ Назад", callback_data="AM_BACK_MENU")
    ])
    await state.set_state(AdminStates.choose_hours_date)
    await query.message.edit_text(text="Выберите дату для установления часов:", reply_markup=cal)

@admin.callback_query(AdminProtect(), F.data.startswith("CAL_DAY|"), F.state(AdminStates.choose_hours_date))
async def on_hours_date(query: CallbackQuery, state: FSMContext):
    _, date_str = query.data.split("|", 1)
    await state.update_data(selected_date=date_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏪ Назад", callback_data="AM_BACK_MENU")]
    ])
    await state.set_state(AdminStates.waiting_hours)
    await query.message.edit_text(text=f"Дата: {date_str}\nВведите количество часов на всех сотрудников:", reply_markup=kb)

@admin.message(AdminStates.waiting_hours, AdminProtect())
async def on_input_hours(message: Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        hours = float(text)
    except ValueError:
        return await message.answer(text="Введите число.")
    date_str = (await state.get_data()).get("selected_date")
    # assign same hours to all waiters
    for tg in get_all_waiters():
        add_shift(tg, date_str)
        set_shift_hours(tg, date_str, hours)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏪ Назад", callback_data="AM_BACK_MENU")]
    ])
    await message.answer(text=f"Часы сохранены: {hours} ч. на {date_str} всем сотрудникам.", reply_markup=kb)
    await state.clear()

# --- Personal schedule calendars ---
@admin.callback_query(AdminProtect(), F.data == "AM_EDIT_SCHEDULE")
async def on_edit_schedule(query: CallbackQuery, state: FSMContext):
    await state.clear()
    waiters = get_all_waiters()
    buttons = [InlineKeyboardButton(text=f"Сотрудник {tg}", callback_data=f"AM_SELECT_W|{tg}") for tg in waiters]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(*buttons)
    kb.add(InlineKeyboardButton(text="⏪ Назад", callback_data="AM_BACK_MENU"))
    await state.set_state(AdminStates.choose_waiter)
    await query.message.edit_text(text="Выберите сотрудника для редактирования графика:", reply_markup=kb)

@admin.callback_query(AdminProtect(), F.data.startswith("AM_SELECT_W|"), F.state(AdminStates.choose_waiter))
async def on_select_waiter(query: CallbackQuery, state: FSMContext):
    _, tg = query.data.split("|",1)
    shifts = get_shifts_for(int(tg))
    year, month = datetime.today().year, datetime.today().month
    cal = make_calendar(year, month, set(shifts.keys()))
    # rewrite day callbacks
    new_k = []
    for row in cal.inline_keyboard:
        new_row = []
        for btn in row:
            cd = btn.callback_data
            if cd and cd.startswith("CAL_DAY|"):
                _, d = cd.split("|",1)
                new_row.append(InlineKeyboardButton(text=btn.text, callback_data=f"AM_WDAY|{tg}|{d}"))
            else:
                new_row.append(btn)
        new_k.append(new_row)
    new_k.append([
        InlineKeyboardButton(text="⏪ Назад к выбору", callback_data="AM_EDIT_SCHEDULE")
    ])
    cal = InlineKeyboardMarkup(inline_keyboard=new_k)
    await state.set_state(AdminStates.choose_edit_date)
    await query.message.edit_text(text=f"График сотрудника {tg}:", reply_markup=cal)

@admin.callback_query(AdminProtect(), F.data.startswith("AM_WDAY|"), F.state(AdminStates.choose_edit_date))
async def on_personal_day(query: CallbackQuery, state: FSMContext):
    _, tg, date_str = query.data.split("|",2)
    await state.update_data(selected_tg=int(tg), selected_date=date_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Задачи", callback_data="AM_PERSON_TASKS")],
        [InlineKeyboardButton(text="❌ Без задач", callback_data="AM_RETURN_PERSON")],
        [InlineKeyboardButton(text="⏪ Назад к календарю", callback_data="AM_SELECT_W|{tg}")],
    ])
    await state.set_state(AdminStates.waiting_tasks)
    await query.message.edit_text(text=f"{date_str}, сотрудник {tg}", reply_markup=kb)

@admin.callback_query(AdminProtect(), F.data == "AM_PERSON_TASKS", F.state(AdminStates.waiting_tasks))
async def on_personal_tasks(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(text="Введите список задач для смены:")
    await state.set_state(AdminStates.waiting_hours)

@admin.message(AdminStates.waiting_hours, AdminProtect())
async def on_input_personal_tasks(message: Message, state: FSMContext):
    tasks = message.text.strip()
    data = await state.get_data()
    tg = data.get("selected_tg")
    date_str = data.get("selected_date")
    add_shift(tg, date_str)
    set_shift_tasks(tg, date_str, tasks)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏪ Назад к календарю", callback_data=f"AM_SELECT_W|{tg}")]
    ])
    await message.answer(text="Задачи сохранены.", reply_markup=kb)
    await state.clear()

@admin.callback_query(AdminProtect(), F.data == "AM_RETURN_PERSON", F.state(AdminStates.waiting_tasks))
async def on_return_person(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tg = data.get("selected_tg")
    # recall calendar for tg
    await on_select_waiter(query, state)

# --- Back to menu ---
@admin.callback_query(AdminProtect(), F.data == "AM_BACK_MENU")
async def on_back_menu(query: CallbackQuery, state: FSMContext):
    await cmd_admin_menu(query.message, state)

# --- Salary, notify, export unchanged ---
@admin.callback_query(AdminProtect(), F.data == "AM_CALC_SALARY")
async def on_calc_salary(query: CallbackQuery):
    rate = float(os.getenv("HOURLY_RATE", "0"))
    rows = get_all_shifts()
    text = "<b>Расчёт зарплаты</b>\n"
    total = 0
    for name, date, hrs, tasks in rows:
        pay = hrs * rate
        total += pay
        text += f"{name} {date}: {hrs}ч × {rate} = {pay:.2f}\n"
    text += f"\n<b>Всего выплатить: {total:.2f}</b>"
    await query.message.edit_text(text=text, parse_mode="HTML")

@admin.callback_query(AdminProtect(), F.data == "AM_NOTIFY")
async def on_notify(query: CallbackQuery):
    await query.message.edit_text(text="Оповещение отправлено.")

@admin.callback_query(AdminProtect(), F.data == "AM_EXPORT")
async def on_export(query: CallbackQuery):
    rows = get_all_shifts()
    wb = Workbook()
    ws = wb.active
    ws.append(["Сотрудник", "Дата", "Часы", "Задачи"])
    for name, date, hrs, tasks in rows:
        ws.append([name, date, hrs, tasks])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    await query.message.edit_document(document=FSInputFile(buf, filename="schedule.xlsx"))
