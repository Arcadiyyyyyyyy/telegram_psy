import asyncio
import os
import warnings
from pathlib import Path

from loguru import logger
from telegram.ext import Application
from telegram.warnings import PTBUserWarning

import frontend.shared.src.db

CHAT_ID_TO_IQ_RESULTS: dict[int, int] = {
    1028891218: 96,
    311571339: 85,
    344823972: 100,
    711116046: 0,
    462134280: 111,
    210518040: 111,
    469952619: 117,
    256183711: 121,
    1485288148: 103,
    5238704259: 0,
    557000896: 85,
    119843940: 106,
    872426137: 100,
    373495794: 78,
    476718339: 111,
    549076465: 124,
    396517337: 100,
    758305628: 100,
    130940575: 106,
    382027611: 103,
    450964832: 111,
    444127938: 88,
    431691892: 0,
    457195618: 100,
    354150147: 106,
    193991845: 140,
    416698789: 113,
}


async def main():
    warnings.filterwarnings("ignore", category=PTBUserWarning)
    bot = (
        Application.builder()  # type: ignore
        .token(os.environ["USER_FACING_TELEGRAM_TOKEN"])
        .build()
    )

    logger.info("Started")

    users = frontend.shared.src.db.UsersCollection()

    for i in range(30):
        try:
            await bot.bot.delete_message()

    send_извинения = True
    for user_id in {
        444127938,
        520794627,
        476718339,
        354150147,
        5238704259,
        462134280,
        311571339,
        711116046,
        1028891218,
        1485288148,
        210518040,
        396517337,
        382027611,
        758305628,
        256183711,
        130940575,
        450964832,
        457195618,
        344823972,
        416698789,
        119843940,
        469952619,
        476798383,
        373495794,
        431691892,
    }:
        user = users.read_one({"chat_id": user_id})

        if user is None:
            raise ValueError

        iq_results = CHAT_ID_TO_IQ_RESULTS.get(
            user_id,
        )
        atq_results: bytes | None = None

        atq_results_path = f"input/ATQ_report_{user['random_id']}.docx"

        if Path(atq_results_path).exists():
            with Path(atq_results_path).open("rb") as file:
                atq_results = file.read()

        results = ""
        if iq_results is None and atq_results is None:
            continue
        results += (
            "Спасибо за участие в нашем исследовании!\n\n"
        )
        if atq_results is not None:
            results += "Результаты ATQ теста доступны в прикреплённом файле.\n\n"
        if iq_results is not None:
            results += f"По результатам IQ теста, ты набрал {iq_results} баллов.\n\n"
        results += "Когда все ключевые этапы исследования будут завершены, поступит отдельное уведомление."


        try:
            if atq_results:
                await bot.bot.send_document(
                    chat_id=user_id,
                    document=atq_results_path,
                    caption=results,
                )
            else:
                await bot.bot.send_message(chat_id=user_id, text=results)
        except Exception:
            print(f"Error sending to {user_id}")
            send_извинения = False


if __name__ == "__main__":
    asyncio.run(main())
