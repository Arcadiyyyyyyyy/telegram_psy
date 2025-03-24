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
import frontend.telegram_bot.src.app.commands
import frontend.telegram_bot.src.app.commands.menu
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
        await frontend.shared.src.utils.remove_all_messages(
            update.effective_chat.id, context
        )
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

    async def _handle_real_2_phase_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        misc_info: frontend.shared.src.models.CallbackValidationOutput,
    ):
        if (
            context.user_data is None
            or update.effective_chat is None
            or update.effective_message is None
        ):
            raise ValueError

        test = frontend.shared.src.db.TestsCollection().read_one(
            {"test_name": self.conversation_name, "test_step": misc_info.current_step}
        )
        if test is None:
            raise ValueError
        current_phase = int(test["phase"])

        answer_text = misc_info.split[3][6:][0]
        test_results_get_arg = f"test_step_{misc_info.current_step}"

        if not (test_results := context.user_data.get("test_results", {}).get("iq")):
            raise ValueError
        if test_results.get(test_results_get_arg) is None:
            test_results[test_results_get_arg] = ""
        if answer_text in test_results[test_results_get_arg]:
            logger.warning(test_results[test_results_get_arg])
            test_results[test_results_get_arg] = test_results[
                test_results_get_arg
            ].replace(answer_text, "")
            logger.warning(test_results[test_results_get_arg])
            try:
                # MARK: TODO: check who the fuck are phase two answers
                await context.bot.edit_message_reply_markup(
                    misc_info.chat_id,
                    update.effective_message.id,
                    reply_markup=self._generate_question_answer_keyboard(  # noqa
                        test_name=self.conversation_name,  # type: ignore
                        test_step=misc_info.current_step,
                        furthest_answered_question=max(
                            [
                                int(x[10:])
                                for x in context.user_data.get("test_results", {})
                                .get("atq", {})
                                .keys()
                            ]
                            + [0]
                        ),
                        test_phase=current_phase,
                        used_answers=test_results[test_results_get_arg].replace(
                            answer_text, ""
                        ),
                    ),
                )
            except Exception:
                pass
            return True
        elif (
            answer_text != "Move"
            and answer_text not in test_results[test_results_get_arg]
        ):
            # TODO: вот это страшное багающее место, которое не ясно как решать
            # Если чел дважды нажимает на кнопку при сдаче теста - ответ сбрасывается
            amount_of_answers = len(test_results.get(test_results_get_arg, "1"))
            if amount_of_answers >= 2:
                self._reset_iq_answers(context, misc_info.current_step)

            test_results[test_results_get_arg] += answer_text
            try:
                await context.bot.edit_message_reply_markup(
                    misc_info.chat_id,
                    update.effective_message.id,
                    reply_markup=self._generate_question_answer_keyboard(  # noqa
                        test_name=self.conversation_name,  # type: ignore
                        test_step=misc_info.current_step,
                        furthest_answered_question=max(
                            [
                                int(x[10:])
                                for x in context.user_data.get("test_results", {})
                                .get("atq", {})
                                .keys()
                            ]
                            + [0]
                        ),
                        test_phase=current_phase,
                        used_answers=test_results[test_results_get_arg],
                    ),
                )
            except Exception:
                pass
            if len(test_results[test_results_get_arg]) >= 2:
                return False
            else:
                return True

    async def callback_handler_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
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

        if (misc_info := await self._validate_callback(update, context)) is None:
            raise ValueError

        test = frontend.shared.src.db.TestsCollection().read_one(
            {"test_name": self.conversation_name, "test_step": misc_info.current_step}
        )
        if test is None:
            raise ValueError
        current_phase = int(test["phase"])

        if current_phase == 2 and misc_info.answer_text not in ["Готов", "Move"]:
            phase_2_result = await self._handle_real_2_phase_answer(
                update, context, misc_info
            )
            if isinstance(phase_2_result, bool):
                return phase_2_result

        if misc_info.answer_text == "Готов":
            phase_starter_question = frontend.shared.src.db.TestsCollection().read_one(
                {"test_step": misc_info.current_step, "test_name": "iq"}
            )
            if phase_starter_question is None:
                raise ValueError("Tests miss config")
            question = frontend.shared.src.models.IQTestModel(**phase_starter_question)
            if question.seconds_to_pass_the_phase is None:
                raise ValueError("Tests miss config")

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

        await frontend.shared.src.utils.remove_all_messages(chat_id, context)

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
        if not (update.message is not None and update.message.text == "/atq"):
            chat_id = update.effective_chat.id
            await frontend.shared.src.utils.remove_all_messages(chat_id, context)

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

        if current_phase < 4:
            message = await context.bot.send_message(
                chat_id,
                "Время на этот тест закончилось. "
                "\n\nТвои результаты сохранены, ты можешь "
                " приступить к следующему тесту, когда будешь готов.",
            )
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)
            else:
                context.user_data["explainer_message_ids"] = [message.id]
            await self.start_phase(kwargs, context, current_phase + 1)
        else:
            return await self.finish(kwargs, context, confirmation_button=True)

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
                    test_name="iq",
                    test_step=current_step,
                    furthest_answered_question=max(
                        [
                            int(x[10:])
                            for x in context.user_data.get("test_results", {})
                            .get("iq", {})
                            .keys()
                        ]
                        + [0]
                    ),
                    test_phase=phase,
                ),
            )
            context.user_data["explainer_message_ids"].append(response.message_id)
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
        reasoning: str | None = current_test.get("answer_reasoning")
        is_phase_2 = current_step in self.commands_distributes_by_phases[2].keys()
        if is_phase_2:
            answer = context.user_data.get("test_results", {}).get("iq", {})
            if not answer:
                raise ValueError
            answer_text = answer[f"test_step_{current_step}"]

        if is_phase_2 and len(answer_text) <= 1:
            return
        else:
            await frontend.shared.src.utils.remove_all_messages(chat_id, context)
            await frontend.shared.src.middleware.main_handler(update, context)

        if (
            answer_text.translate(
                str.maketrans(expected_answer, " " * len(expected_answer))
            ).replace(" ", "")
            == ""
        ):
            text = "Правильный ответ!"
            if reasoning is not None:
                text += f"\n\n{reasoning}"
            explainer_message = await context.bot.send_message(
                chat_id,
                text,
            )
        else:
            previous_test = frontend.shared.src.db.TestsCollection().read_one(
                {"test_name": self.conversation_name, "test_step": current_step}
            )
            if previous_test is None:
                raise ValueError
            with open(previous_test.get("media_location", ""), "rb") as file:
                media = file.read()
            text = (
                f"Неправильный ответ.\n\n"
                f"Ты ответил: {' и '.join(answer_text)}\n\n"
                f"Правильный ответ: {' и '.join(expected_answer)}"
            )
            if reasoning is not None:
                text += f"\n\n{reasoning}"
            explainer_message = await context.bot.send_photo(
                chat_id,
                media,
                caption=text,
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
                test_phase=phase,
                test_name="iq",
                test_step=main_info[0],
                furthest_answered_question=max(
                    [
                        int(x[10:])
                        for x in context.user_data.get("test_results", {})
                        .get("iq", {})
                        .keys()
                    ]
                    + [0]
                ),
            ),
            parse_mode="HTML",
        )

        context.user_data["explainer_message_ids"].append(response.message_id)
        context.user_data["current_test_step"] = main_info[0]

        return main_info[0]

    async def callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_message is None or context.user_data is None:
            raise ValueError

        if (misc_info := await self._validate_callback(update, context)) is None:
            return ConversationHandler.END

        is_next_step_blocked = await self.callback_handler_extension(update, context)
        try:
            if not is_next_step_blocked:
                await context.bot.delete_message(
                    misc_info.chat_id, update.effective_message.id
                )
        except Exception:
            pass

        if misc_info.answer_text == "Move":
            # если аргумент для мува отличный от текущей фазы или больше максимального то соси # noqa
            await frontend.shared.src.utils.remove_all_messages(
                misc_info.chat_id, context
            )
            return await self.commands[misc_info.current_step][1](update, context)
        if misc_info.answer_text == "ch_end":
            await frontend.telegram_bot.src.app.commands.menu.command(update, context)
            return ConversationHandler.END

        next_step = await self._handle_test_answer(update, context)

        if misc_info.answer_text == "Продолжить":
            await self.command_extension(update, context)
            return next_step

        current_test = frontend.shared.src.db.TestsCollection().read_one(
            {"test_step": next_step, "test_name": self.conversation_name}
        )
        if current_test is None:
            raise ValueError
        if misc_info.answer_text == "Продолжить1":
            await self.start_phase(update, context, 1)
            return next_step
        if is_next_step_blocked:
            return next_step

        if misc_info.answer_text == "Готов":
            await frontend.shared.src.utils.remove_all_messages(
                misc_info.chat_id, context
            )

        if (
            current_test.get("seconds_to_pass_the_phase") is not None
            and misc_info.answer_text != "Готов"
        ):
            message = await context.bot.send_message(
                misc_info.chat_id,
                "На этом тренировки к этому тесту закончились. "
                "\nТебе может не хватить времени, чтобы выполнить все задания. "
                "Работай так быстро и внимательно, как сможешь.\n"
                "Когда будешь готов начать тест — нажми на кнопку внизу, чтобы запустить таймер.",  # noqa
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Готов",
                                callback_data=f"a+{self.conversation_name}+step{next_step}+answerГотов",  # noqa
                            )
                        ]
                    ]
                ),
            )
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)  # type: ignore # noqa
            return next_step

        return await self.commands[next_step][1](update, context)

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
        if misc_info.answer_text in ["Продолжить1"]:
            return misc_info.current_step - 1
        if misc_info.answer_text in ["Move"]:
            return misc_info.current_step

        try:
            if self.mock_steps is not None:
                current_test = [
                    x
                    for x in self.mock_steps
                    if int(x["test_step"]) == misc_info.current_step
                ][0]
            else:
                current_test = {}
        except IndexError:
            current_test = {}
        if is_test_step := (
            int(misc_info.current_step) == int(current_test.get("test_step", -1))
        ):
            await self._handle_mock_test_answer(
                update,
                context,
                current_step=misc_info.current_step,
                answer_text=misc_info.answer_text,
            )
            return misc_info.current_step

        is_2_phase_step = (
            misc_info.current_step in self.commands_distributes_by_phases[2].keys()
        )

        if not is_test_step:
            self._save_question_answer(
                misc_info=misc_info,
                context=context,
                is_2_phase_step=is_2_phase_step,
            )

        return misc_info.current_step
