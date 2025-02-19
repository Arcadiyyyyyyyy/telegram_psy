import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

import arrow
from loguru import logger
from pymongo import MongoClient
from pymongo.database import Database

import frontend.shared.src.models


class Connector:
    _instance: Optional["Connector"] = None
    __initialized: bool

    db: Database[Any]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Connector, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        if self.__initialized:
            return
        self.__initialized = True

        self.db = MongoClient(os.environ["MONGO_URI"])["psy_kopatych_user_facing_bot"]
        logger.info("Connected to the mongodb")


class Collection:
    collection: str
    db: Database[Any]

    def read(
        self, _filter: dict[str, Any] = {}, _sort: dict[str, Any] = {}
    ) -> Generator[Any, Any, None]:
        logger.trace("Started reading " + self.__class__.__name__ + " documents")
        yield from self.db[self.collection].find(_filter).sort(_sort)
        logger.trace("Finished reading " + self.__class__.__name__ + " documents")

    def read_one(self, _filter: dict[str, Any]) -> dict[str, Any] | None:
        return self.db[self.collection].find_one(_filter)

    def insert_one(self, document_to_insert: dict[str, Any]):
        if document_to_insert.get("created_at") is not None:
            del document_to_insert["created_at"]
        if document_to_insert.get("updated_at") is not None:
            del document_to_insert["updated_at"]
        document = document_to_insert | {
            "created_at": arrow.utcnow().datetime,
            "updated_at": arrow.utcnow().datetime,
        }

        result = self.db[self.collection].insert_one(document)
        logger.debug(
            f"Inserted document with id {result.inserted_id} "
            f"to {self.__class__.__name__}"
        )
        return result

    def insert_many(self, documents_to_insert: Iterable[dict[str, Any]]):
        docs_to_input: list[dict[str, Any]] = []
        for document in documents_to_insert:
            if document.get("created_at") is not None:
                del document["created_at"]
            if document.get("updated_at") is not None:
                del document["updated_at"]
            document_to_insert = document | {
                "created_at": arrow.utcnow().datetime,
                "updated_at": arrow.utcnow().datetime,
            }
            docs_to_input.append(document_to_insert)

        result = self.db[self.collection].insert_many(docs_to_input)
        logger.debug(
            f"Inserted documents with ids {result.inserted_ids} "
            f"to {self.__class__.__name__}"
        )
        return result

    def update(self, _filter: dict[str, Any], values_to_update: dict[str, Any]):
        document = values_to_update | {"updated_at": arrow.utcnow().datetime}

        result = self.db[self.collection].update_one(_filter, {"$set": document})
        logger.debug(
            f"Updated document with filter {_filter} from {self.__class__.__name__}"
        )
        return result

    def delete(self, _filter: dict[str, Any] = {}):
        result = self.db[self.collection].delete_many(_filter)
        logger.debug(
            "Deleted document with filter "
            + f"{_filter}"
            + " from "
            + self.__class__.__name__
        )
        return result

    def watch(self) -> Generator[Any, Any, None]:
        logger.info(
            "Started listening to " + self.__class__.__name__ + " changes stream"
        )
        yield from self.db[self.collection].watch()
        logger.info(
            "Stopped listening to " + self.__class__.__name__ + " changes stream"
        )


def backup(*args: Collection):
    base_folder = f"./backup/{arrow.Arrow.utcnow().format('YYYY-MM-DDTHH:mm:ss')}/"
    Path(base_folder).mkdir(parents=True)
    for collection in args:
        logger.info(f"Started backing up {collection.__class__.__name__}")
        with Path(base_folder + collection.__class__.__name__ + ".json").open(
            "w"
        ) as file:
            data = json.dumps(list(collection.read({}, {"created_at": 1})), default=str)
            file.write(data)
        logger.info(f"Backed up {collection.__class__.__name__}")


class UsersCollection(Collection):
    def __init__(self):
        self.db = Connector().db
        self.collection = "users"

    def create_user(self, user: frontend.shared.src.models.UserModel):
        return self.insert_one(asdict(user))

    def update_user(self, user: frontend.shared.src.models.UserModel):
        return self.update(
            {"chat_id": user.chat_id},
            asdict(user),
        )


class TestsCollection(Collection):
    def __init__(self):
        self.db = Connector().db
        self.collection = "tests"

    def get_iq_questions(
        self,
    ) -> Generator[frontend.shared.src.models.IQTestModel, Any, None]:
        yield from (
            frontend.shared.src.models.IQTestModel(**x)
            for x in self.read({"test_name": "iq"}, {"phase": 1, "test_step": 1})
        )

    def get_atq_questions(
        self,
    ) -> Generator[frontend.shared.src.models.AtqTestModel, Any, None]:
        yield from (
            frontend.shared.src.models.AtqTestModel(**x)
            for x in self.read({"test_name": "atq"}, {"test_step": 1})
        )

    def populate_tests_from_json(self):
        path = Path("tests.json")
        if not path.exists():
            raise EnvironmentError
        with path.open() as file:
            info = json.loads(file.read())
        logger.info("Started updating tests in the database")
        self.delete({})
        self.insert_many(info)
        logger.info("Finished updating tests in the database")


class TestAnswersCollection(Collection):
    def __init__(self):
        self.db = Connector().db
        self.collection = "test_answers"

    def create_test_answer(self, answer: frontend.shared.src.models.TestAnswerModel):
        return self.insert_one(asdict(answer))
