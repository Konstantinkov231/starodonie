from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import calendar


def make_calendar(year: int, month: int, marked: set) -> InlineKeyboardMarkup:
    """
    marked — множество строк 'YYYY-MM-DD', которые помечаем ✓
    """
    kb = InlineKeyboardMarkup(row_width=7)
    # шапка с навигацией
    kb.row(
        InlineKeyboardButton("<", callback_data=f"CAL_PREV|{year}|{month}"),
        InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
        InlineKeyboardButton(">", callback_data=f"CAL_NEXT|{year}|{month}")
    )
    # дни недели
    for day in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]:
        kb.insert(InlineKeyboardButton(day, callback_data="IGNORE"))
    # числа
    month_cal = calendar.Calendar(firstweekday=0).itermonthdays(year, month)
    for day in month_cal:
        if day == 0:
            kb.insert(InlineKeyboardButton(" ", callback_data="IGNORE"))
        else:
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            mark = "✓" if date_str in marked else ""
            kb.insert(InlineKeyboardButton(f"{day}{mark}", callback_data=f"CAL_DAY|{date_str}"))
    # кнопка «Отмена»
    kb.row(InlineKeyboardButton("❌ Отмена", callback_data="CAL_CANCEL"))
    return kb
