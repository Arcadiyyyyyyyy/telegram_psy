from telegram import Update
from telegram.ext import ContextTypes

import frontend.shared.src.db


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat is None:
        raise ValueError
    chat_id = update.effective_chat.id

    users_collection = frontend.shared.src.db.UsersCollection()
    user = users_collection.read_one({"chat_id": chat_id})
    if user is None:
        raise ValueError
    user_admin_status = user.get("admin", False)

    if user_admin_status is True:
        return True
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="К сожалению, этим ботом могут пользоваться только админы",
        )
        return False
