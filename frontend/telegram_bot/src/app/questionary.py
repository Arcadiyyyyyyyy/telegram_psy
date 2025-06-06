from abc import abstractmethod
from typing import Any, Callable, Generator, Literal, Optional

import arrow
from loguru import logger
from pydantic import ValidationError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.models
import frontend.shared.src.utils


class ConversationUtils:
    error_text = (
        "Разработчик этого бота допустил ошибку, которую не должен "
        "был допустить. К сожалению, сдать тест в данный момент нельзя."
        " Пожалуйста, перешлите это сообщение в контакт из команды /help"
    )
    question_texts: list[Any]

    def _generate_question_answer_keyboard(
        self,
        *,
        test_name: Literal["atq", "iq", "continue"],
        test_step: int,
        furthest_answered_question: int,
        test_phase: int = 0,
        used_answers: list[str] | None = None,
    ):
        buttons_for_moving_in_between_tests: list[InlineKeyboardButton] = []
        if used_answers is None:
            used_answers = [""]

        if test_name == "atq":
            real_used_answers: list[str] = []
            for answer in used_answers.copy():
                real_used_answers.append(answer.rstrip(" ✅"))
            used_answers = real_used_answers.copy()
            if test_step == 1:
                return InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=f"{answer}",
                                callback_data=f"a+{test_name}+step{test_step}+answer{answer}",  # noqa
                            )
                        ]
                        for answer in [
                            "Мужчина",
                            "Женщина",
                        ]
                    ]
                )
            non_test_questions_in_selected_phase = list(
                frontend.shared.src.db.TestsCollection().read(
                    {
                        "test_name": test_name,
                    },
                    {"test_step": 1},
                )
            )
        else:
            non_test_questions_in_selected_phase = list(
                frontend.shared.src.db.TestsCollection().read(
                    {
                        "test_name": test_name,
                        "is_test_step": False,
                        "phase": test_phase,
                    },
                    {"test_step": 1},
                )
            )

        if test_step > non_test_questions_in_selected_phase[0].get("test_step", 0):
            buttons_for_moving_in_between_tests.append(
                InlineKeyboardButton(
                    "Назад",
                    callback_data=f"a+{test_name}+step{test_step - 2}+answerMove",
                )
            )

        if test_step - 1 < furthest_answered_question:
            buttons_for_moving_in_between_tests.append(
                InlineKeyboardButton(
                    "Вперёд",
                    callback_data=f"a+{test_name}+step{test_step}+answerMove",
                )
            )
            buttons_for_moving_in_between_tests.append(
                InlineKeyboardButton(
                    "Последний",
                    callback_data=f"a+{test_name}+step{furthest_answered_question}+answerMove",  # noqa
                )
            )

        if test_name == "atq":
            answers = [
                "Совершенно неверно",
                "Неверно",
                "Скорее неверно",
                "Трудно сказать",
                "Скорее верно",
                "Верно",
                "Совершенно верно",
            ]
            for i, answer in enumerate(answers.copy()):
                if answer.rstrip(" ✅") in used_answers:
                    answers[i] = f"{answer} ✅"
            result = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"{answer}",
                            callback_data=f"a+{test_name}+step{test_step}+answer{answer}",  # noqa
                        )
                    ]
                    for answer in answers
                ]
                + [buttons_for_moving_in_between_tests]
            )

        elif test_name == "iq":
            answers = [
                "a",
                "b",
                "c",
                "d",
                "e",
            ]
            if test_phase == 1 or test_phase == 3:
                answers.append("f")

            for i, answer in enumerate(answers.copy()):
                if answer in used_answers:
                    answers[i] = f"{answer} ✅"

            result = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"{answer}",
                            callback_data=f"a+{test_name}+step{test_step}+answer{answer}",  # noqa
                        )
                        for answer in answers
                    ]
                ]
                + [buttons_for_moving_in_between_tests]
            )
        elif test_name == "continue":
            result = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"{answer}",
                            callback_data=f"a+iq+step{test_step}+answer{answer}",
                        )
                    ]
                    for answer in ["Готов"]
                ]
            )
        else:
            result = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"{answer}",
                            callback_data=f"a+{test_name}+step{test_step}+answer{answer}",  # noqa
                        )
                    ]
                    for answer in [
                        "No keyboard for you",
                    ]
                ]
            )

        return result

    async def _abort_test(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id

        messages_to_delete: list[int] = []
        if (x := context.user_data.get("explainer_message_ids")) is not None:
            messages_to_delete.extend(x)
        context.user_data["explainer_message_ids"] = []

        for message_id in messages_to_delete:
            try:
                await context.bot.delete_message(chat_id, message_id)
            except Exception:
                pass

        return ConversationHandler.END

    def _save_test_answers(
        self, chat_id: int, conversation_name: str, context: ContextTypes.DEFAULT_TYPE
    ):
        if context.user_data is None:
            raise ValueError
        test_results: dict[str, dict[str, str]] | None = context.user_data.get(
            "test_results"
        )

        if test_results is None:
            context.user_data["test_results"] = {"iq": {}, "atq": {}}
        test_results = context.user_data.get("test_results")
        test_answers_collection = frontend.shared.src.db.TestAnswersCollection()
        if test_results is None:
            raise ValueError

        if not test_results.get(conversation_name, {}):
            return

        new_test_answer: dict[str, Any] = {
            "chat_id": chat_id,
            "test_name": conversation_name,
            "test_results": test_results[conversation_name],
            "started_at": context.user_data["started_at"],
            "finished_at": context.user_data.get(
                "finished_at", arrow.utcnow().datetime
            ),
        }
        filter_to_check_existing_answer: dict[str, Any] = {
            "chat_id": chat_id,
            "test_name": conversation_name,
        }

        if (
            test_answers_collection.read_one(filter_to_check_existing_answer)
            is not None
        ):
            test_answers_collection.update(
                filter_to_check_existing_answer, new_test_answer
            )
        else:
            try:
                test_answers_collection.create_test_answer(
                    frontend.shared.src.models.TestAnswerModel(**new_test_answer)
                )
            except ValidationError:
                logger.critical("Fucking alarma")
                test_results = {"iq": {}, "atq": {}}

    def _reset_iq_answers(self, context: ContextTypes.DEFAULT_TYPE, step: int):
        if context.user_data is None:
            raise ValueError

        context.user_data.get("test_results", {}).get("iq")[f"test_step_{step}"] = ""

    def _save_question_answer(
        self,
        *,
        misc_info: frontend.shared.src.models.CallbackValidationOutput,
        context: ContextTypes.DEFAULT_TYPE,
        is_2_phase_step: bool = False,
    ):
        if context.user_data is None:
            raise ValueError

        test_results: dict[str, dict[str, str]] | None = context.user_data.get(
            "test_results"
        )
        if test_results is None:
            context.user_data["test_results"] = {"iq": {}, "atq": {}}
        test_results = context.user_data.get("test_results", {})
        if test_results is None:
            raise ValueError

        if not is_2_phase_step:
            test_results[misc_info.split[1]][f"test_step_{misc_info.current_step}"] = (
                misc_info.answer_text
            )

    async def _validate_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if context.user_data is None:
            raise ValueError

        # For both
        chat_id, callback = await frontend.shared.src.utils.handle_callback(
            update.callback_query
        )
        split = callback.split("+")
        current_step = int(split[2][4:])
        answer_text = split[3][6:]
        if callback == "":
            message = await context.bot.send_message(
                chat_id,
                self.error_text,
            )
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)
            else:
                context.user_data["explainer_message_ids"] = [message.id]
            return None  # Handle ConversationHandler.END  when calling is None result

        return frontend.shared.src.models.CallbackValidationOutput(
            split=split,
            current_step=current_step,
            answer_text=answer_text,
            chat_id=chat_id,
            callback=callback,
        )


class AbstractConversation:
    @abstractmethod
    async def command_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        pass

    @abstractmethod
    async def finish_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        pass

    @abstractmethod
    async def callback_handler_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        pass

    @abstractmethod
    async def cancel_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        pass

    @abstractmethod
    async def start_phase(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, phase: int
    ) -> int:
        pass

    @abstractmethod
    async def callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int | Any:
        pass

    @abstractmethod
    def generate_command_list(
        self,
    ) -> Generator[tuple[int, Callable[..., Any]], Any, None]:
        pass

    @abstractmethod
    async def _handle_test_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        pass


class Conversation(AbstractConversation, ConversationUtils):
    _instance: Optional["Conversation"] = None
    __initialized: bool

    conversation_name: str
    # commands_distributes_by_phases: dict[int, Any] | None = None
    commands: tuple[tuple[int, Callable[..., Any]], ...]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Conversation, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        if self.__initialized:
            return
        self.__initialized = True

        self.questions: list[dict[str, Any]] = list(
            frontend.shared.src.db.TestsCollection().read(
                {
                    "test_name": self.conversation_name,
                },
                {"test_step": 1},
            )
        )
        self.question_texts = [question["text"] for question in self.questions]

        self.mock_steps: list[dict[str, Any]] | None = (
            [x for x in self.questions if x["is_test_step"] is True]
            if self.conversation_name == "iq"
            else None
        )

        logger.info("Created new conversation instance")

    async def command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat is None or context.user_data is None:
            if update.effective_chat is None:
                return ConversationHandler.END
            message = await context.bot.send_message(
                update.effective_chat.id,
                self.error_text,
            )
            if context.user_data is not None:
                if context.user_data.get("explainer_message_ids") is not None:
                    context.user_data["explainer_message_ids"].append(message.id)
                else:
                    context.user_data["explainer_message_ids"] = [message.id]
            return ConversationHandler.END
        await frontend.shared.src.middleware.main_handler(update, context)
        chat_id = update.effective_chat.id

        await frontend.shared.src.utils.remove_all_messages(chat_id, context)

        context.user_data["explainer_message_ids"] = []
        context.user_data["test_results"] = {"iq": {}, "atq": {}}
        context.user_data["current_test_step"] = None

        test_answers_collection = frontend.shared.src.db.TestAnswersCollection()
        if test_answers_collection.read_one(
            {"chat_id": chat_id, "test_name": self.conversation_name}
        ):
            text = (
                "К сожалению, тест можно сдавать только единожды.\n\n"
                "Пожалуйста, обратись к администратору в "
                "/help если столкнулся с ошибкой."
            )
            message = await context.bot.send_message(chat_id, text)
            if context.user_data.get("explainer_message_ids") is not None:
                context.user_data["explainer_message_ids"].append(message.id)  # type: ignore  # noqa
            else:
                context.user_data["explainer_message_ids"] = [message.id]
            return ConversationHandler.END
        context.user_data["started_at"] = arrow.utcnow().datetime

        await self.notify_test_exit_consequence(update, context)

        return 1

    async def notify_test_exit_consequence(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id
        explainer_message = await context.bot.send_message(
            chat_id,
            "Имей в виду, что нажатие любой команды отличной "
            "от ответа на вопрос во время прохождения теста повлечёт за "
            "собой незамедлительное окончание теста. "
            "Пересдать тест в таком случае невозможно.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Продолжить",
                            callback_data=f"a+{self.conversation_name}+step1+answerПродолжить",  # noqa
                        )
                    ]
                ]
            ),
        )
        context.user_data["explainer_message_ids"].append(explainer_message.id)

    async def finish(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        confirmation_button: bool = False,
    ) -> int:
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        context.user_data["finished_at"] = arrow.utcnow().datetime
        chat_id = update.effective_chat.id

        self._save_test_answers(chat_id, self.conversation_name, context)
        await frontend.shared.src.utils.remove_all_messages(chat_id, context)

        await self.finish_extension(update, context)

        text = ""
        if (
            frontend.shared.src.db.TestAnswersCollection().read_one(
                {
                    "test_name": "atq",
                    "chat_id": chat_id,
                }
            )
            is None
        ):
            text += "Следующим шагом необходимо пройти ATQ тест при помощи команды /atq"
        elif (
            frontend.shared.src.db.TestAnswersCollection().read_one(
                {
                    "test_name": "iq",
                    "chat_id": chat_id,
                }
            )
            is None
        ):
            text += "Следующим шагом необходимо пройти IQ тест при помощи команды /iq"
        else:
            text += (
                "Следующим шагом необходимо записаться на интервью "
                "при помощи команды /book_a_call"
            )

        text_to_send = (
            f"Поздравляем! \n\n"
            "Ты успешно прошел тест, твои ответы сохранены.\n"
            "Спасибо за вклад в исследование.\n\n"
            f"{text}"  # noqa
        )
        if not confirmation_button:
            message = await context.bot.send_message(chat_id, text_to_send)
        else:
            message = await context.bot.send_message(
                chat_id,
                text_to_send,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Продолжить",
                                callback_data=f"a+{self.conversation_name}+step1+answerch_end",  # noqa
                            )
                        ]
                    ]
                ),
            )
        if context.user_data.get("explainer_message_ids") is not None:
            context.user_data["explainer_message_ids"].append(message.id)
        else:
            context.user_data["explainer_message_ids"] = [message.id]
        return ConversationHandler.END

    async def callback_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.callback_query is not None:
            await frontend.shared.src.utils.handle_callback(update.callback_query)
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id
        self._save_test_answers(chat_id, self.conversation_name, context)
        await self.cancel_extension(update, context)
        # result = await frontend.telegram_bot.src.app.utils.abort_test(update, context)
        explainer_message = await context.bot.send_message(
            chat_id,
            "Тест закончен преждевременно.\n\n"
            "Если столкнулся с ошибкой — пожалуйста, обратись в поддержку.",
        )
        context.user_data["explainer_message_ids"].append(explainer_message.id)

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        # context.user_data["test_results"]["iq"] = {}
        chat_id = update.effective_chat.id
        self._save_test_answers(chat_id, self.conversation_name, context)
        await self.cancel_extension(update, context)
        # result = await frontend.telegram_bot.src.app.utils.abort_test(update, context)
        if not (update.message is not None and update.message.text == "/atq"):
            explainer_message = await context.bot.send_message(
                chat_id,
                "Тест закончен преждевременно.\n\n"
                "Если столкнулся с ошибкой — пожалуйста, обратись в поддержку.",
            )
            context.user_data["explainer_message_ids"].append(explainer_message.id)

        return ConversationHandler.END
