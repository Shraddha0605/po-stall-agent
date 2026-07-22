from __future__ import annotations

import base64
import email
import os
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.compose']


def _get_oauth_credentials(credentials_path: str, token_path: str) -> Credentials:
    creds = None
    if os.path.exists(token_path):
        from google.oauth2.credentials import Credentials as OAuthCredentials

        creds = OAuthCredentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w', encoding='utf-8') as token_file:
            token_file.write(creds.to_json())
    return creds


def _parse_body(payload: Dict[str, Any]) -> str:
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8', errors='replace')
        return ''
    if payload.get('mimeType', '').startswith('multipart'):
        for part in payload.get('parts', []):
            body = _parse_body(part)
            if body:
                return body
    return ''


class GmailConnector:
    def __init__(self, auth_mode: Optional[str] = None):
        self.auth_mode = auth_mode or os.getenv('GMAIL_AUTH_MODE', 'service')
        self.user_id = os.getenv('GMAIL_IMPERSONATE_EMAIL')
        self.service = None
        self.service_account_creds = None
        if self.auth_mode != 'fixture':
            self._initialize_service()

    def _initialize_service(self):
        if self.auth_mode == 'service':
            sa_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
            if not sa_file:
                raise ValueError('GOOGLE_SERVICE_ACCOUNT_FILE is required for service auth')
            self.service_account_creds = Credentials.from_service_account_file(sa_file, scopes=SCOPES)
        elif self.auth_mode == 'oauth':
            credentials_path = os.getenv('GMAIL_OAUTH_CREDENTIALS')
            token_path = os.getenv('GMAIL_OAUTH_TOKEN')
            if not credentials_path or not token_path:
                raise ValueError('GMAIL_OAUTH_CREDENTIALS and GMAIL_OAUTH_TOKEN are required for oauth auth')
            creds = _get_oauth_credentials(credentials_path, token_path)
            self.service = build('gmail', 'v1', credentials=creds)
        else:
            raise ValueError(f'Unsupported GMAIL_AUTH_MODE={self.auth_mode}')

    def _service_for_user(self, user_id: Optional[str]):
        if self.auth_mode == 'fixture':
            return None
        if self.auth_mode == 'service':
            if not user_id:
                raise ValueError('user_id is required for service account impersonation')
            delegated = self.service_account_creds.with_subject(user_id)
            return build('gmail', 'v1', credentials=delegated)
        return self.service

    def list_messages(self, *, user_id: Optional[str] = None, query: Optional[str] = None, max_results: int = 50) -> List[Dict[str, Any]]:
        if self.auth_mode == 'fixture':
            return []
        user_id = user_id or self.user_id
        service = self._service_for_user(user_id)
        collected: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        remaining = max_results
        while True:
            response = service.users().messages().list(
                userId=user_id,
                q=query,
                maxResults=min(remaining, 100),
                pageToken=page_token,
            ).execute()
            collected.extend(response.get('messages', []))
            if not response.get('nextPageToken') or len(collected) >= max_results:
                break
            page_token = response.get('nextPageToken')
            remaining = max_results - len(collected)
        return collected

    def get_message(self, user_id: Optional[str], message_id: str) -> Dict[str, Any]:
        if self.auth_mode == 'fixture':
            return {'id': message_id, 'subject': '', 'from': '', 'body': '', 'threadId': message_id, 'internalDate': '0'}
        user_id = user_id or self.user_id
        service = self._service_for_user(user_id)
        message = service.users().messages().get(userId=user_id, id=message_id, format='full').execute()
        headers = {header['name']: header['value'] for header in message.get('payload', {}).get('headers', [])}
        body = _parse_body(message.get('payload', {}))
        sender_email = parseaddr(headers.get('From', ''))[1] or headers.get('From', '')
        return {
            'id': message.get('id'),
            'threadId': message.get('threadId'),
            'subject': headers.get('Subject', ''),
            'from': sender_email,
            'body': body,
            'internalDate': message.get('internalDate', '0'),
        }

    def create_draft(
        self,
        *,
        user_id: Optional[str],
        thread_id: Optional[str],
        in_reply_to: str,
        references: str,
        body: str,
        subject: str,
    ) -> Dict[str, Any]:
        if self.auth_mode == 'fixture':
            return {'id': f'draft-{thread_id or in_reply_to}', 'threadId': thread_id or in_reply_to, 'body': body, 'subject': subject}
        user_id = user_id or self.user_id
        service = self._service_for_user(user_id)
        message = email.message.EmailMessage()
        message['Subject'] = f'Re: {subject}'
        message['In-Reply-To'] = in_reply_to
        message['References'] = references
        message['From'] = user_id
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        draft_message = {'raw': raw}
        if thread_id:
            draft_message['threadId'] = thread_id
        draft_body = {'message': draft_message}
        draft = service.users().drafts().create(userId=user_id, body=draft_body).execute()
        return draft
