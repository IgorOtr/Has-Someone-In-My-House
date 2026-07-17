# Imagem do dashboard web (web/server.py) — inclui a inferência do YOLO11n,
# usada tanto pelo histórico/alertas quanto pelo monitoramento via webcam do
# navegador (web/webcam_session.py). NÃO roda o monitor físico (app/main.py):
# isso continua sendo executado localmente, na máquina que tem a webcam.
FROM python:3.11-slim

# libGL/libglib: dependências de sistema exigidas pelo opencv-python mesmo
# sem exibir nenhuma janela (o dashboard nunca chama cv2.imshow).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# `pip install torch` sozinho resolve uma wheel com suporte a CUDA/GPU por
# padrão — inútil e pesado (vários GB a mais) numa VPS sem GPU, onde a
# inferência já cai para CPU de qualquer forma (ver app/detector.py). Instala
# a build CPU-only primeiro; o resto de requirements.txt já encontra essa
# versão satisfeita e não reinstala.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Baixa os pesos do YOLO11n durante o build, não na primeira requisição —
# evita que a primeira sessão de webcam pague esse custo (ou dependa de
# internet) em produção.
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

# Garante que a pasta de detecções exista mesmo antes de montar o volume.
RUN mkdir -p detections

EXPOSE 8000

# 0.0.0.0 (não 127.0.0.1) para ficar acessível de fora do container.
# Um único worker: o app guarda estado compartilhado em memória do processo
# (rate limiter, gerenciador do monitor, lock do modelo) que não sobrevive
# a múltiplos workers/réplicas sem trabalho adicional.
CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
