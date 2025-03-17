import traceback

from loguru import logger
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import frontend.shared.src.utils


class GeneralError(Exception):
    pass


class AccessDeclined(Exception):
    pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""

    tb_list = traceback.format_exception(
        None,
        context.error,
        context.error.__traceback__,  # type: ignore
    )
    tb_string = "".join(tb_list)

    logger.error(
        f"Exception while handling an update: {tb_string}", exc_info=context.error
    )

    message = (
        "Ошибка ошибка ошибочка ошибка ошибка ошибка ошибочка ошибка\nРАСШИБКА!!!!!\n\n\n"
        f"context.chat_data = {str(context.chat_data)}\n\n"
        f"context.user_data = {str(context.user_data)}\n\n"
        "\n\n"
        f"{tb_string}"
    )

    await context.bot.send_message(
        chat_id=431691892,
        text=frontend.shared.src.utils.telegram_escape_markdown(message[-4000:]),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
