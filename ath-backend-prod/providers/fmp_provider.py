"""
providers/fmp_provider.py
Implementación del contrato DataProvider usando Financial Modeling Prep API.

API key: NUNCA hardcodeada aquí.
Se lee exclusivamente desde variable de entorno FMP_API_KEY via config.py.

Endpoints usados:
  /stable/company-screener       → filtros básicos de mercado
  /v3/profile/{ticker}           → sector, nombre, market cap
  /v3/quote/{ticker}             → precio, 52W High/Low, volumen
  /v3/key-metrics/{ticker}       → ROIC, FCF, EPS, insider%, deuda/EBITDA
  /v3/ratios/{ticker}            → P/E, P/B, P/S, PEG, ROE, ROA, márgenes, ratios
  /v3/income-statement/{ticker}  → ventas históricas
  /v3/analyst-estimates/{ticker} → EPS estimado próximo año
  /v3/price-target/{ticker}      → target price consenso
  /v3/technical_indicator/{ticker}?type=sma&period=50|200
"""

import os
import time
import requests
from datetime import datetime, timedelta
from .base import (
    DataProvider, PriceData, FundamentalsData,
    SalesHistory, YearRevenue, ScreenerResult
)


class FMPProvider(DataProvider):

    BASE_V3 = "https://financialmodelingprep.com/api/v3"
    BASE_STABLE = "https://financialmodelingprep.com/stable"

    # Límite conservador para no superar 300 calls/min de Starter
    # 280 calls/min = ~4.7 calls/seg → sleep de 0.22s entre llamadas
    RATE_LIMIT_SLEEP = 0.22

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("FMP_API_KEY no está configurada. "
                             "Añádela al archivo .env")
        self._key = api_key
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ── HTTP helper ─────────────────────────────────────────────

    def _get(self, url: str, params: dict = None, retries: int = 3) -> list | dict:
        p = {"apikey": self._key}
        if params:
            p.update(params)
        for attempt in range(retries):
            try:
                time.sleep(self.RATE_LIMIT_SLEEP)
                r = self._session.get(url, params=p, timeout=10)
                r.raise_for_status()
                return r.json()
            except requests.exceptions.HTTPError as e:
                if r.status_code == 429:          # rate limit
                    time.sleep(60)
                    continue
                if r.status_code == 401:
                    raise ValueError("FMP_API_KEY inválida o expirada") from e
                raise
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return []

    # ── Implementación del contrato ──────────────────────────────

    def get_price(self, ticker: str) -> PriceData:
        url = f"{self.BASE_V3}/quote/{ticker}"
        data = self._get(url)
        if not data:
            raise ValueError(f"Sin datos de precio para {ticker}")
        q = data[0]

        price    = q.get("price") or 0.0
        w52h     = q.get("yearHigh") or 0.0
        avg_vol  = q.get("avgVolume") or 1
        vol      = q.get("volume") or 0

        ath_pct = None
        if w52h and w52h > 0:
            ath_pct = round((price - w52h) / w52h * 100, 2)

        return PriceData(
            ticker     = ticker,
            price      = price,
            change_pct = q.get("changesPercentage") or 0.0,
            w52_high   = w52h,
            w52_low    = q.get("yearLow") or 0.0,
            ath_pct    = ath_pct,
            volume     = vol,
            avg_volume = avg_vol,
            rel_volume = round(vol / avg_vol, 2) if avg_vol else None,
            market_cap = q.get("marketCap"),
        )

    def get_fundamentals(self, ticker: str) -> FundamentalsData:
        # 3 llamadas: key-metrics, ratios, profile
        km_raw = self._get(f"{self.BASE_V3}/key-metrics/{ticker}", {"limit": 1})
        ra_raw = self._get(f"{self.BASE_V3}/ratios/{ticker}",      {"limit": 1})
        pr_raw = self._get(f"{self.BASE_V3}/profile/{ticker}")

        km = km_raw[0] if km_raw else {}
        ra = ra_raw[0] if ra_raw else {}
        pr = pr_raw[0] if pr_raw else {}

        # EPS growth: comparar con año anterior
        km_prev_raw = self._get(f"{self.BASE_V3}/key-metrics/{ticker}", {"limit": 2})
        eps_growth = None
        if len(km_prev_raw) >= 2:
            eps_curr = km_prev_raw[0].get("eps") or 0
            eps_prev = km_prev_raw[1].get("eps") or 0
            if eps_prev and eps_prev != 0:
                eps_growth = round((eps_curr - eps_prev) / abs(eps_prev) * 100, 1)

        return FundamentalsData(
            ticker        = ticker,
            roic          = self._pct(km.get("roic")),
            roe           = self._pct(ra.get("returnOnEquity")),
            roa           = self._pct(ra.get("returnOnAssets")),
            net_margin    = self._pct(ra.get("netProfitMargin")),
            gross_margin  = self._pct(ra.get("grossProfitMargin")),
            pe_ttm        = ra.get("priceEarningsRatio"),
            fwd_pe        = km.get("forwardPE"),
            peg           = ra.get("priceEarningsToGrowthRatio"),
            ps            = ra.get("priceToSalesRatio"),
            pb            = ra.get("priceToBookRatio"),
            debt_equity   = ra.get("debtEquityRatio"),
            current_ratio = ra.get("currentRatio"),
            debt_ebitda   = km.get("netDebtToEBITDA"),
            eps_ttm       = km.get("eps"),
            eps_growth_yoy= eps_growth,
            insider_own   = self._pct(km.get("insidersOwnership")),
            target_price  = pr.get("dcf"),   # FMP usa DCF como proxy
            sector        = pr.get("sector"),
            industry      = pr.get("industry"),
        )

    def get_sales_history(self, ticker: str, years: int = 5) -> SalesHistory:
        url = f"{self.BASE_V3}/income-statement/{ticker}"
        raw = self._get(url, {"limit": years + 1})  # +1 para calcular growth del primero

        if not raw:
            return SalesHistory(ticker=ticker, years=[])

        year_data = []
        for i, row in enumerate(reversed(raw[:years + 1])):  # orden cronológico
            rev = (row.get("revenue") or 0) / 1e9  # a miles de millones
            period = row.get("calendarYear") or row.get("date", "")[:4]
            prev_rev = None
            if i > 0:
                prev_rev = (raw[years - i + 1].get("revenue") or 0) / 1e9 if (years - i + 1) < len(raw) else None

            growth = None
            if prev_rev and prev_rev > 0:
                growth = round((rev - prev_rev) / prev_rev * 100, 1)

            year_data.append(YearRevenue(
                year=int(period) if period else 0,
                revenue=round(rev, 2),
                growth_pct=growth
            ))

        # Calcular CAGRs
        cagr_3y = cagr_5y = None
        if len(year_data) >= 4:
            cagr_3y = self._cagr(year_data[-4].revenue, year_data[-1].revenue, 3)
        if len(year_data) >= 6:
            cagr_5y = self._cagr(year_data[-6].revenue, year_data[-1].revenue, 5)

        latest_yoy = year_data[-1].growth_pct if year_data else None

        return SalesHistory(
            ticker    = ticker,
            years     = year_data,
            cagr_3y   = cagr_3y,
            cagr_5y   = cagr_5y,
            latest_yoy= latest_yoy,
        )

    def get_screener_universe(self, filters: dict) -> list:
        """
        Filtra usando el endpoint nativo de FMP.
        Solo los campos que FMP soporta nativamente en /company-screener.
        El resto de filtros se aplica en post-proceso en el engine.
        """
        url = f"{self.BASE_STABLE}/company-screener"
        params = {}

        # Mapear solo los filtros que FMP acepta nativamente
        fmp_native = {
            "market_cap_min": "marketCapMoreThan",
            "market_cap_max": "marketCapLowerThan",
            "price_min":      "priceMoreThan",
            "price_max":      "priceLowerThan",
            "volume_min":     "volumeMoreThan",
            "beta_min":       "betaMoreThan",
            "beta_max":       "betaLowerThan",
            "dividend_min":   "dividendMoreThan",
            "sector":         "sector",
            "exchange":       "exchange",
            "country":        "country",
        }
        for k, fmp_k in fmp_native.items():
            if filters.get(k) not in (None, "all", ""):
                params[fmp_k] = filters[k]

        params["isActivelyTrading"] = "true"
        params["limit"] = filters.get("limit", 500)

        raw = self._get(url, params)
        if not raw:
            return []

        return [r.get("symbol") for r in raw if r.get("symbol")]

    def get_bulk_metrics(self, tickers: list) -> list:
        """
        Descarga métricas de múltiples tickers para el batch nocturno.
        Usa /key-metrics-ttm/bulk si está disponible en el plan.
        Fallback: llamadas individuales con rate limiting.
        """
        # En Starter no hay bulk endpoint oficial, usamos llamadas individuales
        results = []
        for ticker in tickers:
            try:
                price = self.get_price(ticker)
                fund  = self.get_fundamentals(ticker)
                sales = self.get_sales_history(ticker, years=4)
                sma   = self._get_sma_data(ticker)
                results.append({
                    "ticker": ticker,
                    "price":  price,
                    "fund":   fund,
                    "sales":  sales,
                    "sma":    sma,
                })
            except Exception as e:
                # Log pero no interrumpir el batch
                print(f"[BATCH] Error en {ticker}: {e}")
        return results

    def _get_sma_data(self, ticker: str) -> dict:
        """Descarga SMA50 y SMA200 para filtros técnicos."""
        sma = {}
        for period in [50, 200]:
            try:
                url = f"{self.BASE_V3}/technical_indicator/daily/{ticker}"
                raw = self._get(url, {"type": "sma", "period": period, "limit": 1})
                if raw:
                    sma[f"sma{period}"] = raw[0].get("sma")
            except Exception:
                sma[f"sma{period}"] = None
        return sma

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _pct(val) -> float | None:
        """Convierte valor decimal de FMP a porcentaje. 0.55 → 55.0"""
        if val is None:
            return None
        # FMP devuelve algunos ratios como decimales (0.55) y otros como %
        # key-metrics usa decimales, ratios usa decimales también
        return round(float(val) * 100, 2) if abs(float(val)) <= 10 else round(float(val), 2)

    @staticmethod
    def _cagr(start: float, end: float, years: int) -> float | None:
        if not start or start <= 0 or years <= 0:
            return None
        return round(((end / start) ** (1 / years) - 1) * 100, 1)
