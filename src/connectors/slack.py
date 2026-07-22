import os
from typing import Any, Dict, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackConnector:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        self.client = WebClient(token=self.token)

    def post_message(self, *, channel: str, blocks: list[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            response = self.client.chat_postMessage(channel=channel, blocks=blocks)
            return response.data
        except SlackApiError as exc:
            raise RuntimeError(f"Slack post failed: {exc.response['error']}")
