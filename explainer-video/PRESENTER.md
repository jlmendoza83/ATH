# Añadir un presentador al vídeo

Objetivo: que una persona aparezca explicando el vídeo (picture-in-picture sobre las animaciones) para darle más cercanía y enganche.

## Opción A — Presentador generado con IA (Higgsfield)

Requiere el conector de Higgsfield conectado a una cuenta con créditos (claude.ai/customize/connectors) y una sesión nueva.

1. **Retrato:** generar un presentador **ficticio** (no una persona real identificable), aspecto de asesor financiero, fondo neutro oscuro acorde con la paleta azul marino/dorado, plano medio mirando a cámara, 16:9 o 1:1.
2. **Voz:** la locución actual es femenina (Kokoro `af_heart`, `build/narration.wav`). Si el presentador es un hombre, regenerar la voz con `am_michael` o `bm_george` (`"voice"` en `script.json`) o con una voz de Higgsfield (`list_voices`).
3. **Sincronía labial:** buscar con `models_explore` un modelo de avatar/lip-sync que acepte imagen + audio. La narración se trocea por escenas o frases usando `build/timings.json` (tramos de 15–30 s), se genera cada tramo y se concatena. Consultar el coste con `get_cost` antes de generar.
4. **Composición:** superponer el presentador con ffmpeg sobre `build/video-master.mp4` (círculo o tarjeta redondeada abajo a la derecha, ~420 px, borde dorado), alineado con la línea de tiempo. En el intro y el cierre puede ir más grande.
5. **Transparencia:** añadir al aviso legal final "Presenter is AI-generated". En comunicación financiera, un "asesor" que no existe sin avisarlo puede considerarse engañoso.

## Opción B — Persona real grabada

Grabar con el móvil en horizontal (1080p o 4K, luz frontal, fondo liso o croma) leyendo el guion de `script.json` con un teleprompter. La voz grabada sustituye a `build/narration.wav` y los tiempos se recalculan a partir de la grabación. Es la opción más creíble para una marca financiera.
