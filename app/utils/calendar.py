from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import calendar


def make_calendar(year: int, month: int, marked: set[str]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []

    # Шапка с навигацией
    keyboard.append([
        InlineKeyboardButton(text="‹", callback_data=f"CAL_PREV|{year}|{month}"),
        InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="IGNORE"),
        InlineKeyboardButton(text="›", callback_data=f"CAL_NEXT|{year}|{month}"),
    ])

    # Дни недели
    keyboard.append([
        InlineKeyboardButton(text=day, callback_data="IGNORE")
        for day in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    ])

    # Недели месяца
    cal = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    for week in cal:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="IGNORE"))
            else:
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                mark = "✓" if date_str in marked else ""
                row.append(
                    InlineKeyboardButton(text=f"{day}{mark}", callback_data=f"CAL_DAY|{date_str}")
                )
        keyboard.append(row)

    # Кнопка отмены
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="CAL_CANCEL")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
