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
            answers += ["f"]
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
                        # TODO: i really didn't want to do this, but fuck this
                        # quality of code when deadlines in the ass
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
        "Тест закончен преждевременно, результаты удалены.\n\n"
        "Чтобы сделать тест ещё раз - пожалуйста, используйте команду теста повторно.",
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


def handle_test_answer(
    *,
    question_texts: list[str],
    context: ContextTypes.DEFAULT_TYPE,
    callback: str,
) -> int:
    """Returns next command id"""
    if context.user_data is None:
        raise ValueError

    split = callback.split("+")
    current_step = int(split[2][4:])
    answer_text = split[3][6:]

    previous_question_text = question_texts[current_step - 1]
    answers: list[Any] | None = context.user_data.get("answers")
    questions: list[Any] | None = context.user_data.get("questions")
    if answers is None:
        context.user_data["answers"] = []
    del answers
    valid_answers: list[str] = context.user_data["answers"]
    valid_answers.append(answer_text)
    if questions is None:
        context.user_data["questions"] = []
    del questions
    valid_questions: list[str] = context.user_data["questions"]
    valid_questions.append(previous_question_text)

    next_question_step = current_step

    return next_question_step
