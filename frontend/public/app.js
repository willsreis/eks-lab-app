const element = (id) => document.getElementById(id);
const buttons = [...document.querySelectorAll("button[data-endpoint]")];

function showInfo(info) {
  const healthy = info.status === "healthy";
  element("api-status").textContent = healthy ? "Healthy" : "Degraded";
  element("api-status").className = healthy ? "ok" : "bad";
  element("redis-status").textContent = info.redis;
  element("redis-status").className = info.redis === "connected" ? "ok" : "bad";
  for (const key of ["hostname", "namespace", "version", "timestamp", "requests"]) {
    element(key).textContent = info[key];
  }
  element("connection").textContent = "Última consulta recebida";
}

async function makeRequest(endpoint) {
  buttons.forEach((button) => { button.disabled = true; });
  element("endpoint").textContent = `GET ${endpoint}`;
  element("http-status").textContent = "Executando…";
  element("http-status").className = "";
  element("response").textContent = "Aguardando resposta…";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 16000);
  const start = performance.now();
  try {
    const response = await fetch(endpoint, { signal: controller.signal, cache: "no-store" });
    const body = await response.text();
    let data;
    try { data = JSON.parse(body); } catch { data = null; }
    element("response").textContent = data ? JSON.stringify(data, null, 2) : body;
    element("http-status").textContent = `HTTP ${response.status} · ${Math.round(performance.now() - start)} ms`;
    element("http-status").className = response.ok ? "ok" : "bad";
    if (endpoint === "/api/info") {
      if (!response.ok || !data?.service) throw new Error("A API não respondeu com informações válidas.");
      showInfo(data);
    }
  } catch (error) {
    element("connection").textContent = "Falha na última consulta";
    if (endpoint === "/api/info") {
      element("api-status").textContent = "Indisponível";
      element("api-status").className = "bad";
      for (const key of ["redis-status", "hostname", "namespace", "version", "timestamp", "requests"]) {
        element(key).textContent = "—";
        element(key).className = "";
      }
    }
    // Preserve an HTTP error response (including Nginx 502/504) for troubleshooting.
    if (element("http-status").textContent === "Executando…") {
      element("http-status").textContent = error.name === "AbortError" ? "Timeout" : "Erro de conexão";
      element("http-status").className = "bad";
      element("response").textContent = error.message;
    }
  } finally {
    clearTimeout(timeout);
    buttons.forEach((button) => { button.disabled = false; });
  }
}

buttons.forEach((button) => button.addEventListener("click", () => makeRequest(button.dataset.endpoint)));
makeRequest("/api/info");
