import arrow
from telegram import Update
from telegram.ext import ContextTypes

import frontend.admin_bot
import frontend.admin_bot.src
import frontend.admin_bot.src.app
import frontend.admin_bot.src.app.middleware
import frontend.shared.src.db
import frontend.shared.src.middleware


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.from_user is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    chat_id = update.message.chat.id
    users = frontend.shared.src.db.UsersCollection()
    time_slots = frontend.shared.src.db.TimeSlotsCollection()
    scheduled_calls = list(
        time_slots.read(
            {"time": {"$gte": arrow.utcnow().datetime}, "meeting_link": {"$exists": 1}}
        )
    )
    result: list[str] = ["Вот список запланированных звонков: \n"]
    for call in scheduled_calls:
        user = users.read_one({"chat_id": call["chat_id"]})
        if not user:
            raise ValueError
        result.append(
            f"{arrow.get(call.get('time')).shift(hours=3).format('YYYY-MM-DD HH:mm')} with {user.get('first_name', 'error')} {user.get('username', 'error')} {user.get('chat_id', 'error')}"
        )
    else:
        result.append("У вас ещё нет подтверждённых звонков")

    await context.bot.send_message(chat_id, "\n".join(result))
