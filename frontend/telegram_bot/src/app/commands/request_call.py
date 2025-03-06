import arrow
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.admin_bot
import frontend.admin_bot.src
import frontend.admin_bot.src.app
import frontend.admin_bot.src.app.commands
import frontend.admin_bot.src.app.commands.manage_time_slots
import frontend.shared.src.db
import frontend.shared.src.middleware


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if update.message is None or update.message.from_user is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)

    await context.bot.send_message(
        update.message.chat.id,
        "Привет! \n\nТут можно выбрать время для консультации с нашими специалистами",
        reply_markup=frontend.admin_bot.src.app.commands.manage_time_slots.generate_available_time_slots_keyboard(
            "user", page=page
        ),
    )


async def request_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await frontend.shared.src.middleware.main_handler(update, context)
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    users_collection = frontend.shared.src.db.UsersCollection()
    admins = list(users_collection.read({"admin": True}))
    user = users_collection.read_one({"chat_id": chat_id})
    if user is None:
        raise ValueError

    query = update.callback_query
    if query is None:
        raise ValueError("Callback distributor must only receive updates with query")
    callback = query.data
    if callback is None:
        raise ValueError

    callback_arguments = callback.split("+")
    callback_arg_2 = callback_arguments[3]

    time = arrow.get(callback_arg_2)

    frontend.shared.src.db.TimeSlotsCollection().insert_one(
        {
            "time": time.datetime,
            "occupation_reason": "scheduled call",
            "chat_id": int(chat_id),
        }
    )

    for admin in admins:
        await context.bot.send_message(
            admin["chat_id"],
            f"Пользователь {user['first_name']} {chat_id} @{user['username']} "
            f"хочет договориться о консультации в "
            f"{time.shift(hours=3).format('YYYY-MM-DD HH:mm')} по Москве",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Подтвердить",
                            callback_data=f"y+book+admin+{admin['chat_id']}+{callback_arg_2}",
                        ),
                        InlineKeyboardButton(
                            "Я не могу в это время",
                            callback_data=f"d+book+admin+{admin['chat_id']}+{callback_arg_2}",
                        ),
                    ]
                ]
            ),
        )
