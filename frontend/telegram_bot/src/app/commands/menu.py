import arrow
from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.db
import frontend.shared.src.middleware


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id

    keyboard: list[list[InlineKeyboardButton]] = []

    user_have_not_passed_iq_test = False
    user_have_not_passed_atq_test = False

    test_answers_collection = frontend.shared.src.db.TestAnswersCollection()
    if (
        test_answers_collection.read_one({"chat_id": chat_id, "test_name": "iq"})
        is None
    ):
        user_have_not_passed_iq_test = True
    if (
        test_answers_collection.read_one({"chat_id": chat_id, "test_name": "atq"})
        is None
    ):
        user_have_not_passed_atq_test = True
    blocked_slots = list(
        frontend.shared.src.db.TimeSlotsCollection().read(
            {
                "time": {
                    "$gte": arrow.utcnow().datetime,
                },
                "meeting_link": {"$exists": 1},
                "chat_id": int(chat_id),
            }
        )
    )

    if user_have_not_passed_iq_test:
        keyboard.append([InlineKeyboardButton("Пройти IQ тест", callback_data="r+iqstart")])
    if user_have_not_passed_atq_test:
        keyboard.append(
            [InlineKeyboardButton("Пройти ATQ тест", callback_data="r+atqstart")]
        )

    if blocked_slots:
        logger.warning(blocked_slots)
        # Show scheduled calls
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Список запланированных звонков", callback_data="r+list_calls"
                )
            ]
        )
    else:
        # Schedule calls
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Запланировать звонок с психологом", callback_data="r+schedule_call"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("Сообщить о проблеме", callback_data="r+help")]
    )

    await context.bot.send_message(
        chat_id,
        "Главное меню",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
