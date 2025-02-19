import os
import warnings

from loguru import logger
from telegram import Update
from telegram.ext import Application, PicklePersistence
from telegram.warnings import PTBUserWarning

import frontend.admin_bot.src.app.config
import frontend.shared.src.db


def main():
    warnings.filterwarnings("ignore", category=PTBUserWarning)
    logger.add(
        "logs/admin_bot.log",
        level=5,
        colorize=False,
        backtrace=True,
        diagnose=True,
    )
    persistence = PicklePersistence(filepath="persistance/admin_bot_persistance.pc")
    bot = (
        Application.builder()  # type: ignore
        .token(os.environ["ADMIN_FACING_TELEGRAM_TOKEN"])
        .persistence(persistence)
        .post_init(frontend.admin_bot.src.app.config.set_up_commands)
        .build()
    )
    frontend.admin_bot.src.app.config.bot_setup(bot)

    logger.info("Started")
    bot.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
