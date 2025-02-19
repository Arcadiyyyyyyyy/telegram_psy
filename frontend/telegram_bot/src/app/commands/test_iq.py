import types
from datetime import timedelta
from typing import Any, Callable, Generator

import arrow
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

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
        # TODO: У глеба нужно уточнить что делать с юзерами, кто дропает тест в процессе.  # noqa
        # TODO: нужно отфильтровать реди ответы из саммари  # noqa
        # TODO: нужно изменить логику проверки наличия ответов от пользователя перед началом теста  # noqa
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
        if context.user_data is None or update.effective_chat is None:
            raise ValueError

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
            phase_starter_question = frontend.shared.src.db.TestsCollection().read_one(
                {"test_step": current_step, "test_name": "iq"}
            )
            if phase_starter_question is None:
                raise ValueError("Tests misconfig")
            question = frontend.shared.src.models.IQTestModel(**phase_starter_question)
            if question.seconds_to_pass_the_phase is None:
                logger.error(f"Full question: {phase_starter_question}")
                raise ValueError("Tests misconfig")

            time_of_starting_the_phase = arrow.utcnow()
            expected_to_finish_test_before = time_of_starting_the_phase + timedelta(
                seconds=question.seconds_to_pass_the_phase
            )

            context.job_queue.run_once(  # type: ignore
                callback=self._handle_time_restrictions,
                when=expected_to_finish_test_before.datetime,
                name=f"Time restriction for {question.phase} phase of IQ test for user {chat_id}",  # noqa
                chat_id=chat_id,
                user_id=chat_id,
            )
            logger.info(f"Created a time restriction job for chat id {chat_id}")

        for message_id in context.user_data["explainer_message_ids"]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass
            context.user_data["explainer_message_ids"].remove(message_id)

    async def finish_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_chat is None:
            raise ValueError
        self._remove_time_restriction_jobs(context, update.effective_chat.id)

    async def cancel_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_chat is None:
            raise ValueError
        self._remove_time_restriction_jobs(context, update.effective_chat.id)

    async def _handle_time_restrictions(self, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data is None:
            raise ValueError
        context.user_data["is_failed_to_pass_test_on_time"] = True

    async def _out_of_time_error(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id

        context.user_data["finished_at"] = arrow.utcnow().datetime
        chat_id = update.effective_chat.id

        frontend.telegram_bot.src.app.utils.save_test_answers(
            chat_id, self.conversation_name, context.user_data
        )

        await context.bot.send_message(
            chat_id,
            "К сожалению, вы не успели пройти тест целиком за выделенное время. \n\nВаши результаты сохранены.",
        )

        # TODO: тут возможно текст изменить, и саммари прислать

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
            if context.user_data["is_failed_to_pass_test_on_time"] is True:
                await self._out_of_time_error(update, context)
                return ConversationHandler.END

            next_test = frontend.shared.src.db.TestsCollection().read_one(
                {"test_step": current_step + 1, "test_name": "iq"}
            )
            if next_test is not None:
                next_test = frontend.shared.src.models.IQTestModel(**next_test)
                phase = (
                    next_test.phase
                    if not next_test.is_main_phase_message
                    else next_test.phase - 1
                )
                current_test = self.commands_distributes_by_phases[phase][current_step][
                    1
                ]

                if (
                    current_test.phase == next_test.phase
                    and current_test.is_main_phase_message is True
                ):
                    return await self.start_phase(update, context, next_test.phase)
            else:
                phase = 4

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
                    "iq",
                    current_step,
                    test_phase=phase,
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

        self._remove_time_restriction_jobs(context, update.effective_chat.id)

        selected_phase = self.commands_distributes_by_phases[phase]
        main_info = list(selected_phase.items())[0]

        information = main_info[1][1]
        with open(information.media_location, "rb") as file:
            media = file.read()

        explainer_message = await context.bot.send_message(
            update.effective_chat.id, information.text
        )
        context.user_data["explainer_message_ids"].append(explainer_message.id)

        await context.bot.send_photo(
            update.effective_chat.id,
            media,
            reply_markup=frontend.telegram_bot.src.app.utils.generate_question_answer_keyboard(  # noqa
                "continue",
                main_info[0],
                test_phase=phase,
            ),
            parse_mode="HTML",
        )

        return main_info[0]

    def _remove_time_restriction_jobs(
        self, context: ContextTypes.DEFAULT_TYPE, chat_id: int
    ):
        for phase_number in self.commands_distributes_by_phases.keys():
            name = f"Time restriction for {phase_number} phase of IQ test for user {chat_id}"  # noqa

            jobs = context.job_queue.get_jobs_by_name(  # type: ignore
                name
            )  # noqa
            for job in jobs:  # type: ignore
                job.schedule_removal()
        logger.info(f"Removed jobs for chat_id {chat_id}")
