"""
engine/canon_score.py
Algoritmo del Cañón Score. Lógica 100% propia de ATH App.
No conoce ninguna API. Recibe datos normalizados y devuelve un int 0-100.

Pesos configurables (suma = 100):
  25 — Proximidad al ATH
  20 — ROIC (rentabilidad sobre capital)
  20 — Crecimiento de ventas
  15 — Fortaleza técnica (RS Rating)
  10 — Margen neto
   5 — Solidez del balance
   5 — Liquidez y volumen
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoreBreakdown:
    """Desglose del score para mostrarlo en la ficha."""
    proximidad_ath:    int
    roic:              int
    crecimiento_ventas:int
    fortaleza_tecnica: int
    margen_neto:       int
    solidez_balance:   int
    volumen_liquidez:  int
    total:             int


def calcular_canon_score(
    ath_pct:       Optional[float],    # % distancia al ATH (negativo = debajo)
    roic:          Optional[float],    # % ROIC / ROCE
    sales_cagr_3y: Optional[float],    # % CAGR ventas 3 años
    perf_1y:       Optional[float],    # % rendimiento 12 meses vs SP500 (RS)
    net_margin:    Optional[float],    # % margen neto
    debt_equity:   Optional[float],    # ratio deuda/equity
    current_ratio: Optional[float],    # ratio de liquidez
    rel_volume:    Optional[float],    # volumen relativo vs media 20d
    market_cap:    Optional[float],    # en dólares, para penalizar illíquidas
) -> ScoreBreakdown:

    # ── 1. Proximidad al ATH (25 pts) ───────────────────────────
    p_ath = 0
    if ath_pct is not None:
        if ath_pct >= -2:    p_ath = 25
        elif ath_pct >= -5:  p_ath = 22
        elif ath_pct >= -10: p_ath = 18
        elif ath_pct >= -15: p_ath = 12
        elif ath_pct >= -20: p_ath = 7
        elif ath_pct >= -30: p_ath = 3

    # ── 2. ROIC (20 pts) ────────────────────────────────────────
    p_roic = 0
    if roic is not None:
        if roic >= 50:   p_roic = 20
        elif roic >= 30: p_roic = 17
        elif roic >= 20: p_roic = 13
        elif roic >= 15: p_roic = 9
        elif roic >= 8:  p_roic = 5
        elif roic < 0:   p_roic = 0

    # ── 3. Crecimiento de ventas (20 pts) ───────────────────────
    p_ventas = 0
    if sales_cagr_3y is not None:
        if sales_cagr_3y >= 40:  p_ventas = 20
        elif sales_cagr_3y >= 25:p_ventas = 17
        elif sales_cagr_3y >= 15:p_ventas = 13
        elif sales_cagr_3y >= 8: p_ventas = 8
        elif sales_cagr_3y >= 3: p_ventas = 4
        elif sales_cagr_3y < 0:  p_ventas = 0

    # ── 4. Fortaleza técnica / RS Rating (15 pts) ───────────────
    # perf_1y es el rendimiento de la acción en 12 meses.
    # En V2 se compara contra SP500 para obtener RS relativo.
    # En V1 usamos el rendimiento absoluto como proxy.
    p_tecnica = 0
    if perf_1y is not None:
        if perf_1y >= 100:  p_tecnica = 15
        elif perf_1y >= 50: p_tecnica = 13
        elif perf_1y >= 25: p_tecnica = 10
        elif perf_1y >= 10: p_tecnica = 7
        elif perf_1y >= 0:  p_tecnica = 4
        elif perf_1y >= -15:p_tecnica = 2

    # ── 5. Margen neto (10 pts) ─────────────────────────────────
    p_margen = 0
    if net_margin is not None:
        if net_margin >= 30:  p_margen = 10
        elif net_margin >= 20:p_margen = 8
        elif net_margin >= 12:p_margen = 6
        elif net_margin >= 5: p_margen = 3
        elif net_margin < 0:  p_margen = 0

    # ── 6. Solidez del balance (5 pts) ──────────────────────────
    p_balance = 0
    if debt_equity is not None:
        if debt_equity <= 0:   p_balance = 5   # caja neta
        elif debt_equity <= 0.3:p_balance = 4
        elif debt_equity <= 1:  p_balance = 3
        elif debt_equity <= 2:  p_balance = 1
        # > 2: 0 pts

    if current_ratio is not None and current_ratio >= 2:
        p_balance = min(5, p_balance + 1)    # bonus por liquidez corriente

    # ── 7. Volumen y liquidez (5 pts) ───────────────────────────
    p_volumen = 0
    if rel_volume is not None:
        if rel_volume >= 2:    p_volumen = 5
        elif rel_volume >= 1.5:p_volumen = 4
        elif rel_volume >= 1:  p_volumen = 3
        elif rel_volume >= 0.5:p_volumen = 1

    # Penalizar micro-caps (< $100M) por illiquidez
    if market_cap is not None and market_cap < 100_000_000:
        p_volumen = max(0, p_volumen - 2)

    total = p_ath + p_roic + p_ventas + p_tecnica + p_margen + p_balance + p_volumen

    return ScoreBreakdown(
        proximidad_ath     = p_ath,
        roic               = p_roic,
        crecimiento_ventas = p_ventas,
        fortaleza_tecnica  = p_tecnica,
        margen_neto        = p_margen,
        solidez_balance    = p_balance,
        volumen_liquidez   = p_volumen,
        total              = total,
    )
