import html
import json
import traceback

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


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
    update_str = update.to_dict() if isinstance(update, Update) else str(update)

    message = (
        "Ошибка ошибка ошибочка ошибка ошибка ошибка ошибочка ошибка\nРАСШИБКА!!!!!\n\n\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    await context.bot.send_message(
        chat_id=431691892, text=message[-4000:], parse_mode=ParseMode.HTML
    )
