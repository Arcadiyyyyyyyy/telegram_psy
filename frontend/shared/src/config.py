from dataclasses import dataclass
from typing import Any, Callable, Iterable

from telegram.ext._handlers.basehandler import BaseHandler


@dataclass
class Command:
    command: str
    description: str
    callback: Callable[..., Any] | None


@dataclass
class ConversationHandlerConfig:
    command: str
    description: str
    entrypoint: Iterable[BaseHandler[Any, Any, Any]]
    stages: dict[int, Iterable[BaseHandler[Any, Any, Any]]]
    fallback: Iterable[BaseHandler[Any, Any, Any]]
    group: int = 1
