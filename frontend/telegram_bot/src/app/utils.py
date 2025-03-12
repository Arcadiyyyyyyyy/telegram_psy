from typing import Any, Literal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import frontend.shared.src.db
import frontend.shared.src.models


def generate_question_answer_keyboard(
    test_name: Literal["atq", "iq", "continue"], test_step: int, test_phase: int = 0
):
    if test_name == "atq":
        result = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"{answer}",
                        callback_data=f"a+{test_name}+step{test_step}+answer{answer}",
                    )
                ]
                for answer in [
                    "Совершенно неверно",
                    "Неверно",
                    "Скорее неверно",
                    "Трудно сказать",
                    "Скорее верно",
                    "Верно",
                    "Совершенно верно",
                ]
            ]
        )
    elif test_name == "iq":
        answers = [
            "a",
            "b",
            "c",
            "d",
            "e",
        ]
        if test_phase == 1 or test_phase == 3:
            answers.append("f")
        result = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"{answer}",
                        callback_data=f"a+{test_name}+step{test_step}+answer{answer}",
                    )
                    for answer in answers
                ]
            ]
        )
    elif test_name == "continue":
        result = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"{answer}",
                        callback_data=f"a+iq+step{test_step}+answer{answer}",
                    )
                ]
                for answer in ["Ready"]
            ]
        )
    else:
        result = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"{answer}",
                        callback_data=f"a+{test_name}+step{test_step}+answer{answer}",
                    )
                ]
                for answer in [
                    "No keyboard for you",
                ]
            ]
        )

    return result


async def abort_test(
    update: Update, context: ContextTypes.DEFAULT_TYPE, test_name: str
) -> int:
    if update.effective_chat is None:
        raise ValueError(
            "abort_test function must only be provided "
            + "with updates that have effective chat"
        )
    chat_id = update.effective_chat.id

    tests_collection = frontend.shared.src.db.TestAnswersCollection()
    tests_collection.delete({"chat_id": chat_id, "test_name": test_name})

    await context.bot.send_message(
        chat_id,
        "Тест закончен преждевременно.\n\n"
        "Чтобы сделать тест ещё раз - пожалуйста, обратитесь в поддержку.",
    )

    return ConversationHandler.END


def save_test_answers(chat_id: int, conversation_name: str, user_data: dict[str, Any]):
    answers: list[str] = user_data["answers"]
    questions: list[str] = user_data["questions"]

    test_answers_collection = frontend.shared.src.db.TestAnswersCollection()
    new_test_answer: dict[str, Any] = {
        "chat_id": chat_id,
        "test_name": conversation_name,
        "answers": answers,
        "questions": questions,
        "started_at": user_data["started_at"],
        "finished_at": user_data["finished_at"],
    }
    filter_to_check_existing_answer: dict[str, Any] = {
        "chat_id": chat_id,
        "test_name": conversation_name,
    }

    if test_answers_collection.read_one(filter_to_check_existing_answer) is not None:
        test_answers_collection.update(filter_to_check_existing_answer, new_test_answer)
    else:
        test_answers_collection.create_test_answer(
            frontend.shared.src.models.TestAnswerModel(**new_test_answer)
        )


async def notify_test_exit_consequence(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_chat is None:
        raise ValueError
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id,
        "Имейте в виду, что нажатие любой команды отличной "
        "от ответа на вопрос во время прохождения теста повлечёт за "
        "собой незамедлительное окончание теста. "
        "Пересдать тест в таком случае невозможно.",
    )
