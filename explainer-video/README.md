# Vídeo explicativo — Gabriel Archangel Investments

Vídeo web en inglés (1920×1080, locución + subtítulos) que explica de forma pedagógica cómo funciona el sistema de inversión de este repositorio (`ath-backend-prod`).

Duración: **3:09** · 30 fps · locución en inglés + música rítmica (118 BPM) + efectos de sonido sincronizados · audio normalizado a −16 LUFS. En inglés, el *Cañón Score* se presenta como **Cannon Score**.

## Entregables (`dist/`)

| Archivo | Uso |
|---|---|
| `gabriel-archangel-how-it-works-1080p.mp4` | Versión principal, 35 MB (H.264 + AAC, `faststart` para streaming web) |
| `gabriel-archangel-how-it-works-720p.mp4` | Versión ligera, 12 MB, para móvil / carga rápida |
| `poster.jpg` | Imagen de portada para el reproductor |
| `captions-en.vtt` | Subtítulos en inglés (WebVTT) |

### Insertar en la web

```html
<video controls playsinline preload="metadata" poster="poster.jpg" style="width:100%;height:auto">
  <source src="gabriel-archangel-how-it-works-1080p.mp4" type="video/mp4">
  <track kind="captions" src="captions-en.vtt" srclang="en" label="English" default>
</video>
```

## Guion (lo que explica el vídeo)

| Escena | Contenido | Origen en el código |
|---|---|---|
| Hook | Pregunta gancho: líderes de mercado, una puntuación objetiva, pérdida máxima conocida | — |
| Intro | Logo (golpe musical) + los 5 pasos | — |
| The core idea | Qué es un máximo histórico (ATH) y por qué se siguen los líderes | `ath_pct` en `engine/canon_score.py` |
| 01 · Universe | Lista de 30 líderes por sector | `config.TICKER_UNIVERSE_V1` |
| 02 · Data | Batch nocturno 02:00 UTC → base de datos de scores; refresco 15 min / 24 h / 7 días | `engine/batch.py`, `config.CACHE_*_TTL` |
| 03 · Cannon Score | 7 factores y sus pesos (25/20/20/15/10/5/5) | `engine/canon_score.py` |
| Example | Empresa hipotética que puntúa 82/100; ≥ 60 = candidata destacada | `tests/test_engines.py`, `/api/dashboard` |
| 04 · Screen | Filtros: distancia al ATH, ROIC, PEG, margen, deuda, tendencia SMA200 | `/api/screener` |
| 05 · Risk | Tamaño de posición: 1 % de 50 000 $ = 500 $; entrada 100 $, stop 90 $ → 50 acciones; objetivos 1R/2R/3R; riesgo total de cartera | `engine/risk_engine.py` |
| Recap + outro | Resumen de los 5 pasos, lema y aviso legal | — |

Todas las cifras del ejemplo se calculan con las reglas reales del motor. Los ejemplos van marcados como *Illustrative* en pantalla y el cierre incluye un aviso de que no es asesoramiento de inversión.

## Cómo editarlo y regenerarlo

- **Texto de la locución:** `script.json` (cada frase tiene un `id` que la animación usa como punto de sincronía).
- **Diseño y animación:** `src/index.html` (HTML + GSAP; cada escena se sincroniza con los tiempos de la voz).
- **Música:** `tools/music.py` sintetiza un groove pop/corporativo a 118 BPM (batería, bajo, acordes con *pumping*, arpegio) con subida y golpe en el logo, redobles y platos en cada cambio de escena. Los cambios de escena caen en el pulso (`bpm` y `snap_beats` en `script.json`). Para usar una pista con licencia (Artlist, Epidemic Sound…): `MUSIC=pista.mp3 tools/build.sh`.
- **Efectos de sonido:** cada animación registra su sonido con `fx()` en `src/index.html`; `render.cjs events` los exporta y `music.py` los sintetiza (pops, ticks, campanas, golpes, whooshes).
- **Vista previa interactiva:** abrir `src/index.html` en el navegador (clic para reproducir, barra de progreso y botón CC).

```bash
pip install kokoro-onnx soundfile numpy scipy imageio-ffmpeg
npm i -g playwright   # usa Chromium
tools/build.sh        # voz → eventos → música + efectos → mezcla → render → dist/
```

La voz se genera en local con Kokoro (voz `af_heart`, licencia Apache 2.0) y la música y los efectos se sintetizan con `tools/music.py`, así que no hay derechos de terceros. Tipografías: Inter, Cormorant Garamond y JetBrains Mono (SIL OFL); iconos Lucide (ISC); animación con GSAP (licencia estándar gratuita).

## Siguiente paso: presentador

Ver [`PRESENTER.md`](PRESENTER.md) para añadir una persona que presente el vídeo.
