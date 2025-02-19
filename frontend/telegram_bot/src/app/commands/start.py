from telegram import Update
from telegram.ext import ContextTypes

import frontend.shared.src.middleware


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.from_user is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)

    await context.bot.send_message(
        update.message.chat.id, "Привет! \n\n/atq или /iq для прототипа"
    )  # TODO: change text
