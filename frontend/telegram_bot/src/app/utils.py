from typing import Any, Literal

import arrow
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


async def abort_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat is None or context.user_data is None:
        raise ValueError
    chat_id = update.effective_chat.id

    messages_to_delete: list[int] = []
    if (x := context.user_data.get("explainer_message_ids")) is not None:
        messages_to_delete.extend(x)
    context.user_data["explainer_message_ids"] = []
    if (x := context.user_data.get("last_sent_test_message_id")) is not None:
        messages_to_delete.append(x)
    context.user_data["last_sent_test_message_id"] = None

    for message_id in messages_to_delete:
        try:
            await context.bot.delete_message(chat_id, message_id)
        except Exception:
            pass

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
        "finished_at": user_data.get("finished_at", arrow.utcnow().datetime),
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
    if update.effective_chat is None or context.user_data is None:
        raise ValueError
    chat_id = update.effective_chat.id
    explainer_message = await context.bot.send_message(
        chat_id,
        "Имей в виду, что нажатие любой команды отличной "
        "от ответа на вопрос во время прохождения теста повлечёт за "
        "собой незамедлительное окончание теста. "
        "Пересдать тест в таком случае невозможно.",
    )
    context.user_data["explainer_message_ids"].append(explainer_message.id)
