const TOKEN_STORAGE_KEY = "pdm_access_token";

function getToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function redirectToLogin() {
  window.location.href = "/login.html";
}

/** Redirects to the login page immediately if there is no token client-side. */
function requireAuth() {
  if (!getToken()) {
    redirectToLogin();
  }
}

/** fetch() wrapper that attaches the bearer token and redirects to login on 401. */
async function apiFetch(url, options = {}) {
  const token = getToken();
  const headers = Object.assign(
    {},
    options.headers || {},
    token ? { Authorization: `Bearer ${token}` } : {}
  );

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    clearToken();
    redirectToLogin();
    throw new Error("Not authenticated");
  }

  return response;
}
