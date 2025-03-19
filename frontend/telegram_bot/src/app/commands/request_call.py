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
import frontend.shared.src.utils


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if update.effective_chat is None or context.user_data is None:
        return
    chat_id = update.effective_chat.id
    await frontend.shared.src.middleware.main_handler(update, context)
    await frontend.shared.src.utils.remove_all_messages(
        update.effective_chat.id, context
    )

    message = await context.bot.send_message(
        chat_id,
        "Привет! \n\nТут можно выбрать время для консультации с нашими специалистами",
        reply_markup=frontend.admin_bot.src.app.commands.manage_time_slots.generate_available_time_slots_keyboard(  # noqa
            "user", page=page
        ),
    )
    if context.user_data.get("explainer_message_ids") is not None:
        context.user_data["explainer_message_ids"].append(message.id)
    else:
        context.user_data["explainer_message_ids"] = [message.id]


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

    time = arrow.get(callback_arg_2, "DD/MM/YYYY HH:mm")

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
            f"{time.shift(hours=3).format('DD/MM/YYYY HH:mm')} по Москве",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Подтвердить",
                            callback_data=f"y+book+admin+{admin['chat_id']}+{callback_arg_2}",
                        ),
                        InlineKeyboardButton(
                            "Мне неудобно",
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
    result: list[str] = ["Вот список твоих подтвержденных интервью: \n"]
    for call in scheduled_calls:
        user = users.read_one({"chat_id": call["chat_id"]})
        if not user:
            raise ValueError
        result.append(
            f"Запланированная консультация {arrow.get(call.get('time')).shift(hours=3).format('DD/MM/YYYY HH:mm')}"
        )
    if len(result) == 1:
        result.append("У вас ещё нет подтверждённых звонков")

    message = await context.bot.send_message(chat_id, "\n".join(result))
    if context.user_data is not None:
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(message.id)
        else:
            context.user_data["explainer_message_ids"] = [message.id]


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

    time = arrow.get(callback_arg_3, "DD/MM/YYYY HH:mm")
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
        text = f"Консультация на {time.shift(hours=3).format('DD/MM/YYYY HH:mm')} по Московскому времени отменена."
        await context.bot.send_message(
            _chat_id["chat_id"],
            text,
        )
