from abc import abstractmethod
from typing import Any, Callable, Generator, Literal, Optional

import arrow
from loguru import logger
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
        test_name: Literal["atq", "iq", "continue"],
        test_step: int,
        test_phase: int = 0,
        used_answers: str = "",
    ):
        if test_name == "atq":
            result = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"{answer}",
                            callback_data=f"a+{test_name}+step{test_step}+answer{answer}",  # noqa
                        )
                    ]
                    for answer in [
                        "Совершенно неверно",
                        "Неверно",
                        "Скорее неверно",
                        "Трудно сказать",
                        "Скорее верно",
                        "Верно",
                        "Совершенно верно",
                    ]
                ]
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
        if (x := context.user_data.get("last_sent_test_message_id")) is not None:
            messages_to_delete.append(x)
        context.user_data["last_sent_test_message_id"] = None

        for message_id in messages_to_delete:
            try:
                await context.bot.delete_message(chat_id, message_id)
            except Exception:
                pass

        return ConversationHandler.END

    def _save_test_answers(
        self, chat_id: int, conversation_name: str, user_data: dict[str, Any]
    ):
        answers: list[str] = user_data["answers"]
        questions: list[str] = user_data["questions"]

        test_answers_collection = frontend.shared.src.db.TestAnswersCollection()

        if not answers:
            return

        new_test_answer: dict[str, Any] = {
            "chat_id": chat_id,
            "test_name": conversation_name,
            "answers": answers,
            "questions": questions,
            "started_at": user_data["started_at"],
            "finished_at": user_data.get("finished_at", arrow.utcnow().datetime),
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
            test_answers_collection.create_test_answer(
                frontend.shared.src.models.TestAnswerModel(**new_test_answer)
            )

    def _save_question_answer(
        self,
        *,
        misc_info: frontend.shared.src.models.CallbackValidationOutput,
        context: ContextTypes.DEFAULT_TYPE,
        is_2_phase_step: bool = False,
        amount_of_answers: int = 1,
        _answers: dict[int, str] = {},
    ):
        if context.user_data is None:
            raise ValueError

        previous_question_text = self.question_texts[misc_info.current_step - 1]
        answers: list[Any] | None = context.user_data.get("answers")
        questions: list[Any] | None = context.user_data.get("questions")
        if answers is None:
            context.user_data["answers"] = []
        del answers
        valid_answers: list[str] = context.user_data["answers"]
        if is_2_phase_step:
            if amount_of_answers >= 2:
                valid_answers.append(_answers[misc_info.current_step])
        else:
            valid_answers.append(misc_info.answer_text)
        if questions is None:
            context.user_data["questions"] = []
        del questions
        valid_questions: list[str] = context.user_data["questions"]
        if is_2_phase_step:
            if amount_of_answers >= 2:
                valid_questions.append(previous_question_text)
        else:
            valid_questions.append(previous_question_text)

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

        context.user_data["answers"] = []
        context.user_data["questions"] = []
        context.user_data["explainer_message_ids"] = []
        context.user_data["last_sent_test_message_id"] = None
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
                print(context.user_data["explainer_message_ids"])
                context.user_data["explainer_message_ids"].append(message.id)  # type: ignore
                print(context.user_data["explainer_message_ids"])
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

        self._save_test_answers(chat_id, self.conversation_name, context.user_data)

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
            text += "Следующим шагом необходимо записаться на интервью "
            "при помощи команды /book_a_call"

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
        self._save_test_answers(chat_id, self.conversation_name, context.user_data)
        await self.cancel_extension(update, context)
        # result = await frontend.telegram_bot.src.app.utils.abort_test(update, context)
        explainer_message = await context.bot.send_message(
            chat_id,
            "Тест закончен преждевременно.\n\n"
            "Если столкнулся с ошибкой - пожалуйста, обратись в поддержку.",
        )
        context.user_data["explainer_message_ids"].append(explainer_message.id)

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        chat_id = update.effective_chat.id
        self._save_test_answers(chat_id, self.conversation_name, context.user_data)
        await self.cancel_extension(update, context)
        # result = await frontend.telegram_bot.src.app.utils.abort_test(update, context)
        explainer_message = await context.bot.send_message(
            chat_id,
            "Тест закончен преждевременно.\n\n"
            "Если столкнулся с ошибкой - пожалуйста, обратись в поддержку.",
        )
        context.user_data["explainer_message_ids"].append(explainer_message.id)

        return ConversationHandler.END
