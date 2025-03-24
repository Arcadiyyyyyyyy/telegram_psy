import uuid

from telegram import (
    Update,
)
from telegram.ext import ContextTypes

import frontend.admin_bot.src.app.middleware
import frontend.shared.src.db
import frontend.shared.src.file_manager
import frontend.shared.src.middleware
import frontend.shared.src.utils


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if update.effective_chat is None:
        return
    _chat_id = update.effective_chat.id

    answers = list(
        frontend.shared.src.db.TestAnswersCollection().read(
            {"test_name": "iq"},
        )
    )
    total_amount_of_questions_in_test = list(
        frontend.shared.src.db.TestsCollection().read(
            {"test_name": "iq"},
            {"test_step": -1},
        )
    )
    if not answers or not total_amount_of_questions_in_test:
        raise ValueError

    test_question_steps = list(
        x.get("test_step", 0)
        for x in frontend.shared.src.db.TestsCollection().read({"is_test_step": True})
    )

    answers_by_user_id: dict[int, dict[str, str]] = {}

    users_collection = frontend.shared.src.db.UsersCollection()
    tests_collection = frontend.shared.src.db.TestsCollection()
    for answers_document in answers:
        test_results = answers_document.get("test_results", {})
        results_to_add: dict[str, str] = {}
        user = users_collection.read_one({"chat_id": answers_document["chat_id"]})
        if not user:
            raise ValueError
        if user.get("random_id") is None:
            users_collection.update(
                {"chat_id": answers_document["chat_id"]},
                {"random_id": str(uuid.uuid4())},
            )
            user = users_collection.read_one({"chat_id": answers_document["chat_id"]})
            if not user:
                raise ValueError

        for i in range(
            1, total_amount_of_questions_in_test[0].get("test_step", 200) + 1
        ):
            results_to_add[f"test_step_{i}"] = ""

        for key, value in test_results.items():
            results_to_add[key] = value

        answers_by_user_id[user["random_id"]] = results_to_add

    to_dump_to_csv: list[list[str | int]] = []
    if not total_amount_of_questions_in_test:
        await context.bot.send_message(_chat_id, "Error")
    keys: list[str | int] = ["Name"]
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
    for key in answers_by_user_id[list(answers_by_user_id.keys())[0]].keys():
        question_step = int(key[10:])
        test = tests_collection.read_one(
            {"test_step": question_step, "test_name": "iq"}
        )
        if test is None:
            raise ValueError
        if question_step in test_question_steps:
            continue
        keys.append(
            (
                f"Subtest: {test.get('phase', 'Error')}; "
                f"Question: {(test.get('test_step', 0) + 1) - subtest_first_question[test.get('phase', 0)]['test_step']}"
            )
        )
    to_dump_to_csv.append(keys)

    for chat_id, _answers in answers_by_user_id.items():
        to_dump_to_csv.append(
            [chat_id]
            + list(
                [
                    x2
                    for x1, x2 in _answers.items()
                    if int(x1[10:]) not in test_question_steps
                ]
            )
        )

    file_manager = frontend.shared.src.file_manager.FileManager()
    file_manager.write_cache_test_answers(0, "iq", to_dump_to_csv)

    await context.bot.send_document(
        _chat_id, file_manager.read_cache_test_answers(0, "iq")
    )
