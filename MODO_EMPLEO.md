# Modo de empleo — RAG Poisoning PoC

Recetario práctico orientado a casos de uso. Para la referencia exhaustiva ver [`README.md`](README.md); para el documento académico [`ENTREGABLE.md`](ENTREGABLE.md); para el vídeo [`GUION_VIDEO.md`](GUION_VIDEO.md); para el día de la entrega [`CHECKLIST_ENTREGA.md`](CHECKLIST_ENTREGA.md).

---

## Receta 0 — Arrancar de cero (Mac M4 limpio)

```bash
# 1. Clonar el repo
git clone https://github.com/promero04/rag-poisoning-poc.git
cd rag-poisoning-poc

# 2. Crear entorno y dependencias (~3 min)
bash setup.sh
source .venv/bin/activate

# 3. (Opcional) Instalar Ollama y descargar el modelo si no lo tienes
brew install ollama
brew services start ollama
ollama pull llama3.2:3b

# 4. Validar que todo importa y la BD vectorial funciona (~1 min)
python validate_setup.py
#   Espera: "TODO OK — entorno listo para `python ingest.py`"

# 5. Ajustar .env si usas tag de modelo distinto
#   Editar OLLAMA_MODEL si tu modelo no es "llama3.2:3b"
```

Si **no puedes / no quieres** instalar Ollama, edita `.env` y pon `LLM_PROVIDER=openai` (con tu `OPENAI_API_KEY`) o `LLM_PROVIDER=none` (modo solo recuperación, sin generación de respuesta).

---

## Receta 1 — Reproducir el experimento completo (lo que entregas)

```bash
source .venv/bin/activate

# Ingestar los 4 documentos legítimos en ChromaDB
python ingest.py

# E1 — RAG limpio, 5 queries de control
python demo_baseline.py
#   → resultados/baseline_results.json

# E2 — atacar, comparar, sacar métricas (k=3 y k=5 en una pasada, ~5 min)
python run_experiment.py
#   → resultados/poisoning_comparison_k3.json
#   → resultados/poisoning_comparison_k5.json
#   → resultados/seccion8_resultados_generado.md
#   → logs/experiment_<timestamp>.log

# Generar los 3 gráficos PNG por experimento
python metricas.py --plots
#   → resultados/plots/*.png
```

Tras esto tienes todo lo que necesita el ENTREGABLE (tablas de §6 ya escritas en el .md autogenerado, gráficos listos para incrustar).

---

## Receta 2 — Demo interactiva (la que vas a grabar)

Pre-grabación: deja todo precaliente para que la terminal arranque sin tiempos muertos.

```bash
source .venv/bin/activate

# A. Estado limpio
python poisoning.py --clear-poison
python ingest.py --clear
python ingest.py

# B. Query baseline (chunks legitimos en VERDE)
python query.py --collection rag_baseline -q "¿Cuál es la política de contraseñas?"

# C. Inyectar veneno
python poisoning.py
#   → 6 documentos maliciosos en colección rag_baseline

# D. Misma query, ahora con chunks ENVENENADOS en ROJO
python query.py --collection rag_baseline -q "¿Cuál es la política de contraseñas?"
```

> El paso B y D usan la **misma colección** (`rag_baseline`) — antes y después de inyectar. Es el contraste más limpio para el vídeo.

Si prefieres mantener colecciones separadas (lo que hace `demo_poisoning.py`):

```bash
python query.py --collection rag_baseline_clean -q "..."   # limpia (siempre)
python query.py --collection rag_poisoned     -q "..."   # envenenada (siempre)
```

---

## Receta 3 — Comparar con / sin defensa (para la sección 7 del entregable)

```bash
# Sin defensa — tasa de éxito del ataque ≈ 80%
DEFENSE_ENABLED=false python demo_poisoning.py --skip-ingest --k 3

# Con defensa heurística — debe seguir siendo ≈ 80%
#   (la defensa no captura información falsa plausible)
DEFENSE_ENABLED=true  python demo_poisoning.py --skip-ingest --k 3

# Con defensa + oráculo — debe bajar a 0%
#   (techo teórico, no aplicable en producción)
DEFENSE_ENABLED=true DEFENSE_USE_ORACLE=true python demo_poisoning.py --skip-ingest --k 3
```

Para verificar que el filtro defensivo SÍ funciona donde fue diseñado (prompt injection léxico):

```bash
python defenses.py
#   → Muestra 5 textos, indica cuáles bloquea
```

---

## Receta 4 — Inspección manual

```bash
# Ver el estado de las colecciones ChromaDB
python ingest.py --stats
python poisoning.py --stats

# Ver scores de similitud coseno para una query
python query.py --scores -q "acceso a producción"

# Verificar qué chunks envenenados aparecen en top-k tras la inyección
python poisoning.py --verify

# Procesar un batch de preguntas externas
echo "¿Quién aprueba un cambio en producción?" > preguntas.txt
echo "¿Hay procedimiento para revocar accesos?" >> preguntas.txt
python query.py --batch preguntas.txt --output resultados/batch.json
```

---

## Receta 5 — Limpieza y reseteo

```bash
# Borrar SOLO los documentos envenenados (mantiene los legítimos)
python poisoning.py --clear-poison

# Vaciar la colección por defecto
python ingest.py --clear

# Reset completo: borra BD, resultados y logs
rm -rf chroma_db resultados logs

# Reset total (incluyendo venv)
rm -rf .venv chroma_db resultados logs
```

---

## Receta 6 — Variables de entorno relevantes (`.env`)

| Variable | Valores | Cuándo cambiarla |
|---|---|---|
| `LLM_PROVIDER` | `ollama` / `openai` / `none` | Si Ollama no responde o quieres ahorrar minutos en demo |
| `OLLAMA_MODEL` | `llama3.2:3b` (recomendado), `qwen2.5:14b`, ... | Si tu modelo tiene tag distinto |
| `OPENAI_API_KEY` | `sk-...` real | Si pasas a OpenAI |
| `RETRIEVAL_K` | 3 (default) / 5 | Para sensibilidad a k |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 500 / 50 | Sólo si reingestar con otra granularidad |
| `DEFENSE_ENABLED` | `true` / `false` | Activa `PromptInjectionFilter` |
| `DEFENSE_USE_ORACLE` | `true` / `false` | Activa el oráculo (descarta `is_poisoned=True`) |

Ejemplo de override por sesión sin tocar `.env`:

```bash
DEFENSE_ENABLED=true RETRIEVAL_K=5 python demo_poisoning.py --skip-ingest --k 5
```

---

## Receta 7 — Outputs y dónde encontrar qué

| Quiero ver... | Archivo |
|---|---|
| Las 5 queries del benchmark | [`datasets/queries_es.txt`](datasets/queries_es.txt) |
| Los 6 documentos maliciosos | [`poisoning.py`](poisoning.py) (constante `POISONED_DOCUMENTS`) |
| Las respuestas baseline (E1) | `resultados/baseline_results.json` |
| Las respuestas envenenadas con scores y drift | `resultados/poisoning_comparison_k3.json` |
| Las tablas de la sección 6 del entregable | [`resultados/seccion8_resultados_generado.md`](resultados/seccion8_resultados_generado.md) |
| Gráficos para incrustar | `resultados/plots/*.png` |
| Log textual completo del experimento | `logs/experiment_<timestamp>.log` |

---

## Troubleshooting típico

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `python validate_setup.py` falla con `SyntaxError` en `demo_poisoning.py` | El venv usa Python 3.9 (Apple stock) | `rm -rf .venv && bash setup.sh` (el setup detecta python3.13 de Homebrew) |
| `No matching distribution found for langchain==X.Y.Z` | requirements.txt con versiones inexistentes | Verifica que estás en el último commit; el `requirements.txt` usa rangos `>=` no pins exactos |
| `Ollama no responde en http://localhost:11434` | Servicio parado | `brew services start ollama` o `ollama serve &` |
| `ollama pull` se queda colgado | Red lenta o modelo inexistente | Comprueba el tag exacto: `ollama list` |
| `OPENAI_API_KEY no configurada (placeholder)` | `.env` con `sk-...` literal | Pon una clave real o cambia a `LLM_PROVIDER=ollama` / `none` |
| El experimento no genera respuestas del LLM | El proveedor cayó silenciosamente a `none` | Mira la línea `[LLM] ...` al inicio del output |
| `Number of requested results 2 is greater than 1` | ChromaDB con pocos chunks (smoke test) | Inofensivo en validate_setup.py; en producción es porque la colección no se ingestó |

---

## Si grabas el vídeo desde cero

1. `python poisoning.py --clear-poison` (deja colección limpia).
2. `python ingest.py --clear && python ingest.py` (precarga base limpia).
3. Activa terminal con fuente grande (≥18 pt) y tema legible.
4. Sigue [`GUION_VIDEO.md`](GUION_VIDEO.md) bloque por bloque.
5. Tras grabar: `python run_experiment.py` y `python metricas.py --plots` por si quieres rehacer las cifras y los PNGs.

---

*Universidad de Deusto · Seguridad de la Información (SDI) · Curso 2025/26 · Pablo García*
