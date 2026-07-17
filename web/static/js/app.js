const REFRESH_INTERVAL_MS = 5000;

const state = {
  detections: [],
  monitorRunning: false,
};

const MONITOR_BUTTON_CLASSES = {
  loading: "text-sm px-4 py-1.5 rounded-md bg-gray-700 text-white font-medium transition opacity-60",
  stopped: "text-sm px-4 py-1.5 rounded-md bg-green-600 hover:bg-green-500 text-white font-medium transition",
  running: "text-sm px-4 py-1.5 rounded-md bg-red-600 hover:bg-red-500 text-white font-medium transition",
};

function formatDateTime(isoString) {
  return new Date(isoString).toLocaleString("pt-BR");
}

async function fetchStatus() {
  const response = await apiFetch("/api/status");
  if (!response.ok) return;
  renderStatus(await response.json());
}

function renderStatus(status) {
  const cards = [
    { label: "Total de detecções", value: status.total_detections },
    {
      label: "Última detecção",
      value: status.latest_detection_at ? formatDateTime(status.latest_detection_at) : "—",
    },
    { label: "Confiança mínima", value: `${Math.round(status.confidence_threshold * 100)}%` },
    { label: "Atraso de captura", value: `${status.capture_delay_seconds}s` },
    { label: "Cooldown", value: `${status.capture_cooldown_seconds}s` },
    { label: "Retenção", value: `${status.image_retention_hours}h` },
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

async function fetchDetections() {
  const response = await apiFetch("/api/detections?limit=100");
  if (!response.ok) return;
  state.detections = await response.json();
  renderGallery();
}

let activeObjectUrls = [];

function revokeActiveObjectUrls() {
  activeObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  activeObjectUrls = [];
}

function renderGallery() {
  const gallery = document.getElementById("gallery");
  const emptyState = document.getElementById("empty-state");

  revokeActiveObjectUrls();

  if (state.detections.length === 0) {
    gallery.innerHTML = "";
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  gallery.innerHTML = state.detections
    .map(
      (item) => `
        <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div
            class="w-full h-48 bg-gray-800 flex items-center justify-center text-xs text-gray-500"
            data-image-container="${item.filename}"
          >
            Carregando...
          </div>
          <div class="p-3 flex items-center justify-between">
            <span class="text-sm text-gray-300">${formatDateTime(item.detected_at)}</span>
            <button
              class="text-red-400 hover:text-red-300 text-sm"
              data-delete="${item.filename}"
            >
              Excluir
            </button>
          </div>
        </div>`
    )
    .join("");

  gallery.querySelectorAll("button[data-delete]").forEach((button) => {
    button.addEventListener("click", () => deleteDetection(button.dataset.delete));
  });

  state.detections.forEach((item) => loadDetectionThumbnail(item));
}

/**
 * <img src="..."> cannot send an Authorization header, so authenticated
 * images are fetched as blobs via apiFetch and rendered through an object URL.
 */
async function loadDetectionThumbnail(item) {
  let response;
  try {
    response = await apiFetch(item.image_url);
  } catch (error) {
    return; // apiFetch already redirected to login on 401
  }
  if (!response.ok) return;

  const container = document.querySelector(
    `[data-image-container="${CSS.escape(item.filename)}"]`
  );
  if (!container) return;

  const objectUrl = URL.createObjectURL(await response.blob());
  activeObjectUrls.push(objectUrl);

  const img = document.createElement("img");
  img.src = objectUrl;
  img.alt = item.filename;
  img.className = "w-full h-48 object-cover cursor-pointer hover:opacity-90 transition";
  img.addEventListener("click", () => openLightbox(objectUrl));

  container.replaceWith(img);
}

async function deleteDetection(filename) {
  if (!confirm(`Excluir a imagem "${filename}"?`)) return;

  const response = await apiFetch(`/api/detections/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });

  if (response.ok || response.status === 204) {
    await refreshAll();
  } else {
    alert("Não foi possível excluir a imagem.");
  }
}

function openLightbox(src) {
  document.getElementById("lightbox-img").src = src;
  const lightbox = document.getElementById("lightbox");
  lightbox.classList.remove("hidden");
  lightbox.classList.add("flex");
}

function closeLightbox() {
  const lightbox = document.getElementById("lightbox");
  lightbox.classList.add("hidden");
  lightbox.classList.remove("flex");
}

async function fetchMonitorStatus() {
  const response = await apiFetch("/api/monitor/status");
  if (!response.ok) return;
  renderMonitorButton(await response.json());
}

function renderMonitorButton(monitorStatus) {
  state.monitorRunning = monitorStatus.running;
  const button = document.getElementById("monitor-btn");
  button.disabled = false;
  if (monitorStatus.running) {
    button.textContent = "Encerrar";
    button.className = MONITOR_BUTTON_CLASSES.running;
  } else {
    button.textContent = "Monitorar";
    button.className = MONITOR_BUTTON_CLASSES.stopped;
  }
}

async function toggleMonitor() {
  const button = document.getElementById("monitor-btn");
  const wasRunning = state.monitorRunning;

  button.disabled = true;
  button.className = MONITOR_BUTTON_CLASSES.loading;
  button.textContent = wasRunning ? "Encerrando..." : "Iniciando...";

  try {
    const response = await apiFetch(`/api/monitor/${wasRunning ? "stop" : "start"}`, {
      method: "POST",
    });
    if (!response.ok && response.status !== 409) {
      const body = await response.json().catch(() => ({}));
      alert(body.detail || "Não foi possível executar a ação.");
    }
  } catch (error) {
    alert("Erro de comunicação com o servidor.");
  }

  await fetchMonitorStatus();
}

async function refreshAll() {
  await Promise.all([fetchStatus(), fetchDetections(), fetchMonitorStatus()]);
}

document.getElementById("refresh-btn").addEventListener("click", refreshAll);
document.getElementById("monitor-btn").addEventListener("click", toggleMonitor);
document.getElementById("lightbox-close").addEventListener("click", closeLightbox);
document.getElementById("lightbox").addEventListener("click", (event) => {
  if (event.target.id === "lightbox") closeLightbox();
});
document.getElementById("logout-btn").addEventListener("click", () => {
  clearToken();
  redirectToLogin();
});

requireAuth();
refreshAll();
setInterval(refreshAll, REFRESH_INTERVAL_MS);
