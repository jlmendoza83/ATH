"""
providers/base.py
Contrato base que todo proveedor de datos debe implementar.
Este archivo NUNCA cambia. Es la interfaz estable del sistema.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ── Modelos de datos tipados ────────────────────────────────────
# Forma canónica de los datos en ATH App.
# Los adaptadores mapean sus respuestas a estos modelos.
# La lógica y la UI solo hablan con estos modelos.

@dataclass
class PriceData:
    ticker:        str
    price:         float
    change_pct:    float          # % cambio diario
    w52_high:      float          # 52-week high  [Finviz / FMP]
    w52_low:       float
    ath_absolute:  Optional[float] = None   # ATH histórico absoluto [yfinance]
    ath_pct:       Optional[float] = None   # calculado: (price - ath) / ath * 100
    volume:        Optional[int]   = None
    avg_volume:    Optional[int]   = None
    rel_volume:    Optional[float] = None   # calculado: volume / avg_volume
    perf_1y:       Optional[float] = None   # calculado: rendimiento 12 meses
    market_cap:    Optional[float] = None   # en dólares
    updated_at:    datetime = field(default_factory=datetime.utcnow)


@dataclass
class FundamentalsData:
    ticker:         str
    # Rentabilidad — core del Cañón Score
    roic:           Optional[float] = None   # [FMP /key-metrics]  ≈ ROCE proxy
    roe:            Optional[float] = None   # [FMP /ratios]
    roa:            Optional[float] = None   # [FMP /ratios]
    # Márgenes
    net_margin:     Optional[float] = None   # [FMP /ratios]
    gross_margin:   Optional[float] = None   # [FMP /ratios]
    # Valoración
    pe_ttm:         Optional[float] = None   # [FMP /ratios]
    fwd_pe:         Optional[float] = None   # [FMP /key-metrics]
    peg:            Optional[float] = None   # [FMP /ratios]
    ps:             Optional[float] = None   # [FMP /ratios]
    pb:             Optional[float] = None   # [FMP /ratios]
    # Balance
    debt_equity:    Optional[float] = None   # [FMP /ratios]
    current_ratio:  Optional[float] = None   # [FMP /ratios]
    debt_ebitda:    Optional[float] = None   # [FMP /key-metrics]
    # EPS
    eps_ttm:        Optional[float] = None   # [FMP /key-metrics]
    eps_growth_yoy: Optional[float] = None   # calculado desde /earnings
    eps_next_y:     Optional[float] = None   # [FMP /analyst-estimates]
    eps_next_5y:    Optional[float] = None   # [Finviz scrape — futuro]
    # Extra
    insider_own:    Optional[float] = None   # [FMP /key-metrics] %
    short_float:    Optional[float] = None   # no disponible en FMP
    target_price:   Optional[float] = None   # [FMP /price-target]
    sector:         Optional[str]   = None
    industry:       Optional[str]   = None
    updated_at:     datetime = field(default_factory=datetime.utcnow)


@dataclass
class YearRevenue:
    year:        int
    revenue:     float            # en miles de millones USD
    growth_pct:  Optional[float]  # vs año anterior
    is_estimate: bool = False


@dataclass
class SalesHistory:
    ticker:      str
    years:       list             # list[YearRevenue]
    cagr_3y:     Optional[float] = None   # calculado
    cagr_5y:     Optional[float] = None   # calculado
    latest_yoy:  Optional[float] = None
    next_year_est: Optional[float] = None


@dataclass
class ScreenerResult:
    ticker:       str
    name:         str
    canon_score:  int             # 0-100, calculado por ATH engine
    ath_pct:      float
    roic:         Optional[float]
    sales_3y:     Optional[float]
    eps_next_5y:  Optional[float]
    perf_1y:      Optional[float]
    rel_volume:   Optional[float]
    fwd_pe:       Optional[float]
    peg:          Optional[float]
    insider_own:  Optional[float]
    market_cap:   Optional[float]
    sector:       Optional[str]
    # Técnicos
    price_vs_sma50:  Optional[float] = None   # % vs SMA50
    price_vs_sma200: Optional[float] = None   # % vs SMA200
    golden_cross:    Optional[bool]  = None   # SMA50 > SMA200
    last_updated:    datetime = field(default_factory=datetime.utcnow)


# ── Interfaz base ───────────────────────────────────────────────

class DataProvider(ABC):
    """
    Contrato que todo proveedor de datos debe cumplir.
    FMPProvider y EODHDProvider implementan estos métodos.
    La lógica ATH solo habla con esta interfaz, nunca con APIs concretas.
    """

    @abstractmethod
    def get_price(self, ticker: str) -> PriceData:
        """Precio actual, 52W High/Low, cambio diario, volumen."""

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> FundamentalsData:
        """ROIC, márgenes, ratios de valoración, balance, EPS, insider%."""

    @abstractmethod
    def get_sales_history(self, ticker: str, years: int = 5) -> SalesHistory:
        """Ventas anuales históricas + CAGR calculados."""

    @abstractmethod
    def get_screener_universe(self, filters: dict) -> list:
        """Lista de tickers que pasan los filtros básicos de mercado."""

    @abstractmethod
    def get_bulk_metrics(self, tickers: list) -> list:
        """Descarga masiva de métricas para el batch nocturno."""

    def get_ath_absolute(self, ticker: str) -> Optional[float]:
        """
        ATH histórico absoluto.
        Implementación por defecto: yfinance fallback.
        Los adaptadores pueden sobreescribir si tienen fuente mejor.
        """
        try:
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period="5y")
            if not hist.empty:
                return float(hist["High"].max())
        except Exception:
            pass
        return None

    def health_check(self) -> dict:
        """Verifica que la conexión y la API key funcionan."""
        try:
            self.get_price("AAPL")
            return {"ok": True, "provider": self.__class__.__name__}
        except Exception as e:
            return {"ok": False, "error": str(e), "provider": self.__class__.__name__}
