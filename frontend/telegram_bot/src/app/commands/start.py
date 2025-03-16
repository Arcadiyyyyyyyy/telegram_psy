from telegram import Update
from telegram.ext import ContextTypes

import frontend.shared.src.middleware
import frontend.telegram_bot
import frontend.telegram_bot.src
import frontend.telegram_bot.src.app
import frontend.telegram_bot.src.app.commands
import frontend.telegram_bot.src.app.commands.menu


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.from_user is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)

    await frontend.telegram_bot.src.app.commands.menu.command(update, context)
