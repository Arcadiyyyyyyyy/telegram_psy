from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.middleware
import frontend.shared.src.utils
import frontend.telegram_bot
import frontend.telegram_bot.src
import frontend.telegram_bot.src.app
import frontend.telegram_bot.src.app.commands
import frontend.telegram_bot.src.app.commands.menu


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None or context.user_data is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id
    await frontend.shared.src.utils.remove_all_messages(
        update.effective_chat.id, context
    )

    message = await context.bot.send_message(
        chat_id,
        "Привет!\n\nСпасибо, что согласился принять участие в нашем исследовании. \n"  # noqa
        "Мы команда исследователей, которые хотят изучить взаимосвязь личностных характеристик и рабочей эффективности. \n"  # noqa
        "Участие в исследовании полностью добровольное, это значит, что ты можешь прекратить в любой момент. \n"  # noqa
        "Но мы очень будем признательны, если ты пройдешь исследование целиком. \n"  # noqa
        "Данные будут полностью анонимизированы и доступны только исследовательской команде. \n"  # noqa
        "Продолжая общение с ботом ты даешь право на сбор, обработку и хранение своей персональной информации.\n\n"  # noqa
        "В качестве благодарности мы можем выслать тебе результаты теста IQ и теста на определение темперамента.",  # noqa
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Продолжить", callback_data="s+notify_about_pipeline"
                    ),
                    InlineKeyboardButton("Выйти", callback_data="d+message"),
                ]
            ]
        ),
    )
    if context.user_data.get("explainer_message_ids") is not None:
        context.user_data["explainer_message_ids"].append(message.id)


async def notify_about_the_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None or context.user_data is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id

    message = await context.bot.send_message(
        chat_id,
        "Отлично! Наше исследование состоит из трех частей: двух тестов в этом боте и интервью. \n"  # noqa
        "Для прохождения двух тестов нужно выделить не менее 15 минут в тихом месте, где ты сможешь сконцентрироваться. \n"  # noqa
        "Это особенно важно для теста IQ, так как в нем есть ограничения по времени на каждую часть.\n"  # noqa
        "После прохождения тестов запишись, пожалуйста, на интервью. \n"
        "На него нужно выделить не менее 90 минут.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Хорошо", callback_data="r+menu"),
                ]
            ]
        ),
    )
    if context.user_data.get("explainer_message_ids") is not None:
        context.user_data["explainer_message_ids"].append(message.id)
