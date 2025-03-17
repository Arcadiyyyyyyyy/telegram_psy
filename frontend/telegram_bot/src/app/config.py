import datetime
from typing import Any, Optional

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
import frontend.telegram_bot.src.app.commands.menu
import frontend.telegram_bot.src.app.commands.request_call
import frontend.telegram_bot.src.app.commands.start
import frontend.telegram_bot.src.app.commands.test_atq
import frontend.telegram_bot.src.app.commands.test_iq
import frontend.telegram_bot.src.app.utils


class Commands:
    _instance: Optional["Commands"] = None
    __initialized: bool

    conversation_handlers: Any
    commands: Any

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Commands, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        if self.__initialized:
            return
        self.__initialized = True

        self.conversation_handlers = (
            frontend.shared.src.config.ConversationHandlerConfig(
                (
                    x
                    := frontend.telegram_bot.src.app.commands.test_atq.Conversation().conversation_name  # noqa
                ),
                "Пройти ATQ тест",
                (
                    CommandHandler(
                        x,
                        frontend.telegram_bot.src.app.commands.test_atq.Conversation().command,  # noqa
                    ),
                    CallbackQueryHandler(
                        frontend.telegram_bot.src.app.commands.test_atq.Conversation().command,  # noqa
                        pattern=rf"r\+{frontend.telegram_bot.src.app.commands.test_atq.Conversation().conversation_name}start",  # noqa
                    ),
                ),
                {
                    k: (
                        CallbackQueryHandler(
                            frontend.telegram_bot.src.app.commands.test_atq.Conversation().callback_handler,  # noqa
                            pattern=rf"a\+{frontend.telegram_bot.src.app.commands.test_atq.Conversation().conversation_name}\+[a-zA-Z0-9+]+",  # noqa
                        ),
                    )
                    for k, v in frontend.telegram_bot.src.app.commands.test_atq.Conversation().commands  # noqa  # type: ignore
                },
                [
                    CommandHandler(
                        "cancel",
                        frontend.telegram_bot.src.app.commands.test_atq.Conversation().cancel,  # noqa
                    ),
                    CallbackQueryHandler(
                        frontend.telegram_bot.src.app.commands.test_atq.Conversation().callback_cancel,  # noqa
                    ),
                    MessageHandler(
                        filters.TEXT & filters.COMMAND,
                        frontend.telegram_bot.src.app.commands.test_atq.Conversation().cancel,  # noqa
                    ),
                ],
                2,
            ),
            frontend.shared.src.config.ConversationHandlerConfig(
                (
                    x
                    := frontend.telegram_bot.src.app.commands.test_iq.Conversation().conversation_name  # noqa
                ),
                "Пройти IQ тест",
                (
                    CommandHandler(
                        x,
                        frontend.telegram_bot.src.app.commands.test_iq.Conversation().command,  # noqa
                    ),
                    CallbackQueryHandler(
                        frontend.telegram_bot.src.app.commands.test_iq.Conversation().command,  # noqa
                        pattern=rf"r\+{frontend.telegram_bot.src.app.commands.test_iq.Conversation().conversation_name}start",  # noqa
                    ),
                ),
                {
                    k: (
                        CallbackQueryHandler(
                            frontend.telegram_bot.src.app.commands.test_iq.Conversation().callback_handler,  # noqa
                            pattern=rf"a\+{frontend.telegram_bot.src.app.commands.test_iq.Conversation().conversation_name}\+[a-zA-Z0-9+]+",  # noqa
                        ),
                    )
                    for k, v in frontend.telegram_bot.src.app.commands.test_iq.Conversation().commands  # noqa  # type: ignore
                },
                [
                    CommandHandler(
                        "cancel",
                        frontend.telegram_bot.src.app.commands.test_iq.Conversation().cancel,  # noqa
                    ),
                    CallbackQueryHandler(
                        frontend.telegram_bot.src.app.commands.test_iq.Conversation().callback_cancel,  # noqa
                    ),
                    MessageHandler(
                        filters.TEXT & filters.COMMAND,
                        frontend.telegram_bot.src.app.commands.test_iq.Conversation().cancel,  # noqa
                    ),
                ],
                3,
            ),
        )

        self.commands = (
            frontend.shared.src.config.Command(
                "menu",
                "Главное меню",
                frontend.telegram_bot.src.app.commands.menu.command,
            ),
            frontend.shared.src.config.Command(
                "help",
                "Помощь",
                frontend.telegram_bot.src.app.commands.help.command,
            ),
            frontend.shared.src.config.Command(
                "book_a_call",
                "Назначить звонок со специалистами",
                frontend.telegram_bot.src.app.commands.request_call.command,
            ),
            frontend.shared.src.config.Command(
                "list_confirmed_calls",
                "Список подтверждённых запланированных звонков",
                frontend.telegram_bot.src.app.commands.request_call.show_scheduled_calls,  # noqa
            ),
            frontend.shared.src.config.Command(
                "start",
                "Начать использование бота",
                frontend.telegram_bot.src.app.commands.start.command,
            ),
            frontend.shared.src.config.Command("cancel", "Закончить текущий тест", None),
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
        [
            (x.command, x.description)
            for x in Commands().conversation_handlers + Commands().commands
        ]
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
    for conversation_handler in Commands().conversation_handlers:
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

    for command in Commands().commands:
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
        datetime.time(0, 0, 0),
    )
