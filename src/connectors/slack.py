import os
from typing import Any, Dict, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.util.backoff import retry_with_backoff


def _is_retryable_slack_error(exc: Exception) -> bool:
    if not isinstance(exc, SlackApiError):
        return False
    status = exc.response.status_code
    return status == 429 or status >= 500


class SlackConnector:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        self.client = WebClient(token=self.token)

    def post_message(self, *, channel: str, blocks: list[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            response = retry_with_backoff(
                lambda: self.client.chat_postMessage(channel=channel, blocks=blocks),
                should_retry=_is_retryable_slack_error,
            )
            return response.data
        except SlackApiError as exc:
            raise RuntimeError(f"Slack post failed: {exc.response['error']}")
