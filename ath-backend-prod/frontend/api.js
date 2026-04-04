/**
 * frontend/api.js — Conector del frontend al backend ATH App.
 *
 * USO: importar este módulo en ath-app-v3.html con:
 *   <script src="api.js"></script>
 *
 * La URL del backend se configura en una sola constante.
 * En desarrollo apunta a localhost.
 * En producción apunta a la URL de Railway.
 * La API key NUNCA aparece aquí — eso es responsabilidad del backend.
 */

// ── Configuración ────────────────────────────────────────────────
// En desarrollo: "http://localhost:5000"
// En producción: "https://ath-app.up.railway.app" (tu URL de Railway)
const ATH_API = window.ATH_BACKEND_URL || "http://localhost:5000";

// ── Helper base ──────────────────────────────────────────────────
async function apiGet(path, params = {}) {
  const url = new URL(ATH_API + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") {
      url.searchParams.set(k, v);
    }
  });
  const res = await fetch(url.toString());
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.description || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiPost(path, body = {}) {
  const res = await fetch(ATH_API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.description || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── API pública ──────────────────────────────────────────────────

/** Comprueba estado del backend y último batch */
const ATH = {

  health() {
    return apiGet("/api/health");
  },

  /**
   * Screener con filtros opcionales.
   * Todos los parámetros son opcionales — omitir = sin filtro.
   */
  screener(filters = {}) {
    return apiGet("/api/screener", filters);
  },

  /** Ficha completa: score + precio + fundamentales + ventas */
  ficha(ticker) {
    return apiGet(`/api/ficha/${ticker}`);
  },

  /** Precio actual (cache 15 min en el backend) */
  price(ticker) {
    return apiGet(`/api/price/${ticker}`);
  },

  /**
   * Calcula operativa: posición, stop, R:R.
   * Sin llamadas externas — cálculo puro en el backend.
   */
  calcular(params) {
    return apiPost("/api/operativa/calcular", params);
  },

  /** Estado del último batch nocturno */
  batchStatus() {
    return apiGet("/api/batch/status");
  },
};

// ── Ejemplo de uso en el HTML ────────────────────────────────────
/*

// Cargar screener con filtros:
ATH.screener({ roic_min: 25, ath_pct_max: 15, canon_score_min: 70 })
  .then(data => renderTable(data.data))
  .catch(err => showError(err.message));

// Cargar ficha:
ATH.ficha("NVDA").then(data => {
  document.getElementById("f-price").textContent = "$" + data.price.price;
  document.getElementById("ff-roic").textContent = data.fund.roic + "%";
});

// Calcular operativa:
ATH.calcular({
  entry_price: 175.75,
  stop_price:  155.00,
  capital:     50000,
  risk_pct:    1.0,
  commission:  1.0,
  timeframe:   "weekly",
}).then(result => {
  document.getElementById("r-sh").textContent = result.shares;
  document.getElementById("r-t1").textContent = "$" + result.target_2r;
});

*/
