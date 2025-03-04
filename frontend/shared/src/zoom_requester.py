import json
import os
from typing import Any

import arrow
import requests
from loguru import logger


class ZOOM:
    access_token = "YOUR_ACCESS_TOKEN"
    user_id = os.getenv("ZOOM_USER_ID", "me")

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
        url = f"https://api.zoom.us/v2/users/{self.user_id}/meetings"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, data=json.dumps(meeting_details))

        if response.status_code == 201:
            logger.info("Meeting details:", response.json())
        else:
            logger.error(
                "Failed to create meeting:", response.status_code, response.text
            )

        return response.json()
