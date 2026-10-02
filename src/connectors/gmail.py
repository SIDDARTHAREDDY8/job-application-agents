"""Send email through Gmail, on any computer.

Two modes (env GMAIL_MODE):

  smtp  - Plain SMTP with a Gmail App Password. Simplest, no OAuth dance.
          Needs: GMAIL_ADDRESS, GMAIL_APP_PASSWORD
          (Google Account -> Security -> 2-Step Verification -> App passwords)

  api   - Gmail API with OAuth 2.0 desktop flow.
          Needs: GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in env,
                 or a credentials.json in the project root.
          First run opens a browser to authorize; the token is cached at
          state/gmail_token.json so later runs are headless.

Both modes support attachments (your tailored resume PDF).
"""

from __future__ import annotations
import base64
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from typing import Any


class GmailSender:
    def __init__(
        self,
        mode: str = "smtp",
        address: str | None = None,
        app_password: str | None = None,
        token_path: str = "state/gmail_token.json",
        credentials_path: str = "credentials.json",
    ):
        self.mode = (mode or "smtp").lower().strip()
        self.address = address or os.getenv("GMAIL_ADDRESS", "")
        self.app_password = app_password or os.getenv("GMAIL_APP_PASSWORD", "")
        self.token_path = token_path
        self.credentials_path = credentials_path
        if self.mode not in ("smtp", "api"):
            raise ValueError("GMAIL_MODE must be 'smtp' or 'api'")

    # ------------------------------------------------------------------ public
    def send(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        cc: str | None = None,
    ) -> dict[str, Any]:
        """Send one email. Returns {'message_id': ...} on success."""
        if not to or "@" not in to:
            raise ValueError(f"Refusing to send: bad recipient '{to}'")
        if self.mode == "smtp":
            return self._send_smtp(to, subject, body, attachments or [], cc)
        return self._send_api(to, subject, body, attachments or [], cc)

    # ------------------------------------------------------------------ smtp
    def _send_smtp(self, to, subject, body, attachments, cc) -> dict[str, Any]:
        if not self.address or not self.app_password:
            raise RuntimeError(
                "SMTP mode needs GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env. "
                "Create an App Password at Google Account -> Security -> App passwords."
            )
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.set_content(body)
        for path in attachments:
            self._attach(msg, path)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(self.address, self.app_password)
            s.send_message(msg)
        # smtplib gives no id; the Sent-folder sweep is the verification step.
        return {"message_id": f"smtp:{to}:{subject[:40]}", "mode": "smtp"}

    # ------------------------------------------------------------------ api
    def _send_api(self, to, subject, body, attachments, cc) -> dict[str, Any]:
        service = self._api_service()
        msg = EmailMessage()
        msg["From"] = self.address or "me"
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.set_content(body)
        for path in attachments:
            self._attach(msg, path)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"message_id": sent.get("id", ""), "mode": "api"}

    def _api_service(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as e:
            raise ImportError(
                "Gmail API mode needs: pip install google-api-python-client google-auth-oauthlib"
            ) from e

        scopes = ["https://www.googleapis.com/auth/gmail.send"]
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(self.credentials_path):
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, scopes)
                else:
                    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
                    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
                    if not client_id or not client_secret:
                        raise RuntimeError(
                            "Gmail API mode needs GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET "
                            "in .env, or a credentials.json (Google Cloud -> APIs & Services "
                            "-> Credentials -> OAuth client ID, Desktop app)."
                        )
                    flow = InstalledAppFlow.from_client_config(
                        {
                            "installed": {
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "redirect_uris": ["http://localhost"],
                                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                "token_uri": "https://oauth2.googleapis.com/token",
                            }
                        },
                        scopes,
                    )
                creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(self.token_path) or ".", exist_ok=True)
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())
        return build("gmail", "v1", credentials=creds)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _attach(msg: EmailMessage, path: str) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Attachment not found: {path}")
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))


def from_env() -> GmailSender:
    """Build a GmailSender from .env (GMAIL_MODE, GMAIL_ADDRESS, ...)."""
    return GmailSender(mode=os.getenv("GMAIL_MODE", "smtp"))
