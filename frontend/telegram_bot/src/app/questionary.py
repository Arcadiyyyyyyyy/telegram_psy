from abc import abstractmethod
from typing import Any, Callable, Generator, Optional

import arrow
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import frontend.shared.src.db
import frontend.shared.src.middleware
import frontend.shared.src.models
import frontend.shared.src.utils
import frontend.telegram_bot.src.app.utils


class Conversation:
    _instance: Optional["Conversation"] = None
    __initialized: bool

    conversation_name: str
    # question_preset = (
    #     "Вопрос {current_step} из {total_amount_of_steps}\n\n{question_text}"
    # )
    error_text = (
        "Разработчик этого бота допустил ошибку, которую не должен "
        "был допустить. К сожалению, сдать тест в данный момент нельзя."
        " Пожалуйста, перешлите это сообщение в контакт из команды /help"
    )

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

    @abstractmethod
    async def command_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        pass

    @abstractmethod
    async def _handle_mock_test_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *,
        current_step: int,
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
    ):
        pass

    @abstractmethod
    async def cancel_extension(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        pass

    @abstractmethod
    def generate_command_list(
        self,
    ) -> Generator[tuple[int, Callable[..., Any]], Any, None]:
        pass

    async def command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (
            update.message is None
            or update.message.from_user is None
            or context.user_data is None
        ):
            if update.effective_chat is None:
                return ConversationHandler.END
            await context.bot.send_message(
                update.effective_chat.id,
                self.error_text,
            )
            return ConversationHandler.END
        await frontend.shared.src.middleware.main_handler(update, context)
        chat_id = update.message.chat.id

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
                "К сожалению, тест можно сдавать только единожды. "
                "\n\nПожалуйста, обратитесь к администратору в "
                "/help если столкнулись с ошибкой."
            )
            texts_to_send = frontend.shared.src.utils.split_string(text)
            for t in texts_to_send:
                await context.bot.send_message(chat_id, t)
            return ConversationHandler.END
        context.user_data["started_at"] = arrow.utcnow().datetime

        await frontend.telegram_bot.src.app.utils.notify_test_exit_consequence(
            update, context
        )

        await self.command_extension(update, context)

        return 1

    async def finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.effective_chat is None or context.user_data is None:
            raise ValueError
        context.user_data["finished_at"] = arrow.utcnow().datetime
        chat_id = update.effective_chat.id

        frontend.telegram_bot.src.app.utils.save_test_answers(
            chat_id, self.conversation_name, context.user_data
        )

        await self.finish_extension(update, context)

        text = frontend.shared.src.utils.generate_test_answers_info(
            int(chat_id), self.conversation_name
        )[0]

        texts_to_send = frontend.shared.src.utils.split_string(
            f"Поздравляем! Вы успешно прошли тест, ваши ответы сохранены. \n\n{text}"
        )
        for t in texts_to_send:
            await context.bot.send_message(chat_id, t)
        return ConversationHandler.END

    async def callback_cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        await frontend.shared.src.middleware.main_handler(update, context)
        if update.callback_query is not None:
            await frontend.shared.src.utils.handle_callback(update.callback_query)
        await self.cancel_extension(update, context)
        return await frontend.telegram_bot.src.app.utils.abort_test(
            update, context, self.conversation_name
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await frontend.shared.src.middleware.main_handler(update, context)
        await self.cancel_extension(update, context)
        return await frontend.telegram_bot.src.app.utils.abort_test(
            update, context, self.conversation_name
        )

    async def callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        # await frontend.shared.src.middleware.main_handler(update, context)
        if update.effective_message is None or context.user_data is None:
            raise ValueError
        chat_id, callback = await frontend.shared.src.utils.handle_callback(
            update.callback_query
        )
        if callback == "":
            await context.bot.send_message(
                chat_id,
                self.error_text,
            )
            return ConversationHandler.END

        await self.callback_handler_extension(update, context)

        next_step = await self.handle_test_answer(
            question_texts=self.question_texts,
            update=update,
            context=context,
            callback=callback,
            mock_steps=self.mock_steps,
        )
        try:
            await context.bot.delete_message(chat_id, update.effective_message.id)
        except Exception:
            pass

        return await self.commands[next_step][1](update, context)

    async def handle_test_answer(
        self,
        *,
        question_texts: list[str],
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        callback: str,
        mock_steps: list[dict[str, Any]] | None,
    ) -> int:
        """Returns next command id"""
        if context.user_data is None or mock_steps is None:
            raise ValueError

        split = callback.split("+")
        current_step = int(split[2][4:])
        answer_text = split[3][6:]

        next_question_step = current_step
        try:
            current_test = [
                x for x in mock_steps if int(x["test_step"]) == current_step
            ][0]
        except IndexError:
            current_test = {}

        if int(current_step) == int(current_test.get("test_step", -1)):
            # TODO: if answer is not expected send a message
            if answer_text not in current_test["correct_answer"]:
                await self._handle_mock_test_answer(
                    update, context, current_step=current_step
                )

            return next_question_step

        previous_question_text = question_texts[current_step - 1]
        answers: list[Any] | None = context.user_data.get("answers")
        questions: list[Any] | None = context.user_data.get("questions")
        if answers is None:
            context.user_data["answers"] = []
        del answers
        valid_answers: list[str] = context.user_data["answers"]
        valid_answers.append(answer_text)
        if questions is None:
            context.user_data["questions"] = []
        del questions
        valid_questions: list[str] = context.user_data["questions"]
        valid_questions.append(previous_question_text)

        return next_question_step
