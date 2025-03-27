from typing import Any

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

import frontend.admin_bot.src.app.commands.get_all_atq_answers
import frontend.admin_bot.src.app.commands.get_all_iq_answers
import frontend.admin_bot.src.app.commands.get_answers_by_user
import frontend.admin_bot.src.app.commands.get_interpretation_requests
import frontend.admin_bot.src.app.commands.list_confirmed_consultations
import frontend.admin_bot.src.app.commands.manage_time_slots
import frontend.admin_bot.src.app.commands.start
import frontend.shared.src.config
import frontend.shared.src.middleware
import frontend.shared.src.utils

commands = (
    frontend.shared.src.config.Command(
        "start", "Start the bot", frontend.admin_bot.src.app.commands.start.command
    ),
    frontend.shared.src.config.Command(
        "get_answers_by_user",
        "Get user's answer to the test",
        frontend.admin_bot.src.app.commands.get_answers_by_user.command,
    ),
    frontend.shared.src.config.Command(
        "get_scheduled_calls",
        "Get the list of planned calls",
        frontend.admin_bot.src.app.commands.list_confirmed_consultations.command,
    ),
    frontend.shared.src.config.Command(
        "manage_time_slots",
        "Remove time slots from the availability",
        frontend.admin_bot.src.app.commands.manage_time_slots.command,
    ),
    frontend.shared.src.config.Command(
        "get_all_atq_answers",
        "Get csv of user atq answers",
        frontend.admin_bot.src.app.commands.get_all_atq_answers.command,
    ),
    frontend.shared.src.config.Command(
        "get_all_iq_answers",
        "Get csv of user iq answers",
        frontend.admin_bot.src.app.commands.get_all_iq_answers.command,
    ),
    frontend.shared.src.config.Command(
        "get_interpretation_requests",
        "Get user requests for test results",
        frontend.admin_bot.src.app.commands.get_interpretation_requests.command,
    ),
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
    await bot.bot.set_my_commands([(x.command, x.description) for x in commands])


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
