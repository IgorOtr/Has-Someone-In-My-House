"""Configuração para enviar alertas por WhatsApp via a API HTTP da Z-API.

Mantida separada de ``web/auth_config.py`` porque essas opções só são
relevantes para o envio pelo WhatsApp, não para o banco ou a auth do
dashboard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from dotenv import load_dotenv


class WhatsAppConfigError(Exception):
    """Levantada quando um valor obrigatório da configuração da Z-API está ausente."""


@dataclass(frozen=True)
class WhatsAppConfig:
    instance_id: str
    token: str
    client_token: str

    @property
    def send_image_url(self) -> str:
        return f"https://api.z-api.io/instances/{self.instance_id}/token/{self.token}/send-image"


def _get_required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise WhatsAppConfigError(f"{key} is required to send WhatsApp alerts.")
    return value


def load_whatsapp_config(env: Optional[Mapping[str, str]] = None) -> WhatsAppConfig:
    """Carrega as credenciais da Z-API usadas para enviar alertas por WhatsApp.

    Args:
        env: Mapeamento opcional de onde ler os valores. Por padrão usa
            ``os.environ`` após carregar um arquivo ``.env``, principalmente
            para os testes injetarem valores sem depender de variáveis de
            ambiente reais.

    Raises:
        WhatsAppConfigError: Se ``ZAPI_INSTANCE_ID``, ``ZAPI_TOKEN`` ou
            ``ZAPI_CLIENT_TOKEN`` estiver ausente ou vazio.
    """
    if env is None:
        load_dotenv()
        env = os.environ

    return WhatsAppConfig(
        instance_id=_get_required(env, "ZAPI_INSTANCE_ID"),
        token=_get_required(env, "ZAPI_TOKEN"),
        client_token=_get_required(env, "ZAPI_CLIENT_TOKEN"),
    )
