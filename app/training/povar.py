import asyncio

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile

import app.keyboards as kb

povar = Router()

@povar.callback_query(F.data == 'povar_star')
async def povar_start(callback_query: CallbackQuery):
    await callback_query.message.delete()
    note = FSInputFile('/Users/kostakovacev/PycharmProjects/STARODONIE/imge/startof.mp4')
    await callback_query.message.answer_video_note(note,
                                                   reply_markup=kb.povar1block)

@povar.message(F.text == "НУ приступим-с")
async def povar_block1 (message: Message):
    await message.answer('здесь будет вводная информация про кухню')