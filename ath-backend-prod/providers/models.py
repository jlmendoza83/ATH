"""
providers/models.py — Modelos de datos tipados de ATH App.

Estos dataclasses son el contrato entre el proveedor de datos y el motor ATH.
Cualquier fuente (FMP, EODHD, mock) debe normalizar su respuesta a estos modelos.
La lógica de negocio solo opera sobre estos tipos — nunca sobre JSON crudo.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PriceData:
    ticker:       str
    price:        float
    change_pct:   float            # % cambio en el día
    w52_high:     float            # máximo 52 semanas
    w52_low:      float            # mínimo 52 semanas
    ath_pct:      float            # % distancia a w52_high (calculado: (price-w52h)/w52h*100)
    volume:       int
    avg_volume:   int
    rel_volume:   float            # volume / avg_volume
    market_cap:   float            # en dólares
    beta:         Optional[float] = None
    perf_1y:      Optional[float] = None   # % rendimiento últimos 12 meses
    sma50:        Optional[float] = None   # media móvil 50 sesiones
    sma200:       Optional[float] = None   # media móvil 200 sesiones
    updated_at:   datetime = field(default_factory=datetime.utcnow)


@dataclass
class FundamentalsData:
    ticker:           str
    # Rentabilidad — Core del Cañón Score
    roic:             Optional[float] = None   # Return on Invested Capital (≈ROCE proxy)
    roe:              Optional[float] = None
    roa:              Optional[float] = None
    # Márgenes
    gross_margin:     Optional[float] = None
    net_margin:       Optional[float] = None
    operating_margin: Optional[float] = None
    # Valoración
    pe_ttm:           Optional[float] = None
    fwd_pe:           Optional[float] = None
    peg:              Optional[float] = None
    ps:               Optional[float] = None   # price-to-sales
    pb:               Optional[float] = None   # price-to-book
    ev_ebitda:        Optional[float] = None
    # EPS
    eps_ttm:          Optional[float] = None
    eps_growth_yoy:   Optional[float] = None   # % crecimiento YoY
    # Balance
    debt_equity:      Optional[float] = None
    current_ratio:    Optional[float] = None
    debt_ebitda:      Optional[float] = None
    # Extras
    insider_own_pct:  Optional[float] = None
    short_float:      Optional[float] = None
    target_price:     Optional[float] = None
    sector:           Optional[str]   = None
    industry:         Optional[str]   = None
    updated_at:       datetime = field(default_factory=datetime.utcnow)


@dataclass
class YearRevenue:
    year:        int
    revenue:     float             # en millones USD
    growth_pct:  Optional[float]   # crecimiento YoY %
    is_estimate: bool = False


@dataclass
class SalesHistory:
    ticker:      str
    years:       list              # lista de YearRevenue
    cagr_3y:     Optional[float]   # CAGR 3 años calculado
    cagr_5y:     Optional[float]   # CAGR 5 años calculado
    latest_yoy:  Optional[float]   # crecimiento último año
    updated_at:  datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScreenerRow:
    """Fila del screener: combinación de precio + fundamentales + score calculado."""
    ticker:        str
    name:          str
    sector:        str
    price:         float
    market_cap:    float
    w52_high:      float
    ath_pct:       float
    roic:          Optional[float]
    sales_3y_cagr: Optional[float]
    eps_5y_est:    Optional[float]
    perf_1y:       Optional[float]
    rel_volume:    float
    fwd_pe:        Optional[float]
    peg:           Optional[float]
    insider_own:   Optional[float]
    canon_score:   int
    score_grade:   str             # "A+", "B", "C"
    # Técnicos opcionales
    price_vs_sma50:  Optional[float] = None   # % diferencia precio vs SMA50
    price_vs_sma200: Optional[float] = None   # % diferencia precio vs SMA200
    last_updated:    Optional[datetime] = None
