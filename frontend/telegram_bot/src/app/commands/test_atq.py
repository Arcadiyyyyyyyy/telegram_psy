import types
from typing import Any, Callable, Generator

from telegram import Update
from telegram.ext import ContextTypes

import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.models
import frontend.shared.src.utils
import frontend.telegram_bot.src.app.questionary
import frontend.telegram_bot.src.app.utils


class Conversation(frontend.telegram_bot.src.app.questionary.Conversation):
    conversation_name: str = "atq"

    def __init__(self):
        super().__init__()
        self.commands = tuple(self.generate_command_list())

    async def command_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await self.commands[0][1](update, context)

    def _generate_function(
        self,
        question_text: str,
        current_step: int,
        total_amount_of_steps: int,
    ) -> types.FunctionType:
        async def template_func(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> int:
            await frontend.shared.src.middleware.main_handler(update, context)
            if (
                update.effective_message is None
                or update.effective_chat is None
                or context.user_data is None
            ):
                raise ValueError(
                    "template_func function must only be provided "
                    + "with updates that have effective chat and effective message"
                )
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id,
                self.question_preset.format(
                    current_step=current_step,
                    total_amount_of_steps=total_amount_of_steps,
                    question_text=question_text,
                ),
                reply_markup=frontend.telegram_bot.src.app.utils.generate_question_answer_keyboard(  # noqa
                    "atq", current_step
                ),
            )
            return current_step + 1

        return types.FunctionType(
            template_func.__code__, globals(), closure=template_func.__closure__
        )

    def generate_command_list(
        self,
    ) -> Generator[tuple[int, Callable[..., Any]], Any, None]:
        tests_collection = frontend.shared.src.db.TestsCollection()

        tests = list(tests_collection.get_atq_questions())
        total_amount_of_steps = len(tests)

        for test in tests:
            function = self._generate_function(
                question_text=test.text,
                current_step=test.test_step,
                total_amount_of_steps=total_amount_of_steps,
            )

            yield (test.test_step, function)
        yield (total_amount_of_steps + 1, self.finish)
