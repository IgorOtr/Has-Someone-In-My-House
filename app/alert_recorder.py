"""Best-effort alert history recording for the webcam monitor.

Persists a durable record (message + saved image path) of every detection
so the owner can recover the history later even if a future WhatsApp
delivery attempt fails or a message is lost/deleted on their phone.
WhatsApp sending itself is not implemented yet.

This reuses the persistence utilities under ``web/`` (``auth_config``,
``db``, ``db_models``, ``alert_service``): those modules have no FastAPI or
HTTP dependency, so they work whether or not the web dashboard process is
running. A failure here (e.g. MySQL unreachable) is logged and never
interrupts the monitoring loop — it only disables alert recording for the
rest of the run.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import sessionmaker

from web.alert_service import create_alert
from web.auth_config import load_auth_config
from web.db import build_engine, build_session_factory, ensure_database_exists, init_models

logger = logging.getLogger(__name__)


class AlertRecorder:
    """Records alerts if a database session factory is available.

    Prefer :meth:`create` in application code; the constructor is exposed
    directly mainly for tests to inject a fake/in-memory session factory.
    """

    def __init__(self, session_factory: Optional[sessionmaker]) -> None:
        self._session_factory = session_factory

    @classmethod
    def create(cls) -> "AlertRecorder":
        """Build a recorder from the shared database configuration.

        If the database cannot be prepared (e.g. MySQL is not running or
        not configured), logs a warning once and returns a recorder that
        silently skips every alert for the rest of the run.
        """
        try:
            auth_settings = load_auth_config()
            ensure_database_exists(auth_settings)
            engine = build_engine(auth_settings.database_url)
            init_models(engine)
            session_factory = build_session_factory(engine)
        except Exception:
            logger.warning(
                "Alert history is disabled: could not prepare the database.",
                exc_info=True,
            )
            return cls(session_factory=None)
        return cls(session_factory=session_factory)

    def record_alert(self, message: str, image_path: Path) -> bool:
        """Persist an alert. Returns True on success, False otherwise.

        Never raises: any failure is logged and treated as non-fatal.
        """
        if self._session_factory is None:
            return False

        session = None
        try:
            session = self._session_factory()
            create_alert(session, message, image_path)
            logger.info("Alert recorded for %s", image_path)
            return True
        except Exception:
            logger.exception("Failed to record alert for %s", image_path)
            return False
        finally:
            if session is not None:
                session.close()
