from typing import Literal

import arrow
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.admin_bot.src.app.middleware
import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.utils


def generate_available_time_slots_keyboard(
    _type: Literal["user", "admin"],
    page: int = 0,
):
    time_manager = frontend.shared.src.utils.TimeManager()
    start_date = arrow.utcnow().shift(days=6 * page)
    end_date = arrow.utcnow().shift(days=6 * page + 6)
    slots_by_days = list(time_manager.get_available_slots_by_days(start_date, end_date))

    inline_keyboard = [
        [
            InlineKeyboardButton(
                button.shift(hours=3).format("MM-DD HH:mm"),
                callback_data=f"s+book+{_type}+{button.format('YYYY-MM-DD HH:mm')}+{page}",
            )
            for button in line
        ]
        for line in slots_by_days
    ]
    controls: list[InlineKeyboardButton] = []
    if page > 0:
        controls.append(
            InlineKeyboardButton(
                "Предыдущая страница", callback_data=f"s+book+{_type}+none+{page - 1}"
            )
        )
    back_callback = "s+book"
    if _type == "admin":
        back_callback += "+admin"
    else:
        back_callback += "+user"
    controls.append(InlineKeyboardButton("Назад", callback_data=back_callback))
    controls.append(
        InlineKeyboardButton(
            "Следующая страница", callback_data=f"s+book+{_type}+none+{page + 1}"
        )
    )

    inline_keyboard.append(controls)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id,
        "Тут можно убрать доступный временной слот при помощи клика \n\nСписок слотов:",  # noqa
        reply_markup=generate_available_time_slots_keyboard("admin", page=page),
    )


# TODO: сделать тестовые вопросы в айку
