import datetime
from typing import Any, Literal

from loguru import logger
from telegram import CallbackQuery

import frontend.shared.src.db


async def backup_db(*args: Any, **kwargs: Any) -> None:
    frontend.shared.src.db.backup(
        frontend.shared.src.db.UsersCollection(),
        frontend.shared.src.db.TestsCollection(),
        frontend.shared.src.db.TestAnswersCollection(),
    )


def generate_test_answers_info(
    chat_id: int, conversation_name: str
):
    answer = frontend.shared.src.db.TestAnswersCollection().read_one(
        {"chat_id": chat_id, "test_name": conversation_name},
    )
    if answer is None:
        raise ValueError

    question_answer: list[str] = []

    if conversation_name == "atq":
        for question, _answer in zip(answer["questions"], answer["answers"]):
            question_answer.append(f"{question}: {_answer}")
        test_of_question_answer = "- " + "\n- ".join(question_answer)
    elif conversation_name == "iq":
        answers = answer.get("answers", [])
        for i, question in enumerate(answer.get("questions", [])):
            _answer = answers[i]

            if question != "" and _answer == "Ready":
                pass
            else:
                question_answer.append(f"- {i + 1}: {_answer}")
        test_of_question_answer = "\n".join(question_answer)
    else:
        test_of_question_answer = "Error"

    started_at: datetime.datetime = answer["started_at"]
    finished_at: datetime.datetime = answer["finished_at"]

    test_summary = (
        "Количество секунд потраченных на прохождение теста: "
        f"{(finished_at - started_at).seconds}.\n\n"
        "Вот как вы ответили на вопросы из теста:\n"
        f"{test_of_question_answer}"
    )

    return test_summary


async def handle_callback(query: CallbackQuery | None) -> tuple[int, str]:
    """Returns chat id and query data"""
    if query is None:
        raise ValueError

    chat_id = query.from_user.id
    callback = query.data
    logger.trace(f"Got {callback} callback from user {chat_id}")
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    if data is None:
        data = ""

    return (query.from_user.id, data)


def split_string(s: str, chunk_size: int = 4000):
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]
