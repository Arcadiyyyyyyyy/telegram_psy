import datetime
import re
from typing import Any

import arrow
from loguru import logger
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.db
import frontend.shared.src.file_manager
import frontend.shared.src.utils


def telegram_escape_markdown(msg: str) -> str:
    chars = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(chars)}])", r"\\\1", msg)


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

    tests_collection = frontend.shared.src.db.TestsCollection()

    to_dump_to_csv: list[list[str | int]] = []
    test_question_steps = list(
        x.get("test_step", 0) for x in tests_collection.read({"is_test_step": True})
    )

    if conversation_name == "atq":
        for question, _answer in answer["test_results"].items():
            to_dump_to_csv.append([question, _answer])
    elif conversation_name == "iq":
        subtest_first_question: dict[int, int] = {
            1: list(
                tests_collection.read(
                    {"test_name": "iq", "phase": 1, "is_test_step": False},
                    {"test_step": 1},
                )
            )[  # type: ignore # noqa
                0
            ],
            2: list(
                tests_collection.read(
                    {"test_name": "iq", "phase": 2, "is_test_step": False},
                    {"test_step": 1},
                )
            )[  # type: ignore # noqa
                0
            ],
            3: list(
                tests_collection.read(
                    {"test_name": "iq", "phase": 3, "is_test_step": False},
                    {"test_step": 1},
                )
            )[  # type: ignore # noqa
                0
            ],
            4: list(
                tests_collection.read(
                    {"test_name": "iq", "phase": 4, "is_test_step": False},
                    {"test_step": 1},
                )
            )[  # type: ignore # noqa
                0
            ],
        }
        for question, _answer in answer["test_results"].items():
            question_step = int(question[10:])
            test = tests_collection.read_one(
                {"test_name": "iq", "test_step": question_step}
            )
            if test is not None:
                question_aggregation_name = (
                    f"Subtest: {test.get('phase', 'Error')}; "
                    f"Question: {(test.get('test_step', 0) + 1) - subtest_first_question[test['phase']]['test_step']}"  # type: ignore
                )  # type: ignore
            else:
                question_aggregation_name = question
            if question_step not in test_question_steps:
                to_dump_to_csv.append([question_aggregation_name, _answer])

    file_manager = frontend.shared.src.file_manager.FileManager()
    file_manager.write_cache_test_answers(chat_id, conversation_name, to_dump_to_csv)

    return "", file_manager.read_cache_test_answers(chat_id, conversation_name)


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
        datetime.time(13, 0, 0),
        datetime.time(14, 30, 0),
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
        end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while end_date >= start_date:
            active_week_day = end_date.strftime("%A")

            blocked_slots = list(
                frontend.shared.src.db.TimeSlotsCollection().read(
                    {
                        "time": {
                            "$gte": start_date.datetime,
                            "$lte": end_date.datetime + datetime.timedelta(days=1),
                        }
                    }
                )
            )

            for time_slot in self.available_hours[active_week_day]:
                delta = datetime.timedelta(
                    hours=time_slot.hour, minutes=time_slot.minute
                )
                result = end_date + delta
                slots_to_compare_against = [
                    slot.get("time", datetime.datetime(2025, 1, 1, 0, 0, 0))
                    for slot in blocked_slots
                ]
                if result.datetime.replace(tzinfo=None) not in slots_to_compare_against:
                    yield result
            end_date = end_date.shift(days=-1)

    def get_available_slots_by_days(
        self,
        start_date: arrow.Arrow,
        end_date: arrow.Arrow,
    ):
        available_slots = sorted(
            list(self.generate_free_time_slots(start_date, end_date))
        )
        if available_slots:
            active_day = available_slots[0].clone()
            active_day = active_day.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            yield []
            return

        while active_day < available_slots[-1]:
            result: list[arrow.Arrow] = []
            for slot in available_slots:
                if slot > active_day and slot < active_day.shift(days=1):
                    result.append(slot)
            yield result
            active_day = active_day.shift(days=1)


async def remove_all_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        raise ValueError

    messages_to_delete: list[int] = []
    if (x := context.user_data.get("explainer_message_ids")) is not None:
        messages_to_delete.extend(x)
    context.user_data["explainer_message_ids"] = []
    for message_id in messages_to_delete:
        try:
            await context.bot.delete_message(chat_id, message_id)
        except Exception:
            pass
