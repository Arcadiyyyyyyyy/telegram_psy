from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.middleware
import frontend.telegram_bot
import frontend.telegram_bot.src
import frontend.telegram_bot.src.app
import frontend.telegram_bot.src.app.commands
import frontend.telegram_bot.src.app.commands.menu


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id,
        "Привет!\n\nСпасибо, что согласился принять участие в нашем исследовании. \n"
        "Мы команда исследователей, которые хотят изучить взаимосвязь личностных характеристик и рабочей эффективности. \n"
        "Участие в исследовании полностью добровольное, это значит, что ты можешь прекратить в любой момент. \n"
        "Но мы очень будем признательны, если ты пройдешь исследование целиком. \n"
        "Данные будут полностью анонимизированы и доступны только исследовательской команде. \n"
        "Продолжая общение с ботом ты даешь право на сбор, обработку и хранение своей персональной информации.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Продолжить", callback_data="r+menu"),
                    InlineKeyboardButton("Выйти", callback_data="d+message"),
                ]
            ]
        ),
    )

    # await frontend.telegram_bot.src.app.commands.menu.command(update, context)
