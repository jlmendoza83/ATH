"""
tests/test_engines.py
Tests unitarios de la lógica interna. No necesitan API key.
Ejecutar: python -m pytest tests/ -v
"""

import sys, os
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.canon_score import calcular_canon_score
from engine.risk_engine  import calcular_posicion


# ── Canon Score ──────────────────────────────────────────────────

def test_score_maximo():
    s = calcular_canon_score(
        ath_pct=-1, roic=60, sales_cagr_3y=50,
        perf_1y=120, net_margin=35, debt_equity=0,
        current_ratio=3, rel_volume=2.5, market_cap=5e9
    )
    assert s.total >= 90, f"Score máximo esperado >=90, obtenido {s.total}"

def test_score_minimo():
    s = calcular_canon_score(
        ath_pct=-50, roic=-5, sales_cagr_3y=-10,
        perf_1y=-30, net_margin=-5, debt_equity=5,
        current_ratio=0.5, rel_volume=0.2, market_cap=1e6
    )
    assert s.total <= 5, f"Score mínimo esperado <=5, obtenido {s.total}"

def test_score_nulos():
    s = calcular_canon_score(
        ath_pct=None, roic=None, sales_cagr_3y=None,
        perf_1y=None, net_margin=None, debt_equity=None,
        current_ratio=None, rel_volume=None, market_cap=None
    )
    assert s.total == 0

def test_score_suma_componentes():
    s = calcular_canon_score(
        ath_pct=-3, roic=35, sales_cagr_3y=22,
        perf_1y=60, net_margin=25, debt_equity=0.2,
        current_ratio=2.5, rel_volume=1.8, market_cap=50e9
    )
    suma = (s.proximidad_ath + s.roic + s.crecimiento_ventas +
            s.fortaleza_tecnica + s.margen_neto +
            s.solidez_balance + s.volumen_liquidez)
    assert suma == s.total


# ── Risk Engine ──────────────────────────────────────────────────

def test_posicion_basica():
    r = calcular_posicion("NVDA", entry=175.75, stop=155.0,
                          capital=50000, risk_pct=1.0)
    assert r.shares == 24
    assert r.risk_amount == 500.0
    assert r.dist_abs == pytest.approx(20.75, rel=1e-3)

def test_posicion_no_excede_riesgo():
    r = calcular_posicion("TEST", entry=100, stop=90,
                          capital=10000, risk_pct=2.0)
    riesgo_real = r.shares * r.dist_abs
    assert riesgo_real <= r.risk_amount

def test_stop_mayor_que_entrada():
    import pytest
    with pytest.raises(ValueError):
        calcular_posicion("TEST", entry=100, stop=110,
                          capital=10000, risk_pct=1.0)

def test_riesgo_fuera_rango():
    import pytest
    with pytest.raises(ValueError):
        calcular_posicion("TEST", entry=100, stop=90,
                          capital=10000, risk_pct=15.0)

def test_targets():
    r = calcular_posicion("TEST", entry=100, stop=90,
                          capital=10000, risk_pct=1.0)
    assert r.target_1r == pytest.approx(110, rel=1e-3)
    assert r.target_2r == pytest.approx(120, rel=1e-3)
    assert r.target_3r == pytest.approx(130, rel=1e-3)

def test_riesgo_total_cartera():
    r = calcular_posicion("TEST", entry=100, stop=90,
                          capital=10000, risk_pct=1.5,
                          portfolio_risk_current=3.5)
    assert r.portfolio_risk_total == pytest.approx(5.0, rel=1e-3)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
