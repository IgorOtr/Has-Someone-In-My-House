"""Registro de alertas e envio por WhatsApp para o monitor, ambos best-effort.

Persiste um registro durável (mensagem + caminho da imagem salva) de cada
detecção, para que o proprietário consiga recuperar o histórico depois,
mesmo que uma tentativa de envio pelo WhatsApp falhe ou a mensagem se
perca/seja apagada no celular dele. Logo após registrar, também tenta
enviar o alerta via WhatsApp (Z-API) e marca ``sent`` em caso de sucesso.

Este módulo reaproveita utilitários de persistência/envio do pacote
``web/`` (config de auth, banco, serviços de alerta/auth, cliente do
WhatsApp): esses módulos não dependem do FastAPI, então funcionam com ou
sem o processo do dashboard rodando. Qualquer falha aqui (MySQL fora do
ar, Z-API mal configurado ou indisponível) é logada e nunca interrompe o
loop de monitoramento — registrar e enviar são, cada um, best-effort de
forma independente.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from web.alert_service import create_alert, mark_alert_sent
from web.auth_config import load_auth_config
from web.auth_service import get_notification_phone_number
from web.db import (
    build_engine,
    build_session_factory,
    ensure_database_exists,
    ensure_schema_migrations,
    init_models,
)
from web.whatsapp_client import WhatsAppSendError, send_whatsapp_image
from web.whatsapp_config import WhatsAppConfig, load_whatsapp_config

logger = logging.getLogger(__name__)


class AlertRecorder:
    """Registra alertas e tenta o envio por WhatsApp para cada um deles.

    Prefira :meth:`create` no código da aplicação; o construtor fica
    exposto diretamente principalmente para os testes injetarem fakes.
    """

    def __init__(
        self,
        session_factory: Optional[sessionmaker],
        whatsapp_config: Optional[WhatsAppConfig] = None,
    ) -> None:
        self._session_factory = session_factory
        self._whatsapp_config = whatsapp_config

    @classmethod
    def create(cls) -> "AlertRecorder":
        """Monta um recorder a partir da configuração compartilhada de banco e Z-API.

        Se o banco não puder ser preparado (ex.: MySQL fora do ar ou não
        configurado), loga um aviso uma vez e retorna um recorder que
        ignora silenciosamente todo alerta pelo resto da execução. Se só a
        configuração do Z-API estiver ausente/inválida, o histórico de
        alertas continua funcionando — o que fica desativado é só o envio
        pelo WhatsApp.
        """
        try:
            auth_settings = load_auth_config()
            ensure_database_exists(auth_settings)
            engine = build_engine(auth_settings.database_url)
            init_models(engine)
            ensure_schema_migrations(engine)
            session_factory = build_session_factory(engine)
        except Exception:
            logger.warning(
                "Alert history is disabled: could not prepare the database.",
                exc_info=True,
            )
            return cls(session_factory=None, whatsapp_config=None)

        try:
            whatsapp_config = load_whatsapp_config()
        except Exception:
            # Falta de config do Z-API não deve derrubar o histórico de alertas.
            logger.warning(
                "WhatsApp delivery is disabled: missing or invalid Z-API configuration.",
                exc_info=True,
            )
            whatsapp_config = None

        return cls(session_factory=session_factory, whatsapp_config=whatsapp_config)

    def record_alert(self, message: str, image_path: Path) -> bool:
        """Persiste um alerta e tenta enviá-lo pelo WhatsApp.

        Retorna True se o alerta foi persistido (independente da tentativa
        de envio pelo WhatsApp ter dado certo). Nunca levanta exceção:
        qualquer falha é logada e tratada como não-fatal.
        """
        if self._session_factory is None:
            return False

        session = None
        try:
            session = self._session_factory()
            alert = create_alert(session, message, image_path)
            logger.info("Alert recorded for %s", image_path)
            self._try_send_whatsapp(session, alert.id, message, image_path)
            return True
        except Exception:
            logger.exception("Failed to record alert for %s", image_path)
            return False
        finally:
            if session is not None:
                session.close()

    def _try_send_whatsapp(
        self, session: Session, alert_id: int, message: str, image_path: Path
    ) -> None:
        if self._whatsapp_config is None:
            return

        phone_number = get_notification_phone_number(session)
        if phone_number is None:
            logger.info(
                "No user has a phone number configured; skipping WhatsApp delivery for %s",
                image_path,
            )
            return

        try:
            send_whatsapp_image(self._whatsapp_config, phone_number, image_path, message)
        except WhatsAppSendError:
            logger.warning(
                "Failed to send WhatsApp alert for %s", image_path, exc_info=True
            )
            return

        mark_alert_sent(session, alert_id)
        logger.info("WhatsApp alert sent for %s", image_path)
