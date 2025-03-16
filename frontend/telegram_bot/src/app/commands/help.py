from telegram import Update
from telegram.ext import ContextTypes

import frontend.shared.src.middleware


async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat is None:
        return
    await frontend.shared.src.middleware.main_handler(update, context)

    message = await context.bot.send_message(
        update.effective_chat.id,
        "Чтобы сбросить результаты теста, задать любой вопрос, или уведомить "
        "о технических проблемах бота - пожалуйста, обратитесь в @Phase_trade",
    )
    if context.user_data is not None:
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(message.id)
        else:
            context.user_data["explainer_message_ids"] = [message.id]
