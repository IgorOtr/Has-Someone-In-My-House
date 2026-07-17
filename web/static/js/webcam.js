const CAPTURE_INTERVAL_MS = 700;
const JPEG_QUALITY = 0.8;

const state = {
  running: false,
  mediaStream: null,
  socket: null,
  captureIntervalId: null,
};

const video = document.getElementById("preview");
const placeholder = document.getElementById("preview-placeholder");
const canvas = document.getElementById("capture-canvas");
const toggleButton = document.getElementById("toggle-btn");
const connectionStatus = document.getElementById("connection-status");
const errorMessage = document.getElementById("error-message");

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.classList.remove("hidden");
}

function clearError() {
  errorMessage.classList.add("hidden");
}

function renderStatusCards(payload) {
  const cards = [
    { label: "Status", value: payload.status },
    { label: "Pessoas detectadas", value: payload.person_count },
    { label: "Cooldown", value: `${Math.round(payload.cooldown_remaining)}s` },
  ];

  document.getElementById("status-cards").innerHTML = cards
    .map(
      (card) => `
        <div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3">
          <p class="text-xs text-gray-500 uppercase tracking-wide">${card.label}</p>
          <p class="text-lg font-semibold mt-1">${card.value}</p>
        </div>`
    )
    .join("");
}

function buildWebSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/webcam`;
}

function captureAndSendFrame() {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) return;
  if (!video.videoWidth || !video.videoHeight) return;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(
    (blob) => {
      if (blob && state.socket && state.socket.readyState === WebSocket.OPEN) {
        state.socket.send(blob);
      }
    },
    "image/jpeg",
    JPEG_QUALITY
  );
}

async function startCamera() {
  clearError();
  toggleButton.disabled = true;

  try {
    state.mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720 },
      audio: false,
    });
  } catch (error) {
    showError("Não foi possível acessar a câmera: " + error.message);
    toggleButton.disabled = false;
    return;
  }

  video.srcObject = state.mediaStream;
  placeholder.classList.add("hidden");

  const socket = new WebSocket(buildWebSocketUrl());
  socket.binaryType = "blob";
  state.socket = socket;

  socket.onopen = () => {
    connectionStatus.textContent = "Conectado";
    socket.send(JSON.stringify({ token: getToken() }));
    state.captureIntervalId = setInterval(captureAndSendFrame, CAPTURE_INTERVAL_MS);
  };

  socket.onmessage = (event) => {
    try {
      renderStatusCards(JSON.parse(event.data));
    } catch (error) {
      // ignora mensagens que não sejam JSON válido
    }
  };

  socket.onerror = () => {
    showError("Erro de conexão com o servidor.");
  };

  socket.onclose = (event) => {
    connectionStatus.textContent = "Desconectado";
    if (event.code === 4401) {
      showError("Sessão expirada ou inválida. Faça login novamente.");
      clearToken();
    }
    stopCamera();
  };

  state.running = true;
  toggleButton.disabled = false;
  toggleButton.textContent = "Encerrar";
  toggleButton.className =
    "text-sm px-4 py-2 rounded-md bg-red-600 hover:bg-red-500 text-white font-medium transition";
}

function stopCamera() {
  if (state.captureIntervalId) {
    clearInterval(state.captureIntervalId);
    state.captureIntervalId = null;
  }
  if (state.socket) {
    state.socket.onclose = null;
    if (state.socket.readyState === WebSocket.OPEN) {
      state.socket.close();
    }
    state.socket = null;
  }
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach((track) => track.stop());
    state.mediaStream = null;
  }

  video.srcObject = null;
  placeholder.classList.remove("hidden");
  connectionStatus.textContent = "";
  state.running = false;
  toggleButton.disabled = false;
  toggleButton.textContent = "Ativar câmera";
  toggleButton.className =
    "text-sm px-4 py-2 rounded-md bg-green-600 hover:bg-green-500 text-white font-medium transition";
}

toggleButton.addEventListener("click", () => {
  if (state.running) {
    stopCamera();
  } else {
    startCamera();
  }
});

window.addEventListener("beforeunload", () => {
  if (state.running) stopCamera();
});

requireAuth();
