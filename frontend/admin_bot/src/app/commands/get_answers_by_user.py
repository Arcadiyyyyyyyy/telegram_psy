from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.admin_bot
import frontend.admin_bot.src
import frontend.admin_bot.src.app
import frontend.admin_bot.src.app.middleware
import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.utils


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    await frontend.shared.src.middleware.main_handler(update, context)
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    if update.effective_chat is None:
        return

    chat_id = update.effective_chat.id

    user_data = [
        (
            f"{user['first_name']} | {user['username']} | {user['chat_id']}",
            user["chat_id"],
        )
        for user in frontend.shared.src.db.UsersCollection().read({}, {"created_at": 1})
    ]

    await context.bot.send_message(
        chat_id,
        "Тут можно получить информацию о прохождении теста конкретным пользователем \n\nСписок пользователей бота:",  # noqa
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text[0], callback_data=f"s+ans_by_u+{text[1]}")]
                for text in user_data
            ]
        ),
    )


async def select_the_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    if update.effective_chat is None or update.callback_query is None:
        raise ValueError
    chat_id, callback = await frontend.shared.src.utils.handle_callback(
        update.callback_query
    )

    split_callback = callback.split("+")
    userid_to_check = split_callback[2]
    tests_answers_collection = frontend.shared.src.db.TestAnswersCollection()

    get_tests_that_were_passed_by_the_user = list(
        tests_answers_collection.read(
            {"chat_id": int(userid_to_check), "finished_at": {"$ne": None}},
            {"created_at": 1},
        )
    )

    if not get_tests_that_were_passed_by_the_user:
        await context.bot.send_message(
            chat_id,
            "Этот пользователь не прошёл ни одного теста",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Назад", callback_data="s+ansvs")]]
            ),
        )
    else:
        await context.bot.send_message(
            chat_id,
            "Результаты какого теста вы хотите изучить?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            test["test_name"],
                            callback_data=f"s+ans_by_uid_and_test+{userid_to_check}+{test['test_name']}",  # noqa
                        )
                    ]
                    for test in get_tests_that_were_passed_by_the_user
                ]
            ),
        )


async def show_the_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    if update.effective_chat is None or update.callback_query is None:
        raise ValueError
    chat_id, callback = await frontend.shared.src.utils.handle_callback(
        update.callback_query
    )

    split_callback = callback.split("+")
    userid_to_check = split_callback[2]
    test_to_check = split_callback[3]

    text = frontend.shared.src.utils.generate_test_answers_info(
        int(userid_to_check), test_to_check
    )

    texts_to_send = frontend.shared.src.utils.split_string(text)
    for t in texts_to_send:
        await context.bot.send_message(
            chat_id,
            t,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Delete test answer",
                            callback_data=f"d+ans_by_uid_and_test+{userid_to_check}+{test_to_check}",  # noqa
                        )
                    ]
                ]
            ),
        )


async def delete_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await frontend.admin_bot.src.app.middleware.is_admin(update, context):
        return
    if update.effective_chat is None or update.callback_query is None:
        raise ValueError
    chat_id, callback = await frontend.shared.src.utils.handle_callback(
        update.callback_query
    )

    split_callback = callback.split("+")
    userid_to_check = split_callback[2]
    test_to_delete = split_callback[3]

    frontend.shared.src.db.TestAnswersCollection().delete(
        {"test_name": test_to_delete, "chat_id": int(userid_to_check)}
    )

    await context.bot.send_message(chat_id, "Deleted")
