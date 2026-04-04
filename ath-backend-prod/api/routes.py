"""
api/routes.py — Endpoints REST de ATH App.

El frontend SOLO habla con estos endpoints.
Ningún endpoint expone la API key ni datos internos del sistema.

Endpoints:
  GET  /api/health               → estado del sistema
  GET  /api/screener              → lista de tickers filtrados con Cañón Score
  GET  /api/ficha/<ticker>        → ficha completa de un ticker
  GET  /api/price/<ticker>        → precio actual (cache 15min)
  POST /api/operativa/calcular    → cálculo de posición (sin llamadas externas)
  GET  /api/batch/status          → estado del último batch
  POST /api/batch/run             → lanza batch manualmente (uso dev/admin)
"""
import logging
from flask import Blueprint, jsonify, request, abort

from cache import db
from providers import get_provider
from engine import canon_score, batch as batch_engine
import config

logger = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")


# ── /health ─────────────────────────────────────────────────────

@api.get("/health")
def health():
    """Comprueba que el servidor responde y la BD existe."""
    batch_info = db.get_last_batch_info()
    return jsonify({
        "status": "ok",
        "provider": config.ACTIVE_PROVIDER,
        "tickers_in_universe": len(config.TICKER_UNIVERSE),
        "last_batch": batch_info,
    })


# ── /screener ────────────────────────────────────────────────────

@api.get("/screener")
def screener():
    """
    Devuelve la lista de tickers del screener con Cañón Score.
    Todos los filtros son opcionales. Los datos vienen de scores.db (batch nocturno).

    Query params:
      sector            string    "Tecnología" | "Salud" | ...
      ath_pct_max       float     máxima distancia al ATH en % (ej: 15 → −15%)
      roic_min          float     ROIC mínimo %
      sales_3y_min      float     CAGR ventas 3Y mínimo %
      pe_max            float     P/E máximo
      fwd_pe_max        float     Forward P/E máximo
      peg_max           float     PEG máximo
      ps_max            float     P/S máximo
      pb_max            float     P/B máximo
      roe_min           float
      roa_min           float
      gross_margin_min  float
      net_margin_min    float
      debt_equity_max   float
      current_ratio_min float
      debt_ebitda_max   float
      insider_own_min   float
      rel_volume_min    float
      perf_1y_min       float
      price_above_sma200 bool    "true" | "false"
      price_above_sma50  bool
      canon_score_min   int
      limit             int       default 200
    """
    def flt(key, cast=float):
        v = request.args.get(key)
        try:
            return cast(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    filters = {
        "sector":             request.args.get("sector"),
        "ath_pct_max":        flt("ath_pct_max"),
        "roic_min":           flt("roic_min"),
        "sales_3y_min":       flt("sales_3y_min"),
        "pe_max":             flt("pe_max"),
        "fwd_pe_max":         flt("fwd_pe_max"),
        "peg_max":            flt("peg_max"),
        "ps_max":             flt("ps_max"),
        "pb_max":             flt("pb_max"),
        "roe_min":            flt("roe_min"),
        "roa_min":            flt("roa_min"),
        "gross_margin_min":   flt("gross_margin_min"),
        "net_margin_min":     flt("net_margin_min"),
        "debt_equity_max":    flt("debt_equity_max"),
        "current_ratio_min":  flt("current_ratio_min"),
        "debt_ebitda_max":    flt("debt_ebitda_max"),
        "insider_own_min":    flt("insider_own_min"),
        "rel_volume_min":     flt("rel_volume_min"),
        "perf_1y_min":        flt("perf_1y_min"),
        "price_above_sma200": request.args.get("price_above_sma200") == "true",
        "price_above_sma50":  request.args.get("price_above_sma50") == "true",
        "canon_score_min":    flt("canon_score_min", int),
        "limit":              flt("limit", int) or 200,
    }

    rows = db.get_scores(filters)
    return jsonify({"count": len(rows), "data": rows})


# ── /ficha/<ticker> ──────────────────────────────────────────────

@api.get("/ficha/<ticker>")
def ficha(ticker: str):
    """
    Devuelve ficha completa de un ticker.
    Combina: score (scores.db) + precio fresco (FMP, cache 15min)
             + fundamentales (FMP, cache 24h) + ventas (FMP, cache 7d)
    """
    ticker = ticker.upper()
    provider = get_provider()

    # Score del batch (puede ser None si el ticker no está en el universo)
    score_rows = db.get_scores({"sector": None, "limit": 1})   # hack temporal
    with db.get_db() as conn:
        score_row = conn.execute(
            "SELECT * FROM scores WHERE ticker = ?", (ticker,)
        ).fetchone()
        score_data = dict(score_row) if score_row else {}

    # Precio fresco (cache 15 min)
    cached_price = db.get_cached("price_cache", ticker, config.CACHE_PRICE_TTL_MIN)
    if cached_price:
        price_data = cached_price
    else:
        try:
            p = provider.get_price(ticker)
            price_data = batch_engine._price_to_dict(p)
            db.set_cached("price_cache", ticker, price_data)
        except Exception as e:
            logger.error(f"Error obteniendo precio para {ticker}: {e}")
            price_data = {}

    # Fundamentales (cache 24h)
    cached_fund = db.get_cached("fund_cache", ticker, config.CACHE_FUND_TTL_HOURS * 60)
    if cached_fund:
        fund_data = cached_fund
    else:
        try:
            f = provider.get_fundamentals(ticker)
            fund_data = batch_engine._fund_to_dict(f)
            db.set_cached("fund_cache", ticker, fund_data)
        except Exception as e:
            logger.error(f"Error obteniendo fundamentales para {ticker}: {e}")
            fund_data = {}

    # Ventas históricas (cache 7d)
    cached_sales = db.get_cached("sales_cache", ticker, config.CACHE_SALES_TTL_DAYS * 60 * 24)
    if cached_sales:
        sales_data = cached_sales
    else:
        try:
            s = provider.get_sales_history(ticker)
            sales_data = batch_engine._sales_to_dict(s)
            db.set_cached("sales_cache", ticker, sales_data)
        except Exception as e:
            logger.error(f"Error obteniendo ventas para {ticker}: {e}")
            sales_data = {}

    return jsonify({
        "ticker": ticker,
        "score":  score_data,
        "price":  price_data,
        "fund":   fund_data,
        "sales":  sales_data,
    })


# ── /price/<ticker> ──────────────────────────────────────────────

@api.get("/price/<ticker>")
def price(ticker: str):
    """Precio actual con cache de 15 minutos."""
    ticker   = ticker.upper()
    provider = get_provider()

    cached = db.get_cached("price_cache", ticker, config.CACHE_PRICE_TTL_MIN)
    if cached:
        return jsonify({**cached, "from_cache": True})

    try:
        p    = provider.get_price(ticker)
        data = batch_engine._price_to_dict(p)
        db.set_cached("price_cache", ticker, data)
        return jsonify({**data, "from_cache": False})
    except Exception as e:
        logger.error(f"Error precio {ticker}: {e}")
        abort(502, description=f"No se pudo obtener precio para {ticker}")


# ── /operativa/calcular ──────────────────────────────────────────

@api.post("/operativa/calcular")
def calcular_operativa():
    """
    Calcula posición, stop loss, tamaño y objetivos R:R.
    Sin llamadas externas — lógica interna pura.

    Body JSON:
      entry_price    float  precio de entrada
      stop_price     float  precio del stop loss
      capital        float  capital total de la cuenta
      risk_pct       float  % de riesgo por operación (0.1–10)
      commission     float  comisión estimada (default 1.0)
      timeframe      str    "weekly" | "monthly"
    """
    body = request.get_json(silent=True) or {}

    entry      = float(body.get("entry_price", 0))
    stop       = float(body.get("stop_price", 0))
    capital    = float(body.get("capital", 0))
    risk_pct   = float(body.get("risk_pct", 1.0))
    commission = float(body.get("commission", 1.0))
    timeframe  = str(body.get("timeframe", "weekly"))

    # Validaciones
    if entry <= 0 or stop <= 0 or capital <= 0:
        abort(400, description="entry_price, stop_price y capital deben ser positivos")
    if not (0.1 <= risk_pct <= 10):
        abort(400, description="risk_pct debe estar entre 0.1 y 10")
    if stop >= entry:
        abort(400, description="stop_price debe ser menor que entry_price (operación larga)")

    risk_amount = capital * risk_pct / 100
    dist_abs    = entry - stop
    dist_pct    = dist_abs / entry * 100
    shares      = int(risk_amount / dist_abs) if dist_abs > 0 else 0
    invested    = shares * entry
    exposure    = (invested / capital * 100) if capital > 0 else 0

    return jsonify({
        "entry_price":   round(entry, 2),
        "stop_price":    round(stop, 2),
        "dist_abs":      round(dist_abs, 2),
        "dist_pct":      round(dist_pct, 2),
        "risk_amount":   round(risk_amount, 2),
        "shares":        shares,
        "invested":      round(invested, 2),
        "exposure_pct":  round(exposure, 2),
        "commission":    commission,
        "target_1r":     round(entry + dist_abs, 2),
        "target_2r":     round(entry + dist_abs * 2, 2),
        "target_3r":     round(entry + dist_abs * 3, 2),
        "timeframe":     timeframe,
    })


# ── /batch/status ────────────────────────────────────────────────

@api.get("/batch/status")
def batch_status():
    """Estado del último batch nocturno."""
    info = db.get_last_batch_info()
    if not info:
        return jsonify({"status": "never_run", "message": "El batch no ha ejecutado aún."})
    return jsonify(info)


# ── /batch/run (admin) ───────────────────────────────────────────

@api.post("/batch/run")
def batch_run():
    """
    Lanza el batch manualmente.
    En producción: proteger con clave de admin o restringir a localhost.
    """
    # Protección mínima: solo en modo desarrollo o con header correcto
    admin_key = request.headers.get("X-Admin-Key", "")
    if config.FLASK_ENV == "production" and admin_key != config.FMP_API_KEY[:8]:
        abort(403, description="No autorizado")

    tickers = request.get_json(silent=True) or {}
    tickers = tickers.get("tickers", config.TICKER_UNIVERSE)

    logger.info(f"Batch manual lanzado para {len(tickers)} tickers")
    result = batch_engine.run_batch(tickers)
    return jsonify(result)
