"""
app.py — Servidor Flask ATH App (producción).

En producción el batch lo ejecuta Railway Cron, no APScheduler.
APScheduler está deshabilitado en producción (FLASK_ENV != development).
"""

import os
from datetime import datetime
from dataclasses import asdict
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import DATA_PROVIDER, FRONTEND_URL, PORT, FLASK_ENV
from cache.db import init_db, get_screener_results, cache_get, cache_set
from engine.canon_score import calcular_canon_score
from engine.risk_engine  import calcular_posicion

app = Flask(__name__)

# CORS: en producción restringir a la URL del frontend real
cors_origins = [FRONTEND_URL] if FRONTEND_URL != "*" else ["*"]
CORS(app, origins=cors_origins)

# Init DB (crea tablas si no existen, idempotente)
init_db()

# APScheduler solo en desarrollo local para conveniencia
if FLASK_ENV == "development":
    from apscheduler.schedulers.background import BackgroundScheduler
    from engine.batch import run as run_batch
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(run_batch, "cron", hour=2, minute=0, id="batch_dev")
    sched.start()
    print("[DEV] APScheduler activo (en producción usa Railway Cron)")


# ═══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return jsonify({
        "server":    "ok",
        "env":       FLASK_ENV,
        "provider":  DATA_PROVIDER.health_check(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


@app.get("/api/screener")
def screener():
    def qf(k, cast=float):
        v = request.args.get(k)
        return cast(v) if v is not None else None

    filters = {
        "sector":            request.args.get("sector", "all"),
        "canon_score_min":   qf("canon_score_min"),
        "ath_pct_max":       qf("ath_pct_max"),
        "pe_max":            qf("pe_max"),
        "fwd_pe_max":        qf("fwd_pe_max"),
        "peg_max":           qf("peg_max"),
        "ps_max":            qf("ps_max"),
        "pb_max":            qf("pb_max"),
        "roic_min":          qf("roic_min"),
        "roe_min":           qf("roe_min"),
        "roa_min":           qf("roa_min"),
        "net_margin_min":    qf("net_margin_min"),
        "gross_margin_min":  qf("gross_margin_min"),
        "debt_equity_max":   qf("debt_equity_max"),
        "current_ratio_min": qf("current_ratio_min"),
        "debt_ebitda_max":   qf("debt_ebitda_max"),
        "sales_3y_min":      qf("sales_3y_min"),
        "eps_growth_min":    qf("eps_growth_min"),
        "insider_own_min":   qf("insider_own_min"),
        "perf_1y_min":       qf("perf_1y_min"),
        "rel_volume_min":    qf("rel_volume_min"),
        "price_above_sma200":request.args.get("price_above_sma200") == "true",
        "price_above_sma50": request.args.get("price_above_sma50")  == "true",
        "golden_cross":      request.args.get("golden_cross")        == "true",
        "limit":             qf("limit", int) or 200,
    }

    rows = get_screener_results(filters)
    return jsonify({"data": rows, "count": len(rows)})


@app.get("/api/ficha/<ticker>")
def ficha(ticker: str):
    ticker = ticker.upper().strip()

    price_data = cache_get("price_cache", ticker, 15)
    if price_data is None:
        try:
            p = DATA_PROVIDER.get_price(ticker)
            price_data = asdict(p)
            ath_abs = DATA_PROVIDER.get_ath_absolute(ticker)
            if ath_abs and p.price:
                price_data["ath_absolute"] = ath_abs
                price_data["ath_pct_absolute"] = round(
                    (p.price - ath_abs) / ath_abs * 100, 2)
            cache_set("price_cache", ticker, price_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 502

    fund_data = cache_get("fund_cache", ticker, 60 * 24)
    if fund_data is None:
        try:
            f = DATA_PROVIDER.get_fundamentals(ticker)
            fund_data = asdict(f)
            cache_set("fund_cache", ticker, fund_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 502

    sales_data = cache_get("sales_cache", ticker, 60 * 24 * 7)
    if sales_data is None:
        try:
            s = DATA_PROVIDER.get_sales_history(ticker)
            sales_data = asdict(s)
            cache_set("sales_cache", ticker, sales_data)
        except Exception as e:
            sales_data = {"ticker": ticker, "years": [], "error": str(e)}

    score = calcular_canon_score(
        ath_pct       = price_data.get("ath_pct"),
        roic          = fund_data.get("roic"),
        sales_cagr_3y = sales_data.get("cagr_3y"),
        perf_1y       = price_data.get("perf_1y"),
        net_margin    = fund_data.get("net_margin"),
        debt_equity   = fund_data.get("debt_equity"),
        current_ratio = fund_data.get("current_ratio"),
        rel_volume    = price_data.get("rel_volume"),
        market_cap    = price_data.get("market_cap"),
    )

    return jsonify({
        "ticker": ticker,
        "price":  price_data,
        "fund":   fund_data,
        "sales":  sales_data,
        "score":  asdict(score),
    })


@app.get("/api/price/<ticker>")
def price(ticker: str):
    ticker = ticker.upper().strip()
    cached = cache_get("price_cache", ticker, 15)
    if cached:
        return jsonify(cached)
    try:
        p = DATA_PROVIDER.get_price(ticker)
        data = asdict(p)
        cache_set("price_cache", ticker, data)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/operativa/calcular")
def operativa_calcular():
    body = request.get_json(force=True) or {}
    missing = [k for k in ("entry","stop","capital","risk_pct") if k not in body]
    if missing:
        return jsonify({"error": f"Faltan campos: {missing}"}), 400
    try:
        result = calcular_posicion(
            ticker     = body.get("ticker", "—"),
            entry      = float(body["entry"]),
            stop       = float(body["stop"]),
            capital    = float(body["capital"]),
            risk_pct   = float(body["risk_pct"]),
            timeframe  = body.get("timeframe", "weekly"),
            fee        = float(body.get("fee", 1.0)),
            portfolio_risk_current = float(body.get("portfolio_risk_current", 0.0)),
        )
        return jsonify(asdict(result))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/dashboard")
def dashboard():
    from cache.db import get_conn
    top = get_screener_results({"canon_score_min": 60, "limit": 6})
    with get_conn() as conn:
        last = conn.execute(
            "SELECT * FROM batch_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return jsonify({
        "top_cannons": top,
        "last_batch":  dict(last) if last else {"status": "never_run"},
    })


# Solo para desarrollo local
@app.post("/api/admin/batch")
def trigger_batch():
    if FLASK_ENV != "development":
        return jsonify({"error": "Solo disponible en desarrollo"}), 403
    from engine.batch import run as run_batch
    run_batch()
    return jsonify({"ok": True})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint no encontrado"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Error interno"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT,
            debug=(FLASK_ENV == "development"))
