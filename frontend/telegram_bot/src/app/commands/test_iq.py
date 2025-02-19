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
    conversation_name: str = "iq"

    def __init__(self):
        super().__init__()
        # TODO: У глеба нужно уточнить что делать с юзерами, кто дропает тест в процессе.
        # TODO: нужно реализовать таймер рестрикта, нужно отфильтровать реди ответы из саммари
        self.commands_distributes_by_phases: dict[
            int,
            dict[
                int, tuple[Callable[..., Any], frontend.shared.src.models.IQTestModel]
            ],
        ] = {1: {}, 2: {}, 3: {}, 4: {}}
        self.commands = tuple(self.generate_command_list())

    async def command_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await self.start_phase(update, context, 1)

    async def callback_handler_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat_id, callback = await frontend.shared.src.utils.handle_callback(
            update.callback_query
        )
        if callback == "":
            await context.bot.send_message(
                chat_id,
                self.error_text,
            )
            return

        split = callback.split("+")
        current_step = int(split[2][4:])
        answer_text = split[3][6:]

        if answer_text == "Ready":
            # TODO: start the timer, create a queue of finishing the test
            pass

    def _generate_function(
        self,
        current_step: int,
        total_amount_of_steps: int,
        media_path: str,
    ) -> types.FunctionType:
        async def template_func(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> int:
            await frontend.shared.src.middleware.main_handler(update, context)
            if update.effective_chat is None or context.user_data is None:
                raise ValueError(
                    "template_func function must only be provided "
                    + "with updates that have effective chat and effective message"
                )
            next_test = frontend.shared.src.db.TestsCollection().read_one(
                {"test_step": current_step + 1}
            )
            is_main_phase_message = False
            if next_test is not None:
                is_main_phase_message = next_test.get("is_main_phase_message", False)

            with open(media_path, "rb") as file:
                media = file.read()
            await context.bot.send_photo(
                update.effective_chat.id,
                media,
                caption=self.question_preset.format(
                    current_step=current_step,
                    total_amount_of_steps=total_amount_of_steps,
                    question_text="",
                ),
                reply_markup=frontend.telegram_bot.src.app.utils.generate_question_answer_keyboard(  # noqa
                    "iq" if is_main_phase_message is not True else "continue",
                    current_step,
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
        test_stages = list(tests_collection.get_iq_questions())
        total_amount_of_steps = len(test_stages)

        for test in test_stages:
            function = self._generate_function(
                current_step=test.test_step,
                total_amount_of_steps=total_amount_of_steps,
                media_path=test.media_location,
            )

            self.commands_distributes_by_phases[test.phase][test.test_step] = (
                function,
                test,
            )

            yield (test.test_step, function)
        yield (total_amount_of_steps + 1, self.finish)

    async def start_phase(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, phase: int
    ) -> int:
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.effective_chat is None or context.user_data is None:
            raise ValueError(
                "template_func function must only be provided "
                + "with updates that have effective chat and effective message"
            )

        # TODO: в модель теста нужно поле количества времени на фазу, и джоб при нажатии на кнопку продолжения на такое количество секунд.
        # При переходе на следующую фазу джоба удаляется. Если исполняется - дёргает флаг в контексте, который проверяется при обработке
        # результатов, и кидает на финиш

        selected_phase = self.commands_distributes_by_phases[phase]
        main_info = list(selected_phase.items())[0]

        information = main_info[1][1]
        with open(information.media_location, "rb") as file:
            media = file.read()
        await context.bot.send_message(
            update.effective_chat.id, information.text.replace("-", "\\-")
        )
        await context.bot.send_photo(
            update.effective_chat.id,
            media,
            reply_markup=frontend.telegram_bot.src.app.utils.generate_question_answer_keyboard(  # noqa
                "continue", main_info[0]
            ),
            parse_mode="HTML",
        )

        return main_info[0]
