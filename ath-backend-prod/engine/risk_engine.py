"""
engine/risk_engine.py
Motor de cálculo de gestión de riesgo.
Lógica pura Python. No tiene dependencias externas.
"""

from dataclasses import dataclass


@dataclass
class OperativaResult:
    ticker:          str
    entry:           float
    stop:            float
    capital:         float
    risk_pct:        float
    timeframe:       str
    # Calculados
    risk_amount:     float     # capital * risk_pct / 100
    dist_abs:        float     # entry - stop
    dist_pct:        float     # (entry - stop) / entry * 100
    shares:          int       # floor(risk_amount / dist_abs)
    invested:        float     # shares * entry
    exposure_pct:    float     # invested / capital * 100
    fee:             float
    target_1r:       float     # entry + dist_abs * 1
    target_2r:       float     # entry + dist_abs * 2
    target_3r:       float     # entry + dist_abs * 3
    # Cartera
    portfolio_risk_current:  float
    portfolio_risk_new:      float
    portfolio_risk_total:    float


def calcular_posicion(
    ticker:   str,
    entry:    float,
    stop:     float,
    capital:  float,
    risk_pct: float,    # 0.1 a 10.0
    timeframe: str = "weekly",
    fee:       float = 1.0,
    portfolio_risk_current: float = 0.0,
) -> OperativaResult:

    if entry <= 0 or stop <= 0 or capital <= 0:
        raise ValueError("Entry, stop y capital deben ser > 0")
    if stop >= entry:
        raise ValueError("Stop loss debe ser menor que el precio de entrada")
    if not (0.1 <= risk_pct <= 10):
        raise ValueError("Riesgo debe estar entre 0.1% y 10%")

    risk_amount = round(capital * risk_pct / 100, 2)
    dist_abs    = round(entry - stop, 4)
    dist_pct    = round(dist_abs / entry * 100, 2)
    shares      = int(risk_amount // dist_abs)   # floor, nunca excede el riesgo
    invested    = round(shares * entry, 2)
    exposure    = round(invested / capital * 100, 2)
    new_risk    = round(portfolio_risk_current + risk_pct, 2)

    return OperativaResult(
        ticker           = ticker,
        entry            = entry,
        stop             = stop,
        capital          = capital,
        risk_pct         = risk_pct,
        timeframe        = timeframe,
        risk_amount      = risk_amount,
        dist_abs         = dist_abs,
        dist_pct         = dist_pct,
        shares           = shares,
        invested         = invested,
        exposure_pct     = exposure,
        fee              = fee,
        target_1r        = round(entry + dist_abs,     2),
        target_2r        = round(entry + dist_abs * 2, 2),
        target_3r        = round(entry + dist_abs * 3, 2),
        portfolio_risk_current = portfolio_risk_current,
        portfolio_risk_new     = risk_pct,
        portfolio_risk_total   = new_risk,
    )
