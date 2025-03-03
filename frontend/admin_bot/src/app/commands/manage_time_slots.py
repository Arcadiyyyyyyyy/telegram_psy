import arrow
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.admin_bot.src.app.middleware
import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.utils


def generate_available_time_slots_keyboard(
    start_date: arrow.Arrow, end_date: arrow.Arrow
):
    time_manager = frontend.shared.src.utils.TimeManager()
    available_slots = sorted(
        list(time_manager.generate_free_time_slots(start_date, end_date))
    )

    if not available_slots:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "К сожалению, в выбранном периоде нету свободных слотов. Назад.",  # noqa
                        callback_data="",
                    )
                ]
            ]
        )  # TODO: callback data

    active_day = available_slots[0].clone()
    active_day.replace(hour=0, minute=0, second=0, microsecond=0)
    slots_by_days: list[list[arrow.Arrow]] = [[]]

    while active_day < available_slots[-1]:
        result: list[arrow.Arrow] = []
        for slot in available_slots:
            if slot > active_day and slot < active_day.shift(days=1):
                result.append(slot)
        slots_by_days.append(result)

    # TODO: callback + text format 
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("", callback_data="") for button in slots_by_days]]
    )


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    user_data = [
        (
            f"{user['first_name']} | {user['username']} | {user['chat_id']}",
            user["chat_id"],
        )
        for user in frontend.shared.src.db.UsersCollection().read({}, {"created_at": 1})
    ]

    await context.bot.send_message(
        chat_id,
        "Тут можно получить информацию о прохождении теста конкретным пользователем \n\nСписок пользователей бота:",  # noqa
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text[0], callback_data=f"s+ans_by_u+{text[1]}")]
                for text in user_data
            ]
        ),
    )
