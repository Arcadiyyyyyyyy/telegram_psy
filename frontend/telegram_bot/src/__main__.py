import os
import warnings

from loguru import logger
from telegram import Update
from telegram.ext import Application, PicklePersistence
from telegram.warnings import PTBUserWarning

import frontend.shared.src.config
import frontend.shared.src.db
import frontend.telegram_bot.src.app.config


def main():
    warnings.filterwarnings("ignore", category=PTBUserWarning)
    logger.add(
        "logs/telegram_bot.log",
        level=5,
        colorize=False,
        backtrace=True,
        diagnose=True,
    )
    frontend.shared.src.db.TestsCollection().populate_tests_from_json()
    persistence = PicklePersistence(filepath="persistance/telegram_bot_persistance.pc")
    bot = (
        Application.builder()  # type: ignore
        .token(os.environ["USER_FACING_TELEGRAM_TOKEN"])
        .persistence(persistence)
        .post_init(frontend.telegram_bot.src.app.config.set_up_commands)
        .build()
    )
    frontend.telegram_bot.src.app.config.bot_setup(bot)

    logger.info("Started")
    bot.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
