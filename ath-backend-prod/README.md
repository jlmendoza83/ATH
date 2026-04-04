# ATH App — Backend V1

## Arranque rápido

```bash
# 1. Clonar e instalar dependencias
pip install -r requirements.txt

# 2. Crear .env con tu API key de FMP
cp .env.example .env
# Editar .env y añadir: FMP_API_KEY=tu_clave_aqui

# 3. Arrancar servidor
python app.py

# 4. (Opcional) Lanzar batch manualmente para poblar scores.db
python engine/batch.py

# 5. Verificar que todo funciona
curl http://localhost:5000/health
```

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servidor y API key |
| GET | `/api/screener` | Screener con filtros (ver parámetros en app.py) |
| GET | `/api/ficha/:ticker` | Datos completos de una acción |
| GET | `/api/price/:ticker` | Precio actual (cache 15 min) |
| POST | `/api/operativa/calcular` | Calcula posición y riesgo |
| GET | `/api/dashboard` | Top cañones y resumen |
| POST | `/api/admin/batch` | Lanza batch manual (solo dev) |

## Variables de entorno

```
FMP_API_KEY=...          # requerido
DATA_PROVIDER=fmp        # fmp | eodhd
FLASK_ENV=development    # development | production
PORT=5000
FRONTEND_URL=http://localhost:3000
BATCH_HOUR=2
BATCH_MINUTE=0
```

## Estructura

```
ath-backend/
├── app.py                  # Servidor Flask + endpoints
├── config.py               # ⚡ Interruptor de proveedor
├── requirements.txt
├── Procfile                # Para Railway
├── .env.example
├── providers/
│   ├── base.py             # Contrato DataProvider + modelos
│   ├── fmp_provider.py     # FMP (activo V1)
│   └── eodhd_provider.py   # EODHD (esqueleto, V3)
├── engine/
│   ├── canon_score.py      # Algoritmo Cañón Score
│   ├── risk_engine.py      # Cálculo de posición/riesgo
│   └── batch.py            # Job nocturno
├── cache/
│   └── db.py               # SQLite: scores.db + cache
└── tests/
    └── test_engines.py     # Tests unitarios (sin API key)
```

## Qué está automatizado en V1

| ✅ Automatizado | ❌ No automatizado |
|---|---|
| Batch nocturno (APScheduler 02:00 UTC) | Conexión a datos reales de FMP (requiere Starter plan) |
| Cálculo Cañón Score en batch | Gráficos técnicos (TradingView embed, Fase 2) |
| Cache de precio/fundamentales/ventas | Alertas de ruptura (Fase 3) |
| Todos los endpoints REST | Cartera real desde broker (Fase 4) |
| Motor de riesgo (cálculo puro) | Resumen IA del negocio (Fase 3) |
| Tests unitarios del engine | Cobertura Europa/BME completa (EODHD, Fase 3) |
| Estructura para EODHD swap | — |

## Cambiar de FMP a EODHD

Editar una línea en `config.py`:
```python
DATA_PROVIDER = EODHDProvider(api_key=EODHD_API_KEY)
```
Nada más cambia. La UI y el engine son agnósticos al proveedor.
