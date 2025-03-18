import types
from datetime import timedelta
from typing import Any, Callable, Generator

import arrow
from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.models
import frontend.shared.src.utils
import frontend.telegram_bot.src.app.questionary


class Conversation(frontend.telegram_bot.src.app.questionary.Conversation):
    conversation_name: str = "iq"

    def __init__(self):
        super().__init__()
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
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        explainer_message = await context.bot.send_message(
            update.effective_chat.id,
            "Тебе нужно будет пройти четыре теста, которые похожи на четыре различные игры-головоломки. \n"  # noqa
            "В них нет слов, только рисунки. \n"
            "В каждом тесте есть примеры, которые нужны для того, чтобы понять, как выполнять задания. \n"  # noqa
            "Некоторые задания в конце тестов могут быть очень сложными, однако попробуй решить как можно больше заданий. \n"  # noqa
            "Даже если ты не уверен – выбери вариант ответа, который по твоему мнению может быть правильным. \n"  # noqa
            "Если ты не уверен какой ответ правильный – можно попытаться угадать, так как за неправильные ответы ты не теряешь баллы.\n\n"  # noqa
            "В начале каждого из четырех тестов будет несколько тренировок, чтобы понять как решаются головоломки.",  # noqa
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Продолжить",
                            callback_data=f"a+{self.conversation_name}+step2+answerПродолжить1",  # noqa
                        )
                    ]
                ]
            ),
        )
        context.user_data["explainer_message_ids"].append(explainer_message.id)
        result = {}
        for x in frontend.shared.src.db.TestsCollection().read(
            {"test_name": self.conversation_name, "phase": 2},
            {"test_step": 1},
        ):
            result[x["test_step"]] = ""

        context.user_data["phase_2_answers"] = result

    async def callback_handler_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if (
            context.user_data is None
            or update.effective_chat is None
            or update.effective_message is None
        ):
            raise ValueError

        chat_id, callback = await frontend.shared.src.utils.handle_callback(
            update.callback_query
        )
        if callback == "":
            message = await context.bot.send_message(
                chat_id,
                self.error_text,
            )
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)
            else:
                context.user_data["explainer_message_ids"] = [message.id]
            return True

        split = callback.split("+")
        current_step = int(split[2][4:])
        answer_text = split[3][6:]
        test = frontend.shared.src.db.TestsCollection().read_one(
            {"test_name": self.conversation_name, "test_step": current_step}
        )
        if test is None:
            raise ValueError
        current_phase = int(test["phase"])

        if current_phase == 2 and answer_text != "Готов":
            answer_text = split[3][6:][0]

            if not (phase_2_answers := context.user_data.get("phase_2_answers", {})):
                raise ValueError
            if answer_text in phase_2_answers[current_step]:
                phase_2_answers[current_step] = phase_2_answers[current_step].replace(
                    answer_text, ""
                )
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id,
                        update.effective_message.id,
                        reply_markup=self._generate_question_answer_keyboard(  # noqa
                            self.conversation_name,  # type: ignore
                            current_step,
                            current_phase,
                            phase_2_answers[current_step].replace(answer_text, ""),
                        ),
                    )
                except Exception:
                    pass
                return True
            elif answer_text not in phase_2_answers[current_step]:
                phase_2_answers[current_step] += answer_text
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id,
                        update.effective_message.id,
                        reply_markup=self._generate_question_answer_keyboard(  # noqa
                            self.conversation_name,  # type: ignore
                            current_step,
                            current_phase,
                            phase_2_answers[current_step],
                        ),
                    )
                except Exception:
                    pass
                if len(phase_2_answers[current_step]) >= 2:
                    return False
                else:
                    return True

        if answer_text == "Готов":
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
                data=update,
            )
            logger.info(f"Created a time restriction job for chat id {chat_id}")

        for message_id in context.user_data["explainer_message_ids"]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass
            context.user_data["explainer_message_ids"].remove(message_id)

        return False

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
        if context.user_data is None or context.job is None:
            raise ValueError
        chat_id = context.job.chat_id
        if chat_id is None:
            raise ValueError
        kwargs: Update | None = context.job.data  # type: ignore
        if kwargs is None:
            raise ValueError

        await self._abort_test(kwargs, context)
        current_test_step = context.user_data["current_test_step"]
        context.user_data["current_test_step"] = None

        current_test = frontend.shared.src.db.TestsCollection().read_one(
            {"test_name": self.conversation_name, "test_step": current_test_step}
        )
        if current_test is None:
            raise ValueError
        current_phase = current_test["phase"]

        if current_phase + 1 < 4:
            message = await context.bot.send_message(
                chat_id,
                "Время на этот тест закончилось. "
                "\n\nТвои результаты сохранены, ты можешь "
                "приступить к продолжению теста когда будешь готов.",
            )
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)
            else:
                context.user_data["explainer_message_ids"] = [message.id]
            await self.start_phase(kwargs, context, current_phase + 1)
        else:
            message = await context.bot.send_message(
                chat_id,
                "К сожалению, ты не успел пройти тест целиком за выделенное время. "
                "\n\nТвои результаты сохранены.",
            )
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)
            else:
                context.user_data["explainer_message_ids"] = [message.id]
            return ConversationHandler.END

    def _generate_function(
        self,
        current_step: int,
        media_path: str,
    ) -> types.FunctionType:
        async def template_func(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> int:
            if update.effective_chat is None or context.user_data is None:
                raise ValueError(
                    "template_func function must only be provided "
                    + "with updates that have effective chat and effective message"
                )

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
                test_text = current_test.text

                if (
                    current_test.phase == next_test.phase
                    and current_test.is_main_phase_message is True
                ):
                    return await self.start_phase(update, context, next_test.phase)
            else:
                phase = 4
                test_text = ""

            with open(media_path, "rb") as file:
                media = file.read()
            response = await context.bot.send_photo(
                update.effective_chat.id,
                media,
                caption=test_text,
                reply_markup=self._generate_question_answer_keyboard(  # noqa
                    "iq",
                    current_step,
                    test_phase=phase,
                ),
            )
            context.user_data["last_sent_test_message_id"] = response.message_id
            context.user_data["current_test_step"] = current_step

            return current_step + 1

        return types.FunctionType(
            template_func.__code__, globals(), closure=template_func.__closure__
        )

    async def _handle_mock_test_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *,
        current_step: int,
        answer_text: str,
    ):
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id

        current_test = frontend.shared.src.db.TestsCollection().read_one(
            {"test_name": self.conversation_name, "test_step": current_step}
        )
        if current_test is None:
            raise ValueError
        expected_answer: str = current_test.get("correct_answer", "")
        is_phase_2 = current_step in self.commands_distributes_by_phases[2].keys()
        if is_phase_2:
            answer = context.user_data.get("phase_2_answers", {})
            if not answer:
                raise ValueError
            answer_text = answer[current_step]

        if is_phase_2 and len(answer_text) <= 1:
            return
        else:
            await frontend.shared.src.middleware.main_handler(update, context)

        if (
            answer_text.translate(
                str.maketrans(expected_answer, " " * len(expected_answer))
            ).replace(" ", "")
            == ""
        ):
            explainer_message = await context.bot.send_message(
                chat_id,
                "Правильный ответ!",
            )
        else:
            previous_test = frontend.shared.src.db.TestsCollection().read_one(
                {"test_name": self.conversation_name, "test_step": current_step}
            )
            if previous_test is None:
                raise ValueError
            with open(previous_test.get("media_location", ""), "rb") as file:
                media = file.read()
            explainer_message = await context.bot.send_photo(
                chat_id,
                media,
                caption=f"Неправильный ответ.\n\n"
                f"Вы ответили: {' и '.join(answer_text)}\n\n"
                f"Правильный ответ: {' и '.join(expected_answer)}",
            )
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(explainer_message.id)

    def generate_command_list(
        self,
    ) -> Generator[tuple[int, Callable[..., Any]], Any, None]:
        tests_collection = frontend.shared.src.db.TestsCollection()
        test_stages = list(tests_collection.get_iq_questions())
        total_amount_of_steps = len(test_stages)

        for test in test_stages:
            function = self._generate_function(
                current_step=test.test_step,
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
        if update.effective_chat is None or context.user_data is None:
            raise ValueError

        self._remove_time_restriction_jobs(context, update.effective_chat.id)

        selected_phase = self.commands_distributes_by_phases[phase]
        main_info = list(selected_phase.items())[0]

        information = main_info[1][1]
        with open(information.media_location, "rb") as file:
            media = file.read()

        response = await context.bot.send_photo(
            update.effective_chat.id,
            media,
            caption=information.text,
            reply_markup=self._generate_question_answer_keyboard(  # noqa
                "iq",
                main_info[0],
                test_phase=phase,
            ),
            parse_mode="HTML",
        )

        context.user_data["last_sent_test_message_id"] = response.message_id
        context.user_data["current_test_step"] = main_info[0]

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
