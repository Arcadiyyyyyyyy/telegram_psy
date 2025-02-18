import datetime
from typing import Any

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import frontend.shared.src.config
import frontend.shared.src.db
import frontend.shared.src.errors
import frontend.shared.src.middleware
import frontend.shared.src.utils
import frontend.telegram_bot.src.app.commands.help
import frontend.telegram_bot.src.app.commands.start
import frontend.telegram_bot.src.app.commands.test_atq
import frontend.telegram_bot.src.app.commands.test_iq
import frontend.telegram_bot.src.app.utils

conversation_handlers = (
    frontend.shared.src.config.ConversationHandlerConfig(
        (
            x
            := frontend.telegram_bot.src.app.commands.test_atq.Conversation().conversation_name  # noqa
        ),
        "Take ATQ test",
        (
            CommandHandler(
                x,
                frontend.telegram_bot.src.app.commands.test_atq.Conversation().command,  # noqa
            ),
        ),
        {
            k: (
                CallbackQueryHandler(
                    frontend.telegram_bot.src.app.commands.test_atq.Conversation().callback_handler,  # noqa
                    pattern=rf"a\+{frontend.telegram_bot.src.app.commands.test_atq.Conversation().conversation_name}\+[a-zA-Z0-9+]+",  # noqa
                ),
            )
            for k, v in frontend.telegram_bot.src.app.commands.test_atq.Conversation().commands  # noqa
        },
        [
            CommandHandler(
                "cancel",
                frontend.telegram_bot.src.app.commands.test_atq.Conversation().cancel,
            ),
            CallbackQueryHandler(
                frontend.telegram_bot.src.app.commands.test_atq.Conversation().callback_cancel,  # noqa
            ),
            MessageHandler(
                filters.TEXT & filters.COMMAND,
                frontend.telegram_bot.src.app.commands.test_atq.Conversation().cancel,
            ),
        ],
        2,
    ),
    frontend.shared.src.config.ConversationHandlerConfig(
        (
            x
            := frontend.telegram_bot.src.app.commands.test_iq.Conversation().conversation_name  # noqa
        ),
        "Take IQ test",
        (
            CommandHandler(
                x,
                frontend.telegram_bot.src.app.commands.test_iq.Conversation().command,  # noqa
            ),
        ),
        {
            k: (
                CallbackQueryHandler(
                    frontend.telegram_bot.src.app.commands.test_iq.Conversation().callback_handler,  # noqa
                    pattern=rf"a\+{frontend.telegram_bot.src.app.commands.test_iq.Conversation().conversation_name}\+[a-zA-Z0-9+]+",  # noqa
                ),
            )
            for k, v in frontend.telegram_bot.src.app.commands.test_iq.Conversation().commands  # noqa
        },
        [
            CommandHandler(
                "cancel",
                frontend.telegram_bot.src.app.commands.test_iq.Conversation().cancel,
            ),
            CallbackQueryHandler(
                frontend.telegram_bot.src.app.commands.test_iq.Conversation().callback_cancel,  # noqa
            ),
            MessageHandler(
                filters.TEXT & filters.COMMAND,
                frontend.telegram_bot.src.app.commands.test_iq.Conversation().cancel,
            ),
        ],
        3,
    ),
)

commands = (
    frontend.shared.src.config.Command(
        "start", "Start the bot", frontend.telegram_bot.src.app.commands.start.command
    ),
    frontend.shared.src.config.Command(
        "help", "Get help", frontend.telegram_bot.src.app.commands.help.command
    ),
    frontend.shared.src.config.Command("cancel", "Cancel the current test", None),
)


async def set_up_commands(
    bot: Application[
        Any,
        Any,
        dict[Any, Any],
        dict[Any, Any],
        dict[Any, Any],
        Any,
    ],
):
    await bot.bot.set_my_commands(
        [(x.command, x.description) for x in commands + conversation_handlers]
    )


def bot_setup(
    bot: Application[
        Any,
        Any,
        dict[Any, Any],
        dict[Any, Any],
        dict[Any, Any],
        Any,
    ],
):
    for conversation_handler in conversation_handlers:
        bot.add_handler(
            ConversationHandler(
                conversation_handler.entrypoint,  # type: ignore
                conversation_handler.stages,  # type: ignore
                conversation_handler.fallback,  # type: ignore
                name=conversation_handler.command,
                persistent=True,
            ),
            group=conversation_handler.group,
        )

    for command in commands:
        if command.callback is None:
            continue
        bot.add_handler(
            CommandHandler(
                command.command,
                command.callback,
            )
        )

    bot.add_handler(
        CallbackQueryHandler(frontend.shared.src.middleware.callback_distributor)
    )
    bot.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            frontend.shared.src.middleware.test_message_handler,
        )
    )
    bot.add_error_handler(frontend.shared.src.errors.error_handler)

    if not bot.job_queue:
        raise EnvironmentError("Job queue must be installed")

    bot.job_queue.run_daily(
        frontend.shared.src.utils.backup_db,
        datetime.datetime(2020, 1, 1, 0, 0, 0).time(),
    )
