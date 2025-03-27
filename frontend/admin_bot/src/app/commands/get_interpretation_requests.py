import uuid

from telegram import (
    Update,
)
from telegram.ext import ContextTypes

import frontend.admin_bot.src.app.middleware
import frontend.shared.src.db
import frontend.shared.src.file_manager
import frontend.shared.src.middleware
import frontend.shared.src.utils


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if update.effective_chat is None:
        return
    _chat_id = update.effective_chat.id

    users_collection = frontend.shared.src.db.UsersCollection()
    requests_collection = frontend.shared.src.db.ResultRequestsCollection()

    text = ""

    for request in list(requests_collection.read({})):
        user = users_collection.read_one({"chat_id": request["chat_id"]})
        if user is None:
            user = {}

        text += f"{user['first_name']} | {user['username']} | {user['chat_id']}\n"

    await context.bot.send_message(_chat_id, text)
