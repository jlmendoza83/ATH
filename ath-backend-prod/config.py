"""
config.py — configuración central ATH App.
Lee exclusivamente desde variables de entorno.
En desarrollo: carga .env via dotenv.
En Railway: las variables se configuran en el panel, dotenv no hace nada.
"""

import os
from dotenv import load_dotenv

# Solo activo en desarrollo local; en Railway es no-op
load_dotenv()

# ── API Keys ─────────────────────────────────────────────────────
# NUNCA hardcodear. NUNCA imprimir en logs.
FMP_API_KEY   = os.environ.get("FMP_API_KEY",   "")
EODHD_API_KEY = os.environ.get("EODHD_API_KEY", "")

# ── Validación al arrancar ────────────────────────────────────────
_provider_name = os.environ.get("DATA_PROVIDER", "fmp").lower()

if _provider_name == "fmp" and not FMP_API_KEY:
    raise EnvironmentError(
        "FMP_API_KEY no está configurada. "
        "Añádela en Railway → Variables o en .env local."
    )

# ── Proveedor activo ─────────────────────────────────────────────
from providers.fmp_provider   import FMPProvider
from providers.eodhd_provider import EODHDProvider

if _provider_name == "fmp":
    DATA_PROVIDER = FMPProvider(api_key=FMP_API_KEY)
elif _provider_name == "eodhd":
    DATA_PROVIDER = EODHDProvider(api_key=EODHD_API_KEY)
else:
    raise ValueError(f"DATA_PROVIDER desconocido: '{_provider_name}'. Usar 'fmp' o 'eodhd'.")

# ── Rutas ────────────────────────────────────────────────────────
# En Railway el volumen persistente se monta en /data
# En desarrollo local usa ./cache/
import pathlib
_data_dir = pathlib.Path(os.environ.get("DATA_DIR", "./cache"))
_data_dir.mkdir(parents=True, exist_ok=True)
DB_PATH = str(_data_dir / "scores.db")

# ── Universo V1 ──────────────────────────────────────────────────
TICKER_UNIVERSE_V1 = [
    "NVDA", "META", "LLY",  "CRWD", "MSCI", "AXON",
    "ASML", "NVO",  "ISRG", "FICO", "ODFL", "POOL",
    "SHOP", "MELI", "CELH", "DECK", "FTNT", "CDNS",
    "PANW", "NOW",  "HUBS", "TTD",  "DDOG", "SNOW",
    "SAP",  "TDG",  "RMD",  "WST",  "IDXX", "VEEV",
]

# ── Cache TTL ────────────────────────────────────────────────────
CACHE_PRICE_TTL_MIN  = 15
CACHE_FUND_TTL_HOURS = 24
CACHE_SALES_TTL_DAYS = 7

# ── Servidor ─────────────────────────────────────────────────────
PORT         = int(os.environ.get("PORT", "5000"))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")
FLASK_ENV    = os.environ.get("FLASK_ENV", "production")
