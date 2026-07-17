"""Envia mensagens de imagem pelo WhatsApp via a API HTTP da Z-API.

https://www.z-api.io/ — ``POST /instances/{instanceId}/token/{token}/send-image``
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import httpx

from web.image_encoder import ImageEncodingError, encode_image_as_data_uri
from web.whatsapp_config import WhatsAppConfig

# Limita quanto tempo uma tentativa de envio pode bloquear quem chamou (o
# loop principal do monitor chama isso de forma síncrona) se a Z-API
# estiver lenta ou fora do ar.
_REQUEST_TIMEOUT_SECONDS = 10.0


class WhatsAppSendError(Exception):
    """Levantada quando a imagem não pode ser lida, a requisição à Z-API
    falha, ou ela não responde com HTTP 200."""


def send_whatsapp_image(
    config: WhatsAppConfig, phone: str, image_path: Union[str, Path], caption: str
) -> None:
    """Envia uma mensagem de imagem pelo WhatsApp via Z-API.

    ``image_path`` é lida do disco e enviada embutida como uma ``data:``
    URI em base64 no campo "image" — os servidores da Z-API não têm
    acesso a um caminho no sistema de arquivos local do monitor.

    Raises:
        WhatsAppSendError: Se o arquivo de imagem não puder ser lido, a
            requisição não puder ser feita (erro de rede, timeout), ou a
            Z-API responder com um status diferente de 200.
    """
    try:
        encoded_image = encode_image_as_data_uri(image_path)
    except ImageEncodingError as exc:
        raise WhatsAppSendError(str(exc)) from exc

    headers = {
        "Client-Token": config.client_token,
        "Content-Type": "application/json",
    }
    payload = {
        "phone": phone,
        "image": encoded_image,
        "caption": caption,
    }

    try:
        response = httpx.post(
            config.send_image_url,
            json=payload,
            headers=headers,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise WhatsAppSendError(f"Request to Z-API failed: {exc}") from exc

    if response.status_code != 200:
        raise WhatsAppSendError(
            f"Z-API returned status {response.status_code}: {response.text}"
        )
