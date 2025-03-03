import datetime
from typing import Any

import arrow
from loguru import logger
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.db
import frontend.shared.src.file_manager
import frontend.shared.src.utils


async def backup_db(*args: Any, **kwargs: Any) -> None:
    frontend.shared.src.db.backup(
        frontend.shared.src.db.UsersCollection(),
        frontend.shared.src.db.TestsCollection(),
        frontend.shared.src.db.TestAnswersCollection(),
    )


def generate_test_answers_info(chat_id: int, conversation_name: str):
    """Returns summary text message, and bytes csv file"""
    answer = frontend.shared.src.db.TestAnswersCollection().read_one(
        {"chat_id": chat_id, "test_name": conversation_name},
    )
    if answer is None:
        raise ValueError

    to_dump_to_csv: list[list[str | int]] = []

    if conversation_name == "atq":
        for question, _answer in zip(answer["questions"], answer["answers"]):
            to_dump_to_csv.append([question, _answer])
    elif conversation_name == "iq":
        answers = answer.get("answers", [])
        for i, question in enumerate(answer.get("questions", [])):
            _answer = answers[i]

            if question != "" and _answer == "Ready":
                pass
            else:
                to_dump_to_csv.append([i + 1, _answer])

    started_at: datetime.datetime = answer["started_at"]
    finished_at: datetime.datetime = answer["finished_at"]

    test_summary = (
        "Количество секунд потраченных на прохождение теста: "
        f"{(finished_at - started_at).seconds}.\n\n"
    )

    file_manager = frontend.shared.src.file_manager.FileManager()

    file_manager.write_cache_test_answers(chat_id, conversation_name, to_dump_to_csv)

    return test_summary, file_manager.read_cache_test_answers(
        chat_id, conversation_name
    )


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
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]  # noqa


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None or update.callback_query is None:
        raise ValueError
    chat_id, callback = await frontend.shared.src.utils.handle_callback(
        update.callback_query
    )

    await context.bot.send_message(
        chat_id,
        "Уверен?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes",
                        callback_data=f"{callback}+y",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "No",
                        callback_data="d+message",
                    )
                ],
            ]
        ),
    )


class TimeManager:
    default_work_hours: list[datetime.time] = [
        datetime.time(10, 0, 0),
        datetime.time(11, 0, 0),
        datetime.time(12, 0, 0),
        datetime.time(13, 0, 0),
        datetime.time(14, 0, 0),
        datetime.time(15, 0, 0),
        datetime.time(16, 0, 0),
    ]
    available_hours: dict[str, list[datetime.time]] = {
        "Monday": default_work_hours,
        "Tuesday": default_work_hours,
        "Wednesday": default_work_hours,
        "Thursday": default_work_hours,
        "Friday": default_work_hours,
        "Saturday": default_work_hours,
        "Sunday": default_work_hours,
    }

    def generate_free_time_slots(self, start_date: arrow.Arrow, end_date: arrow.Arrow):
        while end_date >= start_date:
            active_week_day = end_date.strftime("%A")

            blocked_slots = list(
                frontend.shared.src.db.TimeSlotsCollection().read(
                    {"time": {"$gte": start_date.datetime, "$lte": end_date.datetime}}
                )
            )

            for time_slot in self.available_hours[active_week_day]:
                if time_slot not in [
                    slot.get("time", datetime.datetime(2025, 1, 1, 0, 0, 0)).tine()
                    for slot in blocked_slots
                ]:
                    yield end_date + time_slot

            end_date = end_date.shift(days=-1)
