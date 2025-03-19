import arrow
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.utils


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id
    await frontend.shared.src.utils.remove_all_messages(
        update.effective_chat.id, context
    )

    keyboard: list[list[InlineKeyboardButton]] = []

    user_have_passed_iq_test = False
    user_have_passed_atq_test = False

    test_answers_collection = frontend.shared.src.db.TestAnswersCollection()
    if (
        test_answers_collection.read_one({"chat_id": chat_id, "test_name": "iq"})
        is not None
    ):
        user_have_passed_iq_test = True
    if (
        test_answers_collection.read_one({"chat_id": chat_id, "test_name": "atq"})
        is not None
    ):
        user_have_passed_atq_test = True
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

    if not user_have_passed_iq_test:
        keyboard.append(
            [InlineKeyboardButton("Пройти IQ тест", callback_data="r+iqstart")]
        )
    if not user_have_passed_atq_test:
        keyboard.append(
            [InlineKeyboardButton("Пройти ATQ тест", callback_data="r+atqstart")]
        )

    if blocked_slots:
        # Show scheduled calls
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Подтвержденные интервью", callback_data="r+list_calls"
                )
            ]
        )
    else:
        # Schedule calls
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Запланировать интервью", callback_data="r+schedule_call"
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("Сообщить о проблеме", callback_data="r+help")]
    )

    message = await context.bot.send_message(
        chat_id,
        "Главное меню",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    if context.user_data is not None:
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(message.id)
        else:
            context.user_data["explainer_message_ids"] = [message.id]
