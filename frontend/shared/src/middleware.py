from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

import frontend.admin_bot
import frontend.admin_bot.src
import frontend.admin_bot.src.app
import frontend.admin_bot.src.app.commands
import frontend.admin_bot.src.app.commands.get_answers_by_user
import frontend.shared.src.db
import frontend.shared.src.errors
import frontend.shared.src.models
import frontend.shared.src.utils
import frontend.telegram_bot.src.app.commands
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
    users_collection = frontend.shared.src.db.UsersCollection()

    if update.message is not None and update.message.from_user is not None:
        logger.trace(
            f"Got message {update.message.text} from {update.message.from_user.id}"
        )

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
    # await main_handler(update, context)
    _, callback = await frontend.shared.src.utils.handle_callback(update.callback_query)
    if callback == "":
        return

    callback_arguments = callback.split("+")
    callback_group = callback_arguments[0]
    callback_file = callback_arguments[1]

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
