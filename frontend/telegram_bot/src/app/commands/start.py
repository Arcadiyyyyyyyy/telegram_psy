from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import frontend.shared.src.middleware
import frontend.telegram_bot
import frontend.telegram_bot.src
import frontend.telegram_bot.src.app
import frontend.telegram_bot.src.app.commands
import frontend.telegram_bot.src.app.commands.menu


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id,
        "Привет!\n\nСпасибо, что согласился принять участие в нашем исследовании. \n"
        "Мы команда исследователей, которые хотят изучить взаимосвязь личностных характеристик и рабочей эффективности. \n"
        "Участие в исследовании полностью добровольное, это значит, что ты можешь прекратить в любой момент. \n"
        "Но мы очень будем признательны, если ты пройдешь исследование целиком. \n"
        "Данные будут полностью анонимизированы и доступны только исследовательской команде. \n"
        "Продолжая общение с ботом ты даешь право на сбор, обработку и хранение своей персональной информации.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Продолжить", callback_data="s+notify_about_pipeline"
                    ),
                    InlineKeyboardButton("Выйти", callback_data="d+message"),
                ]
            ]
        ),
    )


async def notify_about_the_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        raise ValueError
    await frontend.shared.src.middleware.main_handler(update, context)
    chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id,
        "Отлично! Наше исследование состоит из трех частей: двух тестов в этом боте и интервью. \n"
        "Для прохождения двух тестов нужно выделить не менее 15 минут в тихом месте, где ты сможешь сконцентрироваться. \n"
        "Это особенно важно для прохождения теста IQ, так как его нельзя проходить дважды. \n"
        "После прохождения тестов запишись, пожалуйста, на интервью. \n"
        "На него нужно выделить не менее 90 минут. \n\n"
        "В качестве благодарности мы можем выслать тебе результаты теста IQ и теста на определение темперамента",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Хорошо", callback_data="r+menu"),
                ]
            ]
        ),
    )
