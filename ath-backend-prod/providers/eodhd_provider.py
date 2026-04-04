"""
providers/eodhd_provider.py
Esqueleto preparado para EODHD. NO implementado en V1.
Activar en config.py cuando se necesite cobertura global (Europa, BME, Asia).

Para activar:
  1. pip install requests (ya instalado)
  2. Añadir EODHD_API_KEY al .env
  3. En config.py cambiar DATA_PROVIDER = EODHDProvider(...)
  4. Implementar los métodos marcados con NotImplementedError
"""

from .base import DataProvider, PriceData, FundamentalsData, SalesHistory


class EODHDProvider(DataProvider):
    """
    Proveedor EODHD. Cobertura: 150K+ tickers en 60+ exchanges.
    Diferencia clave vs FMP: mejor calidad de fundamentales europeos
    y tickers con formato {SYMBOL}.{EXCHANGE} (ej: ASML.AS, REP.MC, SAP.XETRA)
    """

    BASE = "https://eodhd.com/api"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("EODHD_API_KEY no está configurada")
        self._key = api_key

    def _to_eodhd_ticker(self, ticker: str) -> str:
        """
        Convierte ticker estándar a formato EODHD.
        NVDA → NVDA.US   |  REP → REP.MC   |  ASML → ASML.AS
        Ampliar este mapa con los exchanges relevantes.
        """
        exchange_map = {
            "MC":    "MC",      # BME España
            "XETRA": "XETRA",  # Deutsche Börse
            "AS":    "AS",      # Euronext Amsterdam
            "PA":    "PA",      # Euronext París
            "L":     "L",       # LSE Londres
        }
        # Por defecto asume USA si no hay sufijo de exchange
        return f"{ticker}.US"

    def get_price(self, ticker: str) -> PriceData:
        raise NotImplementedError(
            "EODHDProvider.get_price() no implementado en V1. "
            "Implementar con endpoint /eod/{ticker}.{exchange}"
        )

    def get_fundamentals(self, ticker: str) -> FundamentalsData:
        """
        EODHD devuelve fundamentales en /fundamentals/{ticker}.{exchange}
        La respuesta tiene estructura: data["Highlights"], data["Valuation"], etc.
        Mapear a FundamentalsData siguiendo el mismo esquema que FMPProvider.
        """
        raise NotImplementedError(
            "EODHDProvider.get_fundamentals() no implementado en V1. "
            "Endpoint: /fundamentals/{ticker}.{exchange}?api_token=KEY&fmt=json"
        )

    def get_sales_history(self, ticker: str, years: int = 5) -> SalesHistory:
        raise NotImplementedError("No implementado en V1")

    def get_screener_universe(self, filters: dict) -> list:
        raise NotImplementedError("No implementado en V1")

    def get_bulk_metrics(self, tickers: list) -> list:
        raise NotImplementedError("No implementado en V1")
