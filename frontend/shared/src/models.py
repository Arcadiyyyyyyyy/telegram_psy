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
    test_results: dict[str, str]
    started_at: datetime.datetime
    finished_at: datetime.datetime
    created_at: datetime.datetime = arrow.utcnow().datetime
    updated_at: datetime.datetime = arrow.utcnow().datetime


@pydantic.dataclasses.dataclass()
class TimeSlotConfirmations:
    by_gleb: bool | None
    by_kopatych: bool | None
    by_irina: bool | None


@pydantic.dataclasses.dataclass()
class TimeSlotBaseModel:
    time: datetime.datetime
    occupation_reason: str
    chat_id: int


@pydantic.dataclasses.dataclass()
class TimeBookingModel(TimeSlotBaseModel):
    confirmations: TimeSlotConfirmations
    meeting_link: str | None
    notify_user_at: list[datetime.datetime]


@pydantic.dataclasses.dataclass()
class CallbackValidationOutput:
    split: list[str]
    current_step: int
    answer_text: str
    chat_id: int
    callback: str
