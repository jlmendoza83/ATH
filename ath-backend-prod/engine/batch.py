"""
engine/batch.py
Job nocturno del Cañón Score.
Ejecutado por Railway Cron como servicio separado, no por el servidor web.

Comando en Railway Cron:
  python engine/batch.py

Necesita las mismas variables de entorno que el servidor:
  FMP_API_KEY, DATA_PROVIDER, DATA_DIR
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from config import DATA_PROVIDER, TICKER_UNIVERSE_V1
from cache.db import init_db, upsert_score, log_batch
from engine.canon_score import calcular_canon_score


def run():
    # Asegurar que la DB existe (idempotente)
    init_db()

    started_at = datetime.utcnow()
    print(f"[BATCH] {started_at.isoformat()}Z — {len(TICKER_UNIVERSE_V1)} tickers")

    ok_count, err_count, errors = 0, 0, []

    all_data = DATA_PROVIDER.get_bulk_metrics(TICKER_UNIVERSE_V1)

    for item in all_data:
        ticker = item["ticker"]
        try:
            price = item["price"]
            fund  = item["fund"]
            sales = item["sales"]
            sma   = item.get("sma", {})

            sma50  = sma.get("sma50")
            sma200 = sma.get("sma200")
            pvs50  = round((price.price - sma50)  / sma50  * 100, 2) if sma50  and price.price else None
            pvs200 = round((price.price - sma200) / sma200 * 100, 2) if sma200 and price.price else None
            gc     = (1 if sma50 > sma200 else 0) if sma50 and sma200 else None

            perf_1y = price.perf_1y
            if perf_1y is None:
                try:
                    import yfinance as yf
                    hist = yf.Ticker(ticker).history(period="1y")
                    if len(hist) >= 2:
                        perf_1y = round(
                            (hist["Close"].iloc[-1] - hist["Close"].iloc[0])
                            / hist["Close"].iloc[0] * 100, 1
                        )
                except Exception:
                    pass

            score = calcular_canon_score(
                ath_pct       = price.ath_pct,
                roic          = fund.roic,
                sales_cagr_3y = sales.cagr_3y,
                perf_1y       = perf_1y,
                net_margin    = fund.net_margin,
                debt_equity   = fund.debt_equity,
                current_ratio = fund.current_ratio,
                rel_volume    = price.rel_volume,
                market_cap    = price.market_cap,
            )

            upsert_score({
                "ticker":          ticker,
                "name":            fund.sector or ticker,
                "canon_score":     score.total,
                "price":           price.price,
                "change_pct":      price.change_pct,
                "w52_high":        price.w52_high,
                "ath_pct":         price.ath_pct,
                "perf_1y":         perf_1y,
                "rel_volume":      price.rel_volume,
                "market_cap":      price.market_cap,
                "sma50":           sma50,
                "sma200":          sma200,
                "price_vs_sma50":  pvs50,
                "price_vs_sma200": pvs200,
                "golden_cross":    gc,
                "roic":            fund.roic,
                "roe":             fund.roe,
                "roa":             fund.roa,
                "net_margin":      fund.net_margin,
                "gross_margin":    fund.gross_margin,
                "pe_ttm":          fund.pe_ttm,
                "fwd_pe":          fund.fwd_pe,
                "peg":             fund.peg,
                "ps":              fund.ps,
                "pb":              fund.pb,
                "debt_equity":     fund.debt_equity,
                "current_ratio":   fund.current_ratio,
                "debt_ebitda":     fund.debt_ebitda,
                "eps_ttm":         fund.eps_ttm,
                "eps_growth_yoy":  fund.eps_growth_yoy,
                "insider_own":     fund.insider_own,
                "target_price":    fund.target_price,
                "sector":          fund.sector,
                "sales_cagr_3y":   sales.cagr_3y,
                "sales_cagr_5y":   sales.cagr_5y,
                "sales_latest_yoy":sales.latest_yoy,
                "batch_run_at":    started_at.isoformat(),
                "error":           None,
            })
            ok_count += 1
            print(f"[BATCH] OK  {ticker:<6} score={score.total}")

        except Exception as e:
            err_count += 1
            msg = str(e)
            errors.append({"ticker": ticker, "error": msg})
            print(f"[BATCH] ERR {ticker:<6} {msg}")
            upsert_score({
                "ticker":       ticker,
                "error":        msg,
                "batch_run_at": started_at.isoformat(),
            })

    finished_at = datetime.utcnow()
    elapsed = (finished_at - started_at).total_seconds()
    log_batch(started_at, finished_at, ok_count, err_count, errors)
    print(f"[BATCH] Fin: {elapsed:.1f}s — OK:{ok_count} ERR:{err_count}")

    # Exit code no-zero si todos fallaron (Railway lo detecta como fallo)
    if err_count > 0 and ok_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
