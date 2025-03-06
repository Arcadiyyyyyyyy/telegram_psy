import csv
from pathlib import Path


class FileManager:
    def __init__(self, cache_folder: str = "./cache"):
        self.cache_folder = cache_folder

        if not Path(self.cache_folder + "/test_answers").exists():
            Path(self.cache_folder + "/test_answers").mkdir(parents=True)

    def write_cache_test_answers(
        self, chat_id: int, test_name: str, answers: list[list[str | int]]
    ):
        with Path(f"{self.cache_folder}/test_answers/{chat_id}+{test_name}.csv").open(
            "w"
        ) as file:
            writer = csv.writer(file)
            writer.writerows(answers)

    def read_cache_test_answers(self, chat_id: int, test_name: str):
        return f"{self.cache_folder}/test_answers/{chat_id}+{test_name}.csv"
        # with Path(f"{self.cache_folder}/test_answers/{chat_id}+{test_name}.csv").open(
        #     "rb"
        # ) as file:
        #     return file.read()
