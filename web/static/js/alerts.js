const PAGE_SIZE = 20;

const state = {
  alerts: [],
  offset: 0,
};

let activeObjectUrls = [];

function revokeActiveObjectUrls() {
  activeObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  activeObjectUrls = [];
}

function formatDateTime(isoString) {
  return new Date(isoString).toLocaleString("pt-BR");
}

async function fetchAlerts({ reset = false } = {}) {
  if (reset) {
    state.alerts = [];
    state.offset = 0;
  }

  const response = await apiFetch(`/api/alerts?limit=${PAGE_SIZE}&offset=${state.offset}`);
  if (!response.ok) return;

  const page = await response.json();
  state.alerts = state.alerts.concat(page);
  state.offset += page.length;

  renderAlerts();

  const loadMoreButton = document.getElementById("load-more-btn");
  loadMoreButton.classList.toggle("hidden", page.length < PAGE_SIZE);
}

function renderAlerts() {
  const list = document.getElementById("alerts-list");
  const emptyState = document.getElementById("empty-state");

  revokeActiveObjectUrls();

  if (state.alerts.length === 0) {
    list.innerHTML = "";
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  list.innerHTML = state.alerts
    .map(
      (alert) => `
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-4">
          <div
            class="w-20 h-20 shrink-0 rounded-md overflow-hidden bg-gray-800 flex items-center justify-center text-[10px] text-gray-500 text-center"
            data-image-container="${alert.id}"
          >
            Carregando...
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-100 truncate">${alert.message}</p>
            <p class="text-xs text-gray-500 mt-1">${formatDateTime(alert.created_at)}</p>
          </div>
          <span
            class="shrink-0 text-xs px-2 py-1 rounded-full ${
              alert.sent ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-400"
            }"
          >
            ${alert.sent ? "Enviado" : "Pendente"}
          </span>
        </div>`
    )
    .join("");

  state.alerts.forEach((alert) => loadAlertThumbnail(alert));
}

/**
 * <img src="..."> cannot send an Authorization header, so authenticated
 * images are fetched as blobs via apiFetch and rendered through an object URL.
 */
async function loadAlertThumbnail(alert) {
  const container = document.querySelector(`[data-image-container="${CSS.escape(alert.id)}"]`);
  if (!container) return;

  let response;
  try {
    response = await apiFetch(alert.image_url);
  } catch (error) {
    return; // apiFetch already redirected to login on 401
  }

  if (!response.ok) {
    container.textContent = "Imagem indisponível";
    return;
  }

  const objectUrl = URL.createObjectURL(await response.blob());
  activeObjectUrls.push(objectUrl);

  const img = document.createElement("img");
  img.src = objectUrl;
  img.alt = alert.message;
  img.className =
    "w-20 h-20 shrink-0 rounded-md object-cover cursor-pointer hover:opacity-90 transition";
  img.addEventListener("click", () => openLightbox(objectUrl));

  container.replaceWith(img);
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

document.getElementById("refresh-btn").addEventListener("click", () => fetchAlerts({ reset: true }));
document.getElementById("load-more-btn").addEventListener("click", () => fetchAlerts());
document.getElementById("lightbox-close").addEventListener("click", closeLightbox);
document.getElementById("lightbox").addEventListener("click", (event) => {
  if (event.target.id === "lightbox") closeLightbox();
});

requireAuth();
fetchAlerts({ reset: true });
