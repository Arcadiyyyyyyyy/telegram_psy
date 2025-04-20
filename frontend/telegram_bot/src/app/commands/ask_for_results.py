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

    tests_passed_by_user = list(
        frontend.shared.src.db.TestAnswersCollection().read({"chat_id": chat_id})
    )

    if not tests_passed_by_user:
        await context.bot.send_message(
            chat_id, "Прежде чем запрашивать результаты, пройди, пожалуйста, тест"
        )
        return

    message = await context.bot.send_message(
        chat_id,
        (
            "В одном из первых сообщений мы обещали поделиться результатами "
            "исследования со всеми желающими, кто поможет нам своими ответами. "
            "\n\nНажав на кнопку ниже можно запросить результаты пройденных "
            "тобой тестов, и интерпретацию результатов."
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Запросить", callback_data="s+ask_for_results")],
                [InlineKeyboardButton("Мне это не нужно", callback_data="d+message")],
            ]
        ),
    )

    if context.user_data is not None:
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(message.id)
        else:
            context.user_data["explainer_message_ids"] = [message.id]


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id
    await frontend.shared.src.utils.remove_all_messages(
        update.effective_chat.id, context
    )

    request_collection = frontend.shared.src.db.ResultRequestsCollection()
    users_collection = frontend.shared.src.db.UsersCollection()

    if request_collection.read_one({"chat_id": chat_id}) is None:
        request_collection.insert_one({"chat_id": chat_id})
        user = users_collection.read_one({"chat_id": chat_id})
        if not user:
            raise ValueError

        for _chat_id in list(users_collection.read({"admin": True})):
            text = (
                f"Пользователь {user.get('first_name', 'error')} "
                f"@{user.get('username', 'error')} {user.get('chat_id', 'error')} "
                " запросил результаты тестов"
            )
            try:
                await context.bot.send_message(
                    _chat_id["chat_id"], text, disable_web_page_preview=True
                )
            except Exception:
                pass

    message = await context.bot.send_message(
        chat_id,
        ("Твоя заявка принята, твои результаты будут обработаны и доставлены."),
    )

    if context.user_data is not None:
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(message.id)
        else:
            context.user_data["explainer_message_ids"] = [message.id]
