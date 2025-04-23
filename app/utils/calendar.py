# app/utils/calendar.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import calendar


def make_calendar(year: int, month: int, marked: set[str]) -> InlineKeyboardMarkup:
    """
    Генерирует inline-календарь на указанный месяц.
    marked — множество дат 'YYYY-MM-DD', на которые нужно поставить галочку.
    """
    keyboard: list[list[InlineKeyboardButton]] = []

    # Шапка с навигацией
    keyboard.append([
        InlineKeyboardButton("‹", callback_data=f"CAL_PREV|{year}|{month}"),
        InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
        InlineKeyboardButton("›", callback_data=f"CAL_NEXT|{year}|{month}"),
    ])

    # Дни недели
    keyboard.append([
        InlineKeyboardButton(day, callback_data="IGNORE")
        for day in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])

    # Недели месяца
    cal = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    for week in cal:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                # Пустая клетка
                row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
            else:
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                mark = "✓" if date_str in marked else ""
                row.append(
                    InlineKeyboardButton(f"{day}{mark}", callback_data=f"CAL_DAY|{date_str}")
                )
        keyboard.append(row)

    # Кнопка отмены
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="CAL_CANCEL")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
