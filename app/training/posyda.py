import asyncio

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile


import app.keyboards as kb

posyda = Router()

@posyda.callback_query(F.data == 'povar_star')
async def posyda_star (callback_query: CallbackQuery):
    await callback_query.message.delete()
    note = FSInputFile('/Users/kostakovacev/PycharmProjects/STARODONIE/imge/startof.mp4')
    await callback_query.message.answer_video_note(note,
                                                   reply_markup=kb.posyda1block)


@posyda.message(F.text == 'Погнали!')
async def block1 (message: Message):
    await message.answer('здесь будет вводная информация о работе помошников')

