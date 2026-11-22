"use strict";

/**
 * Cliente da API FastAPI da Clínica Vida.
 * - Mesma origem quando o site é servido pelo backend (uvicorn na porta 8000).
 * - http://127.0.0.1:8000 quando aberto via Live Server ou direto do arquivo.
 * - Se a API não responder, o site usa window.CLINIC_FALLBACK (modo offline).
 */
(function () {
  const DEV_STATIC_PORTS = ["5500", "5501", "3000", "5173", "8080"];
  const metaBase = document.querySelector('meta[name="api-base"]')?.content.trim();
  const isHttp = location.protocol.startsWith("http");
  const base = metaBase || (isHttp && !DEV_STATIC_PORTS.includes(location.port) ? "" : "http://127.0.0.1:8000");

  class ApiError extends Error {
    constructor(message, status, detail) {
      super(message);
      this.status = status;
      this.detail = detail;
    }
  }

  async function request(path, { method = "GET", body, timeout = 6000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(base + path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      const data = await res.json().catch(() => null);
      // Hospedagem estática (ex.: GitHub Pages) responde 404/405 em HTML para /api → trata como "sem servidor"
      if ((res.status === 404 || res.status === 405) && !data) {
        throw new ApiError("Servidor indisponível.", 0, null);
      }
      if (!res.ok) {
        const detail = data?.detail;
        const message = typeof detail === "string" ? detail : "Não foi possível concluir a solicitação.";
        throw new ApiError(message, res.status, detail);
      }
      return data;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError("Servidor indisponível.", 0, null);   // rede, CORS ou timeout
    } finally {
      clearTimeout(timer);
    }
  }

  let catalogPromise = null;

  /** Carrega o catálogo da API (uma única vez); usa os dados locais se ela estiver fora do ar. */
  function loadCatalog() {
    catalogPromise ??= Promise.all([
      request("/api/specialties", { timeout: 2500 }),
      request("/api/doctors", { timeout: 2500 }),
      request("/api/insurances", { timeout: 2500 }),
      request("/api/faqs", { timeout: 2500 }),
      request("/api/clinic", { timeout: 2500 }),
    ])
      .then(([specialties, doctors, insurances, faqs, clinic]) => ({
        specialties, doctors, insurances, faqs, clinic, online: true,
      }))
      .catch(() => ({ ...window.CLINIC_FALLBACK, online: false }));
    return catalogPromise;
  }

  window.ClinicApi = {
    base,
    ApiError,
    loadCatalog,
    get: (path, opts) => request(path, opts),
    post: (path, body, opts) => request(path, { ...opts, method: "POST", body }),
  };
})();
