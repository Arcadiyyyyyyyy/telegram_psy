import base64
import json
import os
from typing import Any

import arrow
import requests
from loguru import logger


class ZOOM:
    account_id = os.environ["ZOOM_ACCOUNT_ID"]
    user_id = os.environ["ZOOM_CLIENT_ID"]
    access_token = os.environ["ZOOM_CLIENT_SECRET"]
    base_url = "https://api.zoom.us/v2/"

    def __init__(self):
        credentials = f"{self.user_id}:{self.access_token}"
        base64_credentials = base64.b64encode(credentials.encode("ascii")).decode(
            "ascii"
        )
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}"

        headers = {
            "Authorization": f"Basic {base64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            access_token: str = data["access_token"]
        else:
            logger.error(f"{response.status_code}, {response.text}")
            raise ValueError

        self.token = access_token

    def _request(self, endpoint: str, method: str, data: dict[str, Any]):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        url = self.base_url + endpoint
        response = requests.request(method, url, headers=headers, data=json.dumps(data))
        if response.status_code == 201:
            logger.info(f"Meeting details: {response.json()}")
        else:
            logger.error(
                f"Failed to create meeting: {response.status_code} {response.text}",
            )

        return response.json()

    def create_meeting(
        self, topic: str, agenda: str, duration: int, start_time: arrow.Arrow
    ):
        meeting_details: dict[str, Any] = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": start_time.isoformat() + "Z",
            "duration": duration,  # Duration in minutes
            "timezone": "UTC",
            "agenda": agenda,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "mute_upon_entry": False,
                "waiting_room": False,
                "registration_type": 1,  # No registration required
            },
        }

        return self._request("users/me/meetings", "POST", meeting_details)
