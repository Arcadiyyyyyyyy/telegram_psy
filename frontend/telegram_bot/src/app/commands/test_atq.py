import types
from typing import Any, Callable, Generator

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.models
import frontend.shared.src.utils
import frontend.telegram_bot.src.app.questionary


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
                raise ValueError
            await frontend.shared.src.utils.remove_all_messages(
                update.effective_chat.id, context
            )

            chat_id = update.effective_chat.id
            response = await context.bot.send_message(
                chat_id,
                question_text,
                reply_markup=self._generate_question_answer_keyboard(  # noqa
                    test_name="atq",
                    test_step=current_step,
                    furthest_answered_question=max(
                        [
                            int(x[10:])
                            for x in context.user_data.get("test_results", {})
                            .get("atq", {})
                            .keys()
                        ]
                        + [0]
                    ),
                ),
            )
            if current_step != 1:
                await frontend.shared.src.utils.remove_all_messages(chat_id, context)
            context.user_data["explainer_message_ids"].append(response.id)

            return current_step + 1

        # TODO: изучить в свободное время персист джоб куеуе
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
            )

            yield (test.test_step, function)
        yield (total_amount_of_steps + 1, self.finish)

    async def callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_message is None or context.user_data is None:
            raise ValueError

        if (misc_info := await self._validate_callback(update, context)) is None:
            return ConversationHandler.END

        if misc_info.answer_text == "Move":
            # если аргумент для мува отличный от текущей фазы или больше максимального то соси # noqa
            return await self.commands[misc_info.current_step][1](update, context)

        next_step = await self._handle_test_answer(update, context)
        if misc_info.answer_text == "Продолжить":
            await self.command_extension(update, context)
            return next_step

        if misc_info.answer_text == "Готов":
            await frontend.shared.src.utils.remove_all_messages(
                misc_info.chat_id, context
            )

        return await self.commands[next_step][1](update, context)

    async def _handle_test_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Returns next command id"""
        if context.user_data is None:
            raise ValueError
        if (misc_info := await self._validate_callback(update, context)) is None:
            raise ValueError

        if misc_info.answer_text in ["Готов", "Продолжить"]:
            return misc_info.current_step

        self._save_question_answer(
            misc_info=misc_info,
            context=context,
        )

        return misc_info.current_step

    async def cancel_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id
        await frontend.shared.src.utils.remove_all_messages(chat_id, context)
