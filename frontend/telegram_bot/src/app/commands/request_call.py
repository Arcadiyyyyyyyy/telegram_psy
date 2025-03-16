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
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    await frontend.shared.src.middleware.main_handler(update, context)

    await context.bot.send_message(
        chat_id,
        "Привет! \n\nТут можно выбрать время для консультации с нашими специалистами",
        reply_markup=frontend.admin_bot.src.app.commands.manage_time_slots.generate_available_time_slots_keyboard(  # noqa
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

    await context.bot.send_message(
        chat_id, "Запрос на получение консультации получен, уведомим по подтверждению."
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


async def show_scheduled_calls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id
    users = frontend.shared.src.db.UsersCollection()
    time_slots = frontend.shared.src.db.TimeSlotsCollection()
    scheduled_calls = list(
        time_slots.read(
            {
                "time": {"$gte": arrow.utcnow().datetime},
                "meeting_link": {"$exists": 1},
                "chat_id": chat_id,
            },
            {"time": 1},
        )
    )
    result: list[str] = ["Вот список ваших запланированных звонков: \n"]
    for call in scheduled_calls:
        user = users.read_one({"chat_id": call["chat_id"]})
        if not user:
            raise ValueError
        result.append(
            f"Запланированная консультация {arrow.get(call.get('time')).shift(hours=3).format('YYYY-MM-DD HH:mm')}"
        )
    if len(result) == 1:
        result.append("У вас ещё нет подтверждённых звонков")

    await context.bot.send_message(chat_id, "\n".join(result))


async def cancel_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    callback_arg_3 = callback_arguments[4]

    time = arrow.get(callback_arg_3)
    time_slots = frontend.shared.src.db.TimeSlotsCollection()

    get_time_slot = time_slots.read_one(
        {
            "time": time.datetime,
            "occupation_reason": "scheduled call",
        }
    )

    if get_time_slot is None:
        raise ValueError

    time_slots.delete(
        {
            "time": time.datetime,
            "occupation_reason": "scheduled call",
        }
    )

    for _chat_id in admins + [get_time_slot]:
        text = f"Консультация на {time.shift(hours=3).format('YYYY-MM-DD HH:mm')} по Московскому времени отменена."
        await context.bot.send_message(
            _chat_id["chat_id"],
            text,
        )
