"""Angel One SmartAPI session manager.

Handles login (API key + client code + MPIN + runtime TOTP), token persistence,
automatic token refresh, and re-login when the session expires (Angel sessions
die after market hours / inactivity).

Verified against smartapi-python 1.5.3:
    from SmartApi import SmartConnect
    obj = SmartConnect(api_key=API_KEY)
    data = obj.generateSession(clientCode, password, totp)   # password == MPIN
    obj.generateToken(refresh_token)                          # renew JWT
    obj.getProfile(refreshToken)
    obj.getfeedToken()                                        # feed token for websocket
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import pyotp

from ..config import settings
from ..utils.backoff import retry_with_backoff

logger = logging.getLogger("angel.session")

# The SmartApi SDK is only imported lazily so the rest of the app (and tests)
# can import this module even before the dependency is installed.
try:  # pragma: no cover - import guard
    from SmartApi import SmartConnect  # type: ignore
except Exception as _exc:  # noqa: BLE001
    SmartConnect = None  # type: ignore
    _IMPORT_ERROR = _exc
else:
    _IMPORT_ERROR = None


class AngelAuthError(RuntimeError):
    """Raised when login / token generation fails."""


class AngelSession:
    """Thread-safe singleton wrapping a SmartConnect client.

    Other services call :meth:`client` to get a logged-in SmartConnect instance;
    the session transparently logs in on first use and refreshes/re-logs-in when
    the JWT is near expiry or a call reports an auth failure.
    """

    # Angel JWTs are valid for several hours; refresh proactively well before.
    _REFRESH_AFTER = timedelta(hours=5)

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._smart: Any = None
        self.jwt_token: str | None = None
        self.refresh_token: str | None = None
        self.feed_token: str | None = None
        self._logged_in_at: datetime | None = None
        self._profile: dict | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @property
    def is_authenticated(self) -> bool:
        return bool(self._smart and self.jwt_token)

    def status(self) -> dict:
        """Non-secret status for the frontend / health endpoint."""
        return {
            "authenticated": self.is_authenticated,
            "logged_in_at": self._logged_in_at.isoformat() if self._logged_in_at else None,
            "client_code": self._profile.get("clientcode") if self._profile else None,
            "name": self._profile.get("name") if self._profile else None,
            "credentials_present": settings.angel_credentials_present,
        }

    def client(self) -> Any:
        """Return a logged-in SmartConnect, logging in / refreshing as needed."""
        with self._lock:
            if not self.is_authenticated:
                self.login()
            elif self._needs_refresh():
                try:
                    self.refresh()
                except AngelAuthError:
                    logger.warning("Token refresh failed; performing full re-login")
                    self.login()
            return self._smart

    def login(self) -> dict:
        """Perform a fresh login using credentials + a freshly generated TOTP."""
        if SmartConnect is None:
            raise AngelAuthError(
                f"smartapi-python is not installed: {_IMPORT_ERROR}. "
                "Run `pip install -r backend/requirements.txt`."
            )
        if not settings.angel_credentials_present:
            raise AngelAuthError(
                "Angel One credentials are missing. Set ANGEL_API_KEY, "
                "ANGEL_CLIENT_CODE, ANGEL_MPIN and ANGEL_TOTP_SECRET in .env."
            )

        with self._lock:
            totp = self._current_totp()
            smart = SmartConnect(api_key=settings.angel_api_key)

            def _do_login() -> dict:
                # generateSession(clientCode, password, totp) — password is the MPIN.
                return smart.generateSession(
                    settings.angel_client_code, settings.angel_mpin, totp
                )

            data = retry_with_backoff(_do_login, label="generateSession", retries=2)
            if not data or not data.get("status"):
                msg = (data or {}).get("message", "unknown error")
                raise AngelAuthError(f"Angel login failed: {msg}")

            tokens = data["data"]
            self._smart = smart
            self.jwt_token = tokens.get("jwtToken")
            self.refresh_token = tokens.get("refreshToken")
            # feedToken comes back in the session payload; fall back to the getter.
            self.feed_token = tokens.get("feedToken") or self._safe_feed_token(smart)
            self._logged_in_at = datetime.utcnow()
            self._load_profile()
            logger.info(
                "Angel One login OK for client %s",
                self._profile.get("clientcode") if self._profile else "?",
            )
            return self.status()

    def refresh(self) -> None:
        """Renew the JWT using the stored refresh token."""
        if not self._smart or not self.refresh_token:
            raise AngelAuthError("Cannot refresh without an existing session")
        with self._lock:
            def _do_refresh() -> dict:
                return self._smart.generateToken(self.refresh_token)

            data = retry_with_backoff(_do_refresh, label="generateToken", retries=2)
            if not data or not data.get("status"):
                raise AngelAuthError(f"Token refresh failed: {(data or {}).get('message')}")
            tokens = data["data"]
            self.jwt_token = tokens.get("jwtToken", self.jwt_token)
            self.refresh_token = tokens.get("refreshToken", self.refresh_token)
            self.feed_token = tokens.get("feedToken") or self.feed_token
            self._logged_in_at = datetime.utcnow()
            logger.info("Angel One token refreshed")

    def logout(self) -> None:
        with self._lock:
            try:
                if self._smart:
                    self._smart.terminateSession(settings.angel_client_code)
            except Exception as exc:  # noqa: BLE001
                logger.debug("terminateSession error (ignored): %s", exc)
            self._smart = None
            self.jwt_token = self.refresh_token = self.feed_token = None
            self._logged_in_at = None
            self._profile = None

    def get_feed_token(self) -> str:
        """Feed token required by SmartWebSocketV2."""
        self.client()  # ensure logged in
        if not self.feed_token:
            raise AngelAuthError("No feed token available")
        return self.feed_token

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _current_totp(self) -> str:
        try:
            return pyotp.TOTP(settings.angel_totp_secret).now()
        except Exception as exc:  # noqa: BLE001
            raise AngelAuthError(
                f"Failed to generate TOTP — is ANGEL_TOTP_SECRET a valid base32 secret? {exc}"
            ) from exc

    def _needs_refresh(self) -> bool:
        if not self._logged_in_at:
            return True
        return datetime.utcnow() - self._logged_in_at > self._REFRESH_AFTER

    @staticmethod
    def _safe_feed_token(smart: Any) -> str | None:
        for getter in ("getfeedToken", "getFeedToken"):
            fn = getattr(smart, getter, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:  # noqa: BLE001
                    continue
        return None

    def _load_profile(self) -> None:
        try:
            data = self._smart.getProfile(self.refresh_token)
            if data and data.get("status"):
                self._profile = data["data"]
        except Exception as exc:  # noqa: BLE001
            logger.debug("getProfile failed (non-fatal): %s", exc)
            self._profile = None


# Module-level singleton used throughout the app.
angel_session = AngelSession()
