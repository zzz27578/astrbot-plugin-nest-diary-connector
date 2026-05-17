from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from starlette.responses import RedirectResponse


@dataclass
class WebSessionAuth:
    admin_password: str
    session_secret: str

    def create_session_token(self) -> str:
        nonce = secrets.token_urlsafe(24)
        signature = self._sign(nonce)
        return f"{nonce}.{signature}"

    def verify_password(self, password: str) -> bool:
        if not self.admin_password:
            return False
        return hmac.compare_digest(password, self.admin_password)

    def verify_session(self, token: str | None) -> bool:
        if not token or "." not in token:
            return False
        nonce, signature = token.rsplit(".", 1)
        return hmac.compare_digest(signature, self._sign(nonce))

    def redirect_if_missing(self, token: str | None):
        if not self.verify_session(token):
            return RedirectResponse("/login", status_code=303)
        return None

    def _sign(self, nonce: str) -> str:
        return hmac.new(
            self.session_secret.encode("utf-8"),
            nonce.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
