"""Codifica uma imagem de detecção salva em base64, para embutir em payloads de API.

Usado por ``web.whatsapp_client`` para enviar a imagem embutida no corpo
da requisição (os servidores da Z-API não conseguem ler um caminho no
sistema de arquivos local do monitor, então um caminho puro não serve).
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Union

_DEFAULT_MIME_TYPE = "image/jpeg"


class ImageEncodingError(Exception):
    """Levantada quando um arquivo de imagem não pode ser lido ou codificado."""


def encode_image_as_data_uri(image_path: Union[str, Path]) -> str:
    """Lê um arquivo de imagem e o retorna como uma ``data:`` URI em base64.

    Retorna uma string ``data:<mime-type>;base64,<...>`` — o formato
    embutido esperado sempre que não há uma URL pública disponível.

    Raises:
        ImageEncodingError: Se o arquivo não puder ser lido.
    """
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or _DEFAULT_MIME_TYPE

    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise ImageEncodingError(f"Could not read image file {path}: {exc}") from exc

    encoded = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
