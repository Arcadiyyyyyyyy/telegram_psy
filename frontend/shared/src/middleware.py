from typing import Any
from unittest.mock import NonCallableMagicMock

import arrow
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

import frontend.admin_bot
import frontend.admin_bot.src
import frontend.admin_bot.src.app
import frontend.admin_bot.src.app.commands
import frontend.admin_bot.src.app.commands.get_answers_by_user
import frontend.admin_bot.src.app.commands.manage_time_slots
import frontend.shared.src.db
import frontend.shared.src.errors
import frontend.shared.src.models
import frontend.shared.src.utils
import frontend.shared.src.zoom_requester
import frontend.telegram_bot.src.app.commands
import frontend.telegram_bot.src.app.commands.request_call
import frontend.telegram_bot.src.app.commands.test_atq
import frontend.telegram_bot.src.app.commands.test_iq
import frontend.telegram_bot.src.app.utils


def is_chat_exists(
    update: Update, users_collection: frontend.shared.src.db.UsersCollection
) -> None:
    if update.effective_chat is None:
        raise ValueError(
            "is_chat_private function should not be called "
            "on updates with no effective chat"
        )

    chat = users_collection.read_one({"chat_id": update.effective_chat.id})

    if chat is not None:
        return

    if update.message is None or update.message.from_user is None:
        return

    users_collection.create_user(
        frontend.shared.src.models.UserModel(
            chat_id=update.message.from_user.id,
            first_name=update.message.from_user.first_name,
            last_name=update.message.from_user.last_name,
            username=update.message.from_user.username,
        )
    )


async def is_chat_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat is None:
        raise ValueError(
            "is_chat_private function should not be called "
            "on updates with no effective chat"
        )
    if update.effective_chat is not None and update.effective_chat.type == "private":
        return True
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="К сожалению, этим ботом можно пользоваться только в личных чатах",
        )
        return False


async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None and update.message.from_user is not None:
        logger.trace(
            f"Got message {update.message.text} from {update.message.from_user.id}"
        )
    users_collection = frontend.shared.src.db.UsersCollection()

    is_chat_exists(update, users_collection)
    if not await is_chat_private(update, context):
        raise frontend.shared.src.errors.AccessDeclined()
    if (update.message is not None and update.message.from_user is not None) and (
        update.effective_chat is not None
        and update.effective_chat.id == update.message.from_user.id
    ):
        users_collection.update_user(
            frontend.shared.src.models.UserModel(
                chat_id=update.message.from_user.id,
                first_name=update.message.from_user.first_name,
                last_name=update.message.from_user.last_name,
                username=update.message.from_user.username,
            )
        )


async def callback_distributor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None or update.effective_message is None:
        raise ValueError
    chat_id = update.effective_chat.id

    query = update.callback_query
    if query is None:
        raise ValueError("Callback distributor must only receive updates with query")
    callback = query.data
    if callback is None:
        raise ValueError

    callback_arguments = callback.split("+")
    callback_group = callback_arguments[0]
    callback_file = callback_arguments[1]
    callback_len = len(callback_arguments)
    callback_arg_1: str | None = None
    callback_arg_2: str | None = None
    callback_arg_3: str | None = None
    if callback_len > 3:
        callback_arg_1 = callback_arguments[2]
    if callback_len > 4:
        callback_arg_2 = callback_arguments[3]
    if callback_len > 5:
        callback_arg_3 = callback_arguments[4]

    if callback_group == "s":
        if callback_file == "ansvs":
            await frontend.admin_bot.src.app.commands.get_answers_by_user.command(
                update, context
            )
        elif callback_file == "ans_by_u":
            await (
                frontend.admin_bot.src.app.commands.get_answers_by_user.select_the_test(
                    update, context
                )
            )
        elif callback_file == "ans_by_uid_and_test":
            await frontend.admin_bot.src.app.commands.get_answers_by_user.show_the_test(
                update, context
            )
        elif (
            callback_file == "book"
            and callback_arg_1 == "admin"
            and callback_arg_2 is not None
        ):
            date = arrow.get(callback_arg_2)
            occupation_reason = f"Blocked by telegram id {chat_id}"
            page = callback_arg_3

            try:
                await context.bot.delete_message(chat_id, update.effective_message.id)
            except Exception:
                pass

            frontend.shared.src.db.TimeSlotsCollection().insert_one(
                {
                    "time": date,
                    "occupation_reason": occupation_reason,
                    "chat_id": chat_id,
                }
            )

            await frontend.admin_bot.src.app.commands.manage_time_slots.command(
                update, context, page=int(page) if page is not None else 0
            )
        elif callback_file == "book" and callback_arg_1 == "admin":
            await frontend.admin_bot.src.app.commands.manage_time_slots.command(
                update, context
            )
        elif callback_file == "book":
            # TODO: call user side
            pass
        elif (
            callback_file == "book"
            and callback_arg_1 in ["user", "admin"]
            and callback_arg_2 == "None"
            and callback_arg_3 is not None
        ):
            page = callback_arg_3
            try:
                await context.bot.delete_message(chat_id, update.effective_message.id)
            except Exception:
                pass
            if callback_arg_1 == "user":
                await frontend.telegram_bot.src.app.commands.request_call.command(
                    update, context, page=int(page)
                )
            elif callback_arg_1 == "admin":
                await frontend.admin_bot.src.app.commands.manage_time_slots.command(
                    update, context, page=int(page)
                )
        elif (
            callback_file == "book"
            and callback_arg_1 == "user"
            and callback_arg_2 is not None
        ):
            date = arrow.get(callback_arg_2)

            # TODO: request call
            await frontend.telegram_bot.src.app.commands.request_call.request_call(
                update, context
            )
    elif (
        callback_group == "y"
        and callback_arg_1 == "admin"
        and callback_arg_2 is not None
        and callback_arg_3 is not None
    ):
        if callback_file == "book":
            date = arrow.get(callback_arg_3)
            confirming_admin_id = int(callback_arg_2)
            time_slots = frontend.shared.src.db.TimeSlotsCollection()

            event = time_slots.read_one({"time": date})
            if event is None:
                raise ValueError

            # TODO: add read ids
            admin_who_confirmed = {1: "gleb", 2: "kopatych", 3: "elena"}.get(
                confirming_admin_id, "unknown"
            )
            time_slots.update(
                {"time": date}, {"confirmations": {f"by_{admin_who_confirmed}": True}}
            )
            updated = time_slots.read_one({"time": date})
            if updated is None:
                raise ValueError
            confirmations: dict[str, Any] = updated.get("confirmations", {})
            users_collection = frontend.shared.src.db.UsersCollection()
            if len(confirmations) == 3:
                meeting_link = frontend.shared.src.zoom_requester.ZOOM().create_meeting(
                    "Trader consultation", "", 45, date
                )
                notify_user_at = [
                    date.shift(days=-1).datetime,
                    date.shift(hours=-1).datetime,
                ]

                time_slots.update(
                    {"time": date},
                    {"meeting_link": meeting_link, "notify_user_at": notify_user_at},
                )

                for _chat_id in list(users_collection.read({"admin": True})) + [
                    updated["chat_id"]
                ]:
                    await context.bot.send_message(
                        _chat_id,
                        f"Консультация на {date.shift(hours=3).format('YYYY-MM-DD HH:mm')} по Московскому времени подтверждена. \n\nСсылка на встречу: {meeting_link}",
                    )

    elif callback_group == "d":
        if callback_file == "ans_by_uid_and_test" and callback_arguments[-1] == "y":
            await frontend.admin_bot.src.app.commands.get_answers_by_user.delete_test_answer(  # noqa
                update, context
            )
        elif callback_file == "ans_by_uid_and_test":
            await frontend.shared.src.utils.confirm_callback(  # noqa
                update, context
            )
        elif callback_file == "message":
            try:
                await context.bot.delete_message(chat_id, update.effective_message.id)
            except Exception:
                pass
        elif callback_file == "book":
            pass


async def test_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.message is None or update.message.from_user is None:
        return
    await main_handler(update, context)
    chat_id = update.message.chat.id

    await context.bot.send_message(
        chat_id,
        "К сожалению, я не понимаю текст. "
        "\n\nПожалуйста, воспользуйтесь командами, или кнопками.",
    )
