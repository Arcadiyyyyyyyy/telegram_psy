import datetime

import arrow
import pydantic


@pydantic.dataclasses.dataclass()
class UserModel:
    chat_id: int
    first_name: str
    last_name: str | None
    username: str | None
    created_at: datetime.datetime = arrow.utcnow().datetime
    updated_at: datetime.datetime = arrow.utcnow().datetime


@pydantic.dataclasses.dataclass()
class AtqTestModel:
    text: str
    test_name: str
    test_step: int
    created_at: datetime.datetime = arrow.utcnow().datetime
    updated_at: datetime.datetime = arrow.utcnow().datetime


@pydantic.dataclasses.dataclass()
class IQTestModel:
    text: str
    test_name: str
    test_step: int
    media_location: str
    is_main_phase_message: bool
    phase: int
    seconds_to_pass_the_phase: int | None
    created_at: datetime.datetime = arrow.utcnow().datetime
    updated_at: datetime.datetime = arrow.utcnow().datetime


@pydantic.dataclasses.dataclass()
class TestAnswerModel:
    chat_id: int
    test_name: str
    answers: list[str]
    questions: list[str]
    started_at: datetime.datetime
    finished_at: datetime.datetime
    created_at: datetime.datetime = arrow.utcnow().datetime
    updated_at: datetime.datetime = arrow.utcnow().datetime
