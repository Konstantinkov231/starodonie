from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, FSInputFile

import app.keyboards as kb  # здесь могут находиться общие клавиатуры и, например, словарь video_note_messages
from app.database import sqlite_db
from app.keyboards import *

waiter = Router()

# ============================================================================
# Тексты уроков на основе материалов документов
# ============================================================================
LESSON1_TEXT = (
    "<b>Урок 1: Внешний вид официанта</b>\n\n"
    "Стандарты внешнего вида работника зала:\n"
    "• Футболка/толстовка согласованного цвета, без рисунков, страз, надписей. Выглаженные.\n"
    "• Шорты свободного кроя бежевого/серого/джинсового оттенков, неспортивные, длина ниже колена.\n"
    "• Джинсы свободного кроя без дыр и потертостей.\n"
    "• Обувь удобная, с закрытым носом, неярких цветов (рекомендуются CROCS).\n"
    "• Волосы у мальчиков: чистые, аккуратные, уложенные (если длинные – собраны); борода допускается только в ухоженном виде.\n"
    "• Волосы у девочек: собраны в пучки, заплетены или заколоты без страз и камней.\n"
    "• Ногти аккуратно подстрижены; у девочек допускается лак пастельных тонов.\n"
    "• Соблюдение гигиены: мытьё рук после посещения туалета/мест для курения (без фартука).\n"
    "• Фирменный фартук должен быть чистым и выглаженным, значки и нашивки – только по согласованию.\n"
    "• Духи/туалетная вода – легких оттенков, без резких запахов.\n"
    "• И, самое главное, улыбайся – твое настроение читается окружающими!\n"
    "\n"
    "Если ты всё понял, то скорее жмякни эту манящую кнопочку"
)

LESSON2_TEXT = (
    "<b>Урок 2: Здесь мы разберём с вами 4 главных аспекта работы, наши ценности:\n\n "
    "Ответственность</b>\n\n"
    "• Мы работаем честно.\n"
    "• Осознаем свою и общую ответственность перед собой, коллегами и гостями.\n"
    "• Честно говорим о допущенных ошибках и несем за них ответственность.\n"
    "• Выполняем вовремя все взятые на себя обязательства.\n\n"
    "<b>Забота</b>\n"
    "• Мы любим наших гостей и заботимся о них, как о самых дорогих членах нашей семьи.\n"
    "• Создаем особую атмосферу, дарим гостям впечатления и эмоции.\n"
    "• Бережем и поддерживаем семейные традиции.\n\n"
    "<b>Развитие</b>\n"
    "• Проявляем творческий подход в поиске решений.\n"
    "• Постоянно развиваемся и ищем возможности для реализации новых идей.\n\n"
    "<b>Команда</b>\n\n"
    "• Ценим вклад каждого сотрудника.\n"
    "• Помогаем друг другу, работая сообща.\n"
    "• Создаем единую команду, где каждый важен.\n"
)

LESSON3_TEXT = (
    "<b>Урок 3: Правила работы официанта</b>\n\n"
    "<b>Правило 1: Пунктуальность</b>\n"
    "• Всегда приходите на работу вовремя. При задержке – предупредите менеджера.\n\n"
    "<b>Правило 2: Поведение в зале</b>\n"
    "• Не пользуйтесь мобильными телефонами, не жуйте резинку, не принимайте пищу и напитки во время работы.\n\n"
    "<b>Правило 3: Трудовая дисциплина</b>\n"
    "• Качественно выполняйте порученную работу, уважайте коллег и руководство.\n\n"
    "<b>Правило 4: Общение и помощь коллегам</b>\n"
    "• Работайте в команде, помогайте друг другу и просите о помощи, когда необходимо.\n\n"
    "Дополнительно:\n"
    "• Следите за чистотой зала: проводите утреннюю уборку, проверяйте станцию официанта.\n"
    "• Соблюдайте технику сервировки столов и подаче блюд и напитков.\n"
)

LESSON4_TEXT = (
    '<b>Работа с подносом</b>\n'
    'Основные правила работы с подносом:\n'
    '• Поднос необходимо носить на одной руке: легкий на пальцах, тяжелый на ладони.\n'
    '• Поднос держат не выше плеча и не ниже локтя.\n'
    '• Пустой поднос носят, опустив вниз перпендикулярно полу.\n'
    '• Все барное стекло (графины, бокалы, чайники, пиалы) разрешается носить только на подносе.\n\n'
    'ЗАПРЕЩЕНО!!!\n'
    '• Носить поднос «Под мышкой»\n'
    '• Носить двумя руками перед собой, т.е. как «таз».\n'
    '• Подбрасывать, крутить поднос на пальце.\n'
    '• При подаче блюд держать поднос над столом.\n'
    '• Ставить поднос на стол, стулья, диваны!\n'
    '• Одновременно на одном подносе носить блюда и грязную посуду.\n'
)

LESSON5_TEXT = (
    '<b>Здесь мы с тобой разберём шаги обслуживания:</b>\n'
    '<b>ШАГ 1. ВСТРЕЧА И ПРИВЕТСТВИЕ ГОСТЕЙ</b>\n'
    '• Поприветствуйте Гостя, входящего в кафе;\n'
    '• Узнайте, был ли зарезервирован столик;\n'
    '• Узнайте предпочтения Гостя в выборе зала (зал или терраса)\n'
    '• Проводите Гостя к столу;\n'
    '• Подайте меню;\n'
    '• Пожелайте приятного отдыха.\n\n'
    '<b>ШАГ 2. ЗНАКОМСТВО, ПРИНЯТИЕ ЗАКАЗА НА АПЕРИТИВ И ЕГО ПОДАЧА</b>\n'
    '• Подойдите к столу в течение 3 минут, после посадки Гостя;\n'
    '• Поприветствуйте Гостя и представьтесь;\n'
    '• Предложите и порекомендуйте Гостю аперитивы;\n'
    '• Проинформируйте гостя о скидках, акциях действующих в данный момент времени;\n'
    '• Внимательно и грамотно запишите заказ, учитывая пожелания каждого Гостя;\n'
    '• Повторите заказ Гостя со всеми его пожеланиями;\n'
    '• Пробейте заказ в кассе, передайте на кухню;\n'
    '• Получите заказанные аперитивы в баре;\n'
    '• Подайте аперитивы. При подаче напитка, обязательно назовите его.\n\n'
    '<b>ШАГ 3. ПРИНЯТИЕ И ВЫПОЛНЕНИЕ ОСНОВНОГО ЗАКАЗА</b>\n'
    '• Порекомендуйте Гостю закуски, супы, основные блюда;\n'
    '• Предупредить о времени приготовления блюд\n'
    '• Предложите дополнительные блюда, напитки, гарниры, лепешку, десерты, соусы;\n'
    '• Повторите заказ;\n'
    '• Уточните последовательность подачи блюд;\n'
    '• Время приготовления: Салат 15-25 минут после заказа, горячие блюда – в течение 15 – 30 мин, десерт в течение 10-15 мин.\n'
    '• Заберите меню.\n'
    '• Введите заказ в кассу, учитывая пожелания Гостей (например: без лука, без чеснока, одновременно, позже)\n'
    '• Засервируйте стол в соответствии с заказом;\n'
    '• Подайте Гостю блюда;\n'
    '• Поинтересуйтесь, понадобятся ли дополнительные соуса и специи;\n'
    '• Предложите дополнительные напитки;\n\n'
    '<b>ШАГ 4. КОНТРОЛЬ КАЧЕСТВА БЛЮД CHECK BACK.</b>\n'
    '• Узнайте мнение Гостя о блюде. Выбирайте удобный момент. Это можно сделать:\n'
    '• сразу после того, как Гость попробовал блюдо или напиток;\n'
    '• во время уборки посуды;\n'
    '• при негативной реакции Гостя (отодвинул тарелку, попробовал - не довольноелицо).\n\n'
    '<b>ШАГ 5. ПРЕДЛОЖЕНИЕ ДЕСЕРТОВ, ГОРЯЧИХ НАПИТКОВ И ДИЖЕСТИВОВ.</b>\n'
    '• Вовремя уберите со стола грязную посуду и приборы;\n'
    '• Предложите Гостю горячие напитки, дижестивы, десерты;\n\n'
    '<b>ШАГ 6. РАСЧЕТ И ПРОЩАНИЕ С ГОСТЕМ.</b>\n'
    '• По первой просьбе Гостя принесите предчек в корзине, не более 3-х минут\n'
    '• Рассчитайте Гостя;\n'
    '• Принесите сдачу в течение 4-х минут\n'
    '• Попрощайтесь с Гостем и пригласите его прийти снова;\n'
    '• Пересервируйте стол, приведите в порядок диван, подушки и пол вокруг стола.'
)

LESSON6_TEXT = (
    '<b>Cервировка стола во время обслуживания:</b>bn\n'
    '. Сервировка стола столовыми приборами.\n'
    'Oсновные правила:\n'
    '• Лезвие ножа всегда «смотрит» влево.\n'
    '• Вилки кладут выпуклой частью на стол\n'
    '• Приборы всегда подаются до начала трапезы или одновременно с блюдом. НО сначала приборы, а затем блюдо.\n'
    '• Приборы устанавливаются с правой стороны от Гостя.\n'
    '• «Убирать посуду и приборы, на которых осталась еда (напитки), можно только с разрешения Гостя, спросив: «С Вашего разрешения я заберу тарелку», «...бокал», «Позвольте....». Во всех остальных случаях грязная посуда убирается молча и, по возможности, незаметно».\n'
    '<b>Подача бокалов, стаканов</b>\n\n'
    'ВНИМАНИЕ!\n'
    'Всю стеклянную посуду разрешается носить ТОЛЬКО на подносе!!!\n'
    '• Подают и убирают бокалы (стаканы) держа за ножку или донную часть.\n'
    '• Ни в коем случае нельзя дотрагиваться до верхней части бокалов из гигиенических соображений, тем более, если они уже находились в употреблении.\n'
)


# ============================================================================
# Состояния для теста
# ============================================================================
class TestStates(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    q7 = State()
    q8 = State()
    q9 = State()
    q10 = State()
    q11 = State()
    q12 = State()
    q13 = State()
    q14 = State()
    q15 = State()
    q16 = State()
    q17 = State()
    q18 = State()


# ============================================================================
# Сохранённые ранее обработчики (если нужны для альтернативной логики)
# ============================================================================
@waiter.callback_query(F.data == "ofik")
async def per_block(callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    # Добавляем Telegram ID официанта в таблицу waiters
    sqlite_db.add_waiter(user_id)

    # Если ранее отправлялось видео-сообщение, удаляем его
    if user_id in kb.video_note_messages:
        try:
            await callback_query.bot.delete_message(chat_id=chat_id, message_id=kb.video_note_messages[user_id])
        except Exception as e:
            print(f"Ошибка при удалении видео-заметки: {e}")
        finally:
            kb.video_note_messages.pop(user_id, None)

    # Подтверждаем callback-запрос без текста (чтобы не показывалось всплывающее окно)
    await callback_query.answer()
#'/Users/kostakovacev/PycharmProjects/STARODONIE/imge/startof.mp4'
    # Отправляем видеосообщение startof.mp4 с нужной клавиатурой
    video_note = FSInputFile('/root/bot/imge/startof.mp4')
    sent_message = await callback_query.bot.send_video_note(
        chat_id=chat_id,
        video_note=video_note,
        reply_markup=kb.ofik_skip
    )

    # Сохраняем id отправленного сообщения, если понадобится его удалить в будущем
    kb.video_note_messages[user_id] = sent_message.message_id


@waiter.callback_query(F.data == "skip1")
async def start_training(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Начинаем с урока 1: Внешний вид официанта
    await callback_query.message.answer(LESSON1_TEXT, parse_mode="HTML", reply_markup=kb.lesson1_kb)
    await state.clear()

@waiter.callback_query(F.data == "lesson1_next")
async def lesson1_next(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Урок 2: Ответственность
    await callback_query.message.answer(LESSON2_TEXT, parse_mode="HTML", reply_markup=kb.lesson2_kb)

@waiter.callback_query(F.data == "lesson2_next")
async def lesson2_next(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Урок 3: Забота
    await callback_query.message.answer(LESSON3_TEXT, parse_mode="HTML", reply_markup=kb.lesson3_kb)

@waiter.callback_query(F.data == "lesson3_next")
async def lesson3_next(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Урок 4: Развитие
    await callback_query.message.answer(LESSON4_TEXT, parse_mode="HTML", reply_markup=kb.lesson4_kb)

@waiter.callback_query(F.data == "lesson4_next")
async def lesson4_next(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Урок 5: Команда
    await callback_query.message.answer(LESSON5_TEXT, parse_mode="HTML", reply_markup=kb.lesson5_kb)

@waiter.callback_query(F.data == "lesson5_next")
async def lesson5_next(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Урок 6: Правила работы официанта
    await callback_query.message.answer(LESSON6_TEXT, parse_mode="HTML", reply_markup=kb.lesson6_kb)

# ============================================================================
# Обработчики теста
# ============================================================================
@waiter.callback_query(F.data == "start_test")
async def start_new_test(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    # Инициализируем счет теста
    await state.update_data(score=0)
    question1 = "<b>Вопрос 1:</b> Какие украшения допускаются для официанта-девушки?"
    await callback_query.message.answer(question1, parse_mode="HTML", reply_markup=kb.new_test_q1_kb)
    await state.set_state(TestStates.q1)

@waiter.callback_query(F.data.in_(["new_q1_right", "new_q1_wrong"]))
async def answer_new_q1(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q1_right":
        feedback = "Правильно! Допускаются серьги-гвоздики или кольца диаметром до 3 см."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: серьги-гвоздики или кольца диаметром до 3 см."
    await state.update_data(score=score)
    question2 = "<b>Вопрос 2:</b> Какой должна быть обувь официанта?"
    await callback_query.message.answer(question2, parse_mode="HTML", reply_markup=kb.new_test_q2_kb)
    await state.set_state(TestStates.q2)

@waiter.callback_query(F.data.in_(["new_q2_right", "new_q2_wrong"]))
async def answer_new_q2(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q2_right":
        feedback = "Верно! Официант должен носить удобную обувь с закрытым носом, неброских цветов."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: удобная, с закрытым носом, неброских цветов."
    await state.update_data(score=score)
    question3 = "<b>Вопрос 3:</b> Как должны быть уложены волосы у официанта-мужчины, если они длинные?"
    await callback_query.message.answer(question3, parse_mode="HTML", reply_markup=kb.new_test_q3_kb)
    await state.set_state(TestStates.q3)

@waiter.callback_query(F.data.in_(["new_q3_right", "new_q3_wrong"]))
async def answer_new_q3(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q3_right":
        feedback = "Правильно! Волосы должны быть собраны."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: волосы должны быть собраны."
    await state.update_data(score=score)
    question4 = "<b>Вопрос 4:</b> Что категорически запрещено официантам делать в зале?"
    await callback_query.message.answer(question4, parse_mode="HTML", reply_markup=kb.new_test_q4_kb)
    await state.set_state(TestStates.q4)

@waiter.callback_query(F.data.in_(["new_q4_right", "new_q4_wrong"]))
async def answer_new_q4(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q4_right":
        feedback = "Верно! Официантам запрещено пользоваться мобильными телефонами."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: пользоваться мобильными телефонами."
    await state.update_data(score=score)
    question5 = "<b>Вопрос 5:</b> Как нужно носить поднос с напитками и блюдами?"
    await callback_query.message.answer(question5, parse_mode="HTML", reply_markup=kb.new_test_q5_kb)
    await state.set_state(TestStates.q5)

@waiter.callback_query(F.data.in_(["new_q5_right", "new_q5_wrong"]))
async def answer_new_q5(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q5_right":
        feedback = "Верно! Поднос носят только на одной руке, легкий на пальцах, тяжелый на ладони."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: только на одной руке, легкий на пальцах, тяжелый на ладони."
    await state.update_data(score=score)
    question6 = "<b>Вопрос 6:</b> В течение какого времени официант должен подойти к гостю после посадки?"
    await callback_query.message.answer(question6, parse_mode="HTML", reply_markup=kb.new_test_q6_kb)
    await state.set_state(TestStates.q6)

@waiter.callback_query(F.data.in_(["new_q6_right", "new_q6_wrong"]))
async def answer_new_q6(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q6_right":
        feedback = "Верно! Официант должен подойти к гостю в течение 3 минут."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: в течение 3 минут."
    await state.update_data(score=score)
    question7 = "<b>Вопрос 7:</b> Когда необходимо предложить гостям десерты и горячие напитки?"
    await callback_query.message.answer(question7, parse_mode="HTML", reply_markup=kb.new_test_q7_kb)
    await state.set_state(TestStates.q7)

@waiter.callback_query(F.data.in_(["new_q7_right", "new_q7_wrong"]))
async def answer_new_q7(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q7_right":
        feedback = "Верно! Предложение должно происходить после того, как убрана грязная посуда со стола."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: после того, как убрана грязная посуда со стола."
    await state.update_data(score=score)
    question8 = "<b>Вопрос 8:</b> Какой первый шаг в работе с возражениями гостей?"
    await callback_query.message.answer(question8, parse_mode="HTML", reply_markup=kb.new_test_q8_kb)
    await state.set_state(TestStates.q8)

@waiter.callback_query(F.data.in_(["new_q8_right", "new_q8_wrong"]))
async def answer_new_q8(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q8_right":
        feedback = "Верно! Первым шагом является выслушать гостя до конца."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: выслушать гостя до конца."
    await state.update_data(score=score)
    question9 = "<b>Вопрос 9:</b> Какая из перечисленных ценностей НЕ относится к ресторану Стародонье?"
    await callback_query.message.answer(question9, parse_mode="HTML", reply_markup=kb.new_test_q9_kb)
    await state.set_state(TestStates.q9)

@waiter.callback_query(F.data.in_(["new_q9_right", "new_q9_wrong"]))
async def answer_new_q9(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q9_right":
        feedback = "Отлично! Конкуренция – это ценность, которая не соответствует ценностям ресторана Стародонье."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: конкуренция."
    await state.update_data(score=score)
    question10 = "<b>Вопрос 10:</b> Какие головные уборы допускаются для официанта?"
    await callback_query.message.answer(question10, parse_mode="HTML", reply_markup=kb.new_test_q10_kb)
    await state.set_state(TestStates.q10)

@waiter.callback_query(F.data.in_(["new_q10_right", "new_q10_wrong"]))
async def answer_new_q10(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q10_right":
        feedback = "Верно! Фирменный головной убор допускается."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: фирменный головной убор."
    await state.update_data(score=score)
    question11 = "<b>Вопрос 11:</b> Какой должен быть стиль макияжа официантки?"
    await callback_query.message.answer(question11, parse_mode="HTML", reply_markup=kb.new_test_q11_kb)
    await state.set_state(TestStates.q11)

@waiter.callback_query(F.data.in_(["new_q11_right", "new_q11_wrong"]))
async def answer_new_q11(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q11_right":
        feedback = "Верно! Нейтральный и естественный макияж предпочтителен."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: нейтральный и естественный макияж."
    await state.update_data(score=score)
    question12 = "<b>Вопрос 12:</b> Как правильно ухаживать за униформой официанта?"
    await callback_query.message.answer(question12, parse_mode="HTML", reply_markup=kb.new_test_q12_kb)
    await state.set_state(TestStates.q12)

@waiter.callback_query(F.data.in_(["new_q12_right", "new_q12_wrong"]))
async def answer_new_q12(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q12_right":
        feedback = "Верно! Униформа должна быть всегда чистой и выглаженной."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: всегда чистая и выглаженная униформа."
    await state.update_data(score=score)
    question13 = "<b>Вопрос 13:</b> Что является проявлением профессионализма на рабочем месте?"
    await callback_query.message.answer(question13, parse_mode="HTML", reply_markup=kb.new_test_q13_kb)
    await state.set_state(TestStates.q13)

@waiter.callback_query(F.data.in_(["new_q13_right", "new_q13_wrong"]))
async def answer_new_q13(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q13_right":
        feedback = "Верно! Своевременное выполнение обязанностей и аккуратный внешний вид – проявление профессионализма."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: своевременное выполнение обязанностей и аккуратный внешний вид."
    await state.update_data(score=score)
    question14 = "<b>Вопрос 14:</b> Какие действия способствуют улучшению клиентского опыта?"
    await callback_query.message.answer(question14, parse_mode="HTML", reply_markup=kb.new_test_q14_kb)
    await state.set_state(TestStates.q14)

@waiter.callback_query(F.data.in_(["new_q14_right", "new_q14_wrong"]))
async def answer_new_q14(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q14_right":
        feedback = "Верно! Внимательное отношение и готовность помочь значительно улучшают клиентский опыт."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: внимательное отношение и готовность помочь."
    await state.update_data(score=score)
    question15 = "<b>Вопрос 15:</b> Как правильно обслуживать стол без нарушения этикета?"
    await callback_query.message.answer(question15, parse_mode="HTML", reply_markup=kb.new_test_q15_kb)
    await state.set_state(TestStates.q15)

@waiter.callback_query(F.data.in_(["new_q15_right", "new_q15_wrong"]))
async def answer_new_q15(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q15_right":
        feedback = "Верно! Следование стандартам сервировки – залог правильного обслуживания."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: следовать установленным стандартам сервировки."
    await state.update_data(score=score)
    question16 = "<b>Вопрос 16:</b> Какую роль играет коммуникация с гостями при заказе напитков?"
    await callback_query.message.answer(question16, parse_mode="HTML", reply_markup=kb.new_test_q16_kb)
    await state.set_state(TestStates.q16)

@waiter.callback_query(F.data.in_(["new_q16_right", "new_q16_wrong"]))
async def answer_new_q16(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q16_right":
        feedback = "Верно! Точная коммуникация помогает удовлетворить пожелания гостя."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: коммуникация позволяет точно определить пожелания гостя."
    await state.update_data(score=score)
    question17 = "<b>Вопрос 17:</b> Как официант должен реагировать на жалобы клиента?"
    await callback_query.message.answer(question17, parse_mode="HTML", reply_markup=kb.new_test_q17_kb)
    await state.set_state(TestStates.q17)

@waiter.callback_query(F.data.in_(["new_q17_right", "new_q17_wrong"]))
async def answer_new_q17(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q17_right":
        feedback = "Верно! Выслушать жалобу, извиниться и предложить решение – оптимальная реакция."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: выслушать жалобу, извиниться и предложить решение."
    await state.update_data(score=score)
    question18 = "<b>Вопрос 18:</b> Какие принципы работы в команде наиболее важны для ресторана Стародонье?"
    await callback_query.message.answer(question18, parse_mode="HTML", reply_markup=kb.new_test_q18_kb)
    await state.set_state(TestStates.q18)

@waiter.callback_query(F.data.in_(["new_q18_right", "new_q18_wrong"]))
async def answer_new_q18(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0)
    if callback_query.data == "new_q18_right":
        feedback = "Отлично! Взаимное уважение и поддержка – ключевые принципы."
        score += 1
    else:
        feedback = "Неверно. Правильный ответ: взаимное уважение и поддержка."
    await state.update_data(score=score)
    data = await state.get_data()  # Получаем финальный счет
    final_score = data.get("score", 0)
    final_text = (
        f"{feedback}\n\n"
        "Поздравляем, вы прошли тест!\n"
        "Спасибо за прохождение теста! Будем рады видеть вас в нашем Telegram‑форуме.\n\n"
        f"Ваш результат: {final_score} из 18."
    )
    # Записываем результат в базу
    tg_id = callback_query.from_user.id
    sqlite_db.add_test_result(tg_id, final_score, 18)
    forum_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти в форум", url="https://t.me/your_forum")]
    ])
    await callback_query.message.answer(final_text, parse_mode="HTML", reply_markup=forum_keyboard)
    await state.clear()