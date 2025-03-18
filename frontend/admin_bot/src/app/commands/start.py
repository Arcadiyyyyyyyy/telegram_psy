from telegram import Update
from telegram.ext import ContextTypes

import frontend.admin_bot
import frontend.admin_bot.src
import frontend.admin_bot.src.app
import frontend.admin_bot.src.app.middleware
import frontend.shared.src.middleware


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.from_user is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    chat_id = update.message.chat.id

    await context.bot.send_message(chat_id, "Привет!")
