# Fase 0 — Reconocimiento del repositorio `rag-poisoning-poc`

> **Modo:** solo lectura, sin modificaciones al código.
> **Fecha:** 2026-05-18. **Autores del repo:** Pablo Romero, Iker Diez y Jacqueline Furelos. **Entrega:** 2026-05-29.
> **Asignatura:** Seguridad de la Información (SDI) — Universidad de Deusto, curso 2025/26.

---

## Contexto

Este informe documenta el estado del repositorio `rag-poisoning-poc` antes de comenzar cualquier modificación. El repo contiene **un único commit** (`2f62849 Initial commit`) heredado de una conversación anterior con Claude. El objetivo es entender qué hay, qué funciona y qué falta, sin tocar nada, para planificar la entrega del 29 de mayo (documento descriptivo + vídeo ≤ 2:30 min).

> ⚠ **Aviso de entorno:** este reconocimiento se realizó desde Windows 11 (PowerShell), pero el usuario ejecutará el código en un **Mac M4**. El proyecto incluye un `setup.sh` POSIX-only — funciona nativamente en Mac/Linux y **no en Windows sin adaptación**. Por tanto los comandos de instalación se documentan para Mac/Linux, que es el entorno de destino real.

---

## 0.1 Inventario

### Árbol de directorios (raíz)

```
rag-poisoning-poc/
├── .env.example            # plantilla de configuración (sin secretos reales)
├── .gitignore              # excluye .venv, .env, chroma_db, resultados, logs
├── README.md               # documentación principal (DESACTUALIZADA — ver §0.5)
├── requirements.txt        # dependencias pinneadas
├── setup.sh                # instalador bash (Mac/Linux, no Windows)
│
├── rag_pipeline.py         # núcleo: clase RAGPipeline (ingesta + retrieve + LLM)
├── ingest.py               # script de ingestión inicial del corpus legítimo
├── query.py                # CLI de consultas (interactivo / batch / scores)
├── demo_baseline.py        # E1 — demo RAG limpio
├── demo_poisoning.py       # E2 — comparativa limpio vs. envenenado
├── poisoning.py            # inyección de documentos maliciosos
├── metricas.py             # análisis post-experimento de los JSON
├── run_experiment.py       # orquestador del experimento completo
│
└── docs/                   # corpus legítimo (4 docs de políticas corporativas)
    ├── politica_seguridad.txt
    ├── control_accesos.txt
    ├── gestion_incidentes.txt
    └── configuracion_red.txt

# Directorios generados en tiempo de ejecución (en .gitignore):
# .venv/, chroma_db/, resultados/, logs/
```

### Lenguajes y dependencias clave

- **Lenguaje único:** Python.
- **Versión Python declarada** (comentario en `requirements.txt`): 3.13.12. No hay `pyproject.toml` ni constraint duro.
- **Dependencias pinneadas (`requirements.txt`):**
  - RAG/orquestación: `langchain==1.2.13`, `langchain-community==0.4.1`, `langchain-core==1.2.23`, `langchain-text-splitters==1.1.1`
  - Vector store: `chromadb==1.5.5`, `langchain-chroma==1.1.0`
  - Embeddings locales: `sentence-transformers==5.3.0`, `langchain-huggingface==1.2.1`
  - LLMs: `langchain-ollama==1.0.1`, `langchain-openai==1.1.12`
  - Utilidades: `python-dotenv==1.2.2`, `colorama==0.4.6`, `tabulate==0.10.0`
- **Pre-requisito manual:** `torch` CPU-only debe instalarse **antes** de `requirements.txt` (`pip install torch --index-url https://download.pytorch.org/whl/cpu`). `setup.sh` lo gestiona.

### Tamaño aproximado

| Categoría | Archivos | Notas |
|---|---|---|
| Código Python | 8 `.py` | Núcleo + 3 demos + 2 utilidades + orquestador |
| Datos (corpus) | 4 `.txt` en `docs/` | ~9 KB de texto, políticas corporativas inventadas |
| Configuración | 3 (`.env.example`, `requirements.txt`, `setup.sh`) | — |
| Documentación | 1 (`README.md`) | ~4 KB, desactualizado |
| **Total versionado** | 17 archivos | Repo muy ligero (~150 KB) |

---

## 0.2 Arquitectura inferida

### Diagrama del pipeline RAG

```
docs/*.txt
   │
   ▼
DirectoryLoader + TextLoader (glob **/*.txt, UTF-8)        [rag_pipeline.py]
   │
   ▼
RecursiveCharacterTextSplitter
   chunk_size=500, overlap=50, separadores ["\n\n","\n",". "," "]
   │
   ▼
Embeddings: sentence-transformers/all-MiniLM-L6-v2
   local, CPU, normalize_embeddings=True, dim=384
   │
   ▼
ChromaDB persistente en ./chroma_db/
   colecciones: rag_baseline, rag_baseline_clean, rag_poisoned
   metadatos por chunk: {source, chunk_id (MD5), ingested_at, is_poisoned}
   │
   ▼
Retriever similarity_search, top-k configurable (default 3)
   │
   ▼
Prompt template (rag_pipeline.py):
   "Eres un asistente de seguridad corporativa. Responde la pregunta
    usando ÚNICAMENTE la información proporcionada en el contexto..."
   │
   ▼
LLM (configurable vía LLM_PROVIDER):
   - ollama → llama3.2 vía http://localhost:11434  (default)
   - openai → gpt-4o-mini con OPENAI_API_KEY
   - none   → solo recuperación, sin generación
   temperature=0
   │
   ▼
Respuesta + chunks fuente (con flag is_poisoned visible)
```

### Componentes y ubicación

| Componente | Archivo |
|---|---|
| Clase `RAGPipeline` | `rag_pipeline.py` |
| Prompt template | `rag_pipeline.py` (constante al inicio del módulo) |
| Inicialización de embeddings | `rag_pipeline.py` |
| Inicialización de ChromaDB | `rag_pipeline.py` |
| Lógica de retrieve (top-k) | `rag_pipeline.py` |
| Selección de LLM (factory) | `rag_pipeline.py` |
| Constantes `CHROMA_PERSIST`, `COLLECTION_NAME` | `rag_pipeline.py` (importadas en `poisoning.py` y demos) |

### Modelo de embeddings y LLM

- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (local, sin coste, sin API key, 384 dim).
- **LLM:** triple opción configurable. El default es **Ollama con `llama3.2`**. En Mac M4 viable nativamente.

### Vector store

ChromaDB local con persistencia en disco (`./chroma_db/`, SQLite embebido). Tres colecciones:
- `rag_baseline` — usada por `ingest.py` y `demo_baseline.py`.
- `rag_baseline_clean` — copia limpia para la comparativa en `demo_poisoning.py`.
- `rag_poisoned` — la que se envenena.

### Corpus legítimo

`docs/` contiene **4 documentos `.txt` inventados** que simulan políticas corporativas de una empresa ficticia (TechCorp Solutions S.L.):
- `politica_seguridad.txt` — contraseñas (12 caracteres mín., MFA obligatoria, vigencia 90 días).
- `control_accesos.txt` — mínimo privilegio, bastión, rotación SSH 30 días.
- `gestion_incidentes.txt` — procedimiento CSIRT 24/7, escalación inmediata.
- `configuracion_red.txt` — TLS 1.2+, sin protocolos legacy.

Tamaño total ~9 KB. Genera del orden de 10-15 chunks legítimos.

---

## 0.3 Tipos de RAG poisoning implementados

Todos los ataques viven en `poisoning.py` y consisten en **inyección directa de documentos maliciosos en el corpus** (data poisoning sobre ChromaDB). El archivo contiene **6 documentos maliciosos** que cubren **5 tipos de ataque distintos**.

| # | Attack type | Query objetivo | Estado | Técnica |
|---|---|---|---|---|
| 1 | `weak_passwords` (v1) | "¿Cuál es la política de contraseñas?" | ✅ Completo | Doc corporativo falso "actualización de emergencia" (6 chars, MFA opcional, 365 días) |
| 2 | `weak_passwords` (v2) | "¿Cuál es la política de contraseñas?" | ✅ Completo | Amplificación semántica — guía de onboarding RRHH falsa |
| 3 | `incident_suppression` | "¿Qué hacer si detecto un incidente?" | ✅ Completo | Procedimiento simplificado que desincentiva escalación |
| 4 | `access_escalation` | "¿Quién tiene acceso a producción?" | ✅ Completo | Política devops permisiva (todos los devs >6 meses) |
| 5 | `key_rotation_bypass` | "¿Cada cuánto se rotan las claves?" | ✅ Completo | Rotación anual en vez de 30 días, secretos en `.env` permitidos |
| 6 | `protocol_downgrade` | "¿Qué protocolos de cifrado se usan?" | ✅ Completo | Permite TLS 1.0/1.1, HTTP sin cifrar, Telnet, FTP |

**Característica común:** los 6 documentos llevan `is_poisoned=True` en metadatos, para distinguirlos en la demo (etiquetado pedagógico, no es una defensa real).

**Variantes NO implementadas** (candidatas a Fase 2 si se decide ampliar):
- Prompt injection en el cuerpo del documento (instrucciones tipo "ignore previous").
- Adversarial passages optimizados por gradiente para subir ranking.
- Backdoor en el modelo de embeddings.
- Manipulación de metadatos / ataques sobre chunk splitting.
- Jailbreak vía contexto que rompe el system prompt.

**Demostración del impacto:** sí existe. `demo_poisoning.py` compara baseline vs. envenenado para las mismas 5 queries, mide cuántos chunks envenenados aparecen en top-k y aplica detección heurística (lista de "indicadores" por query) sobre la respuesta del LLM. Calcula `attack_success_rate` global y por tipo de ataque.

---

## 0.4 Cómo ejecutarlo (Mac M4)

### Variables de entorno (`.env`)

Plantilla completa en `.env.example` (sin secretos reales — el `sk-...` es un placeholder):

```bash
LLM_PROVIDER=ollama|openai|none

# Si ollama:
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Si openai:
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION=rag_baseline
RETRIEVAL_K=3
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

`.env` no está commiteado (está en `.gitignore`). `setup.sh` lo crea copiando `.env.example`.

### Instalación

```bash
bash setup.sh                          # crea .venv, instala torch CPU y deps, copia .env
source .venv/bin/activate
# Opcional pero recomendado (para LLM local):
brew install ollama                    # o curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

### Ejecución (orden lógico)

```bash
python ingest.py                       # paso 1: poblar ChromaDB con docs legítimos
python demo_baseline.py                # paso 2: E1 — RAG limpio, 5 queries de control
python poisoning.py                    # paso 3: inyectar docs maliciosos
python demo_poisoning.py --k 3         # paso 4: E2 — comparativa limpio vs. envenenado
python metricas.py                     # paso 5: tablas de resumen

# Alternativa todo-en-uno:
python run_experiment.py --k 3         # orquestador con captura de logs
```

`query.py` permite consultas interactivas (`python query.py`) o batch (`python query.py --batch preguntas.txt --output resultados/`) fuera del experimento principal.

### Incógnitas pendientes de validación

- 🟡 Compatibilidad real entre `langchain-chroma==1.1.0` y `chromadb==1.5.5` (versiones muy recientes, no validado ejecutando).
- 🟡 Calidad de `llama3.2` respondiendo en castellano (depende de variante 1B/3B, no declarada).
- 🟡 El pipeline no se ha ejecutado: el reconocimiento es estático. La primera ejecución real podría revelar errores de import o de path.

---

## 0.5 Estado de salud

### README
- **Existe** y describe arquitectura, stack, instalación y uso del baseline.
- **DESACTUALIZADO** en aspectos importantes:
  - Indica `LangChain 0.3` y `ChromaDB 0.6` — el `requirements.txt` real tiene `langchain 1.2.13` y `chromadb 1.5.5`.
  - Menciona un archivo `evaluate.py` ("Día 7") que **no existe** en el repo. En su lugar existen `demo_poisoning.py`, `metricas.py` y `run_experiment.py`, **ninguno documentado en el README**.
  - El bloque "Fases del PoC" no refleja el flujo real `demo_poisoning.py → metricas.py`.
- **Consecuencia:** un profesor que clone el repo y siga el README puede ejecutar la fase E1 pero no la E2.

### Tests
- No hay carpeta `tests/`, ni `pytest.ini`, ni archivos `test_*.py`. Esperable en un PoC académico, pero conviene mencionarlo en el entregable.

### TODOs / FIXME
- No se han encontrado comentarios `TODO`/`FIXME`/`XXX` visibles en el código.

### Secretos hardcodeados
- **No hay secretos reales.** La cadena `sk-...` en `.env.example` y la referencia en `setup.sh` son placeholders pedagógicos.
- `.env` está correctamente en `.gitignore`.

### Deuda técnica visible
- README desactualizado (alto impacto académico — bloquea reproducción).
- Sin tests.
- Sin defensas implementadas (ver §0.6).
- Sin `pyproject.toml` ni constraint formal de versión de Python.
- `setup.sh` solo POSIX — no es problema para Mac, pero limita reproducibilidad en Windows.
- Detección de ataques exitosos basada en lista fija de keywords (en `demo_poisoning.py`). Razonable como PoC, mejorable académicamente.

### Bugs evidentes
- Ninguno detectado por inspección estática. Pendiente de ejecución real.

---

## 0.6 Diagnóstico final

### ¿Funcional, a medias o esquelético?

**Funcional y bastante completo para un PoC académico.** Cubre los 6 ingredientes que pediría un evaluador:

1. ✅ Pipeline RAG real (no maqueta) con ChromaDB + embeddings + LLM.
2. ✅ Corpus legítimo coherente (políticas de seguridad corporativa).
3. ✅ Ataque implementado y ejecutable (6 documentos maliciosos, 5 tipos).
4. ✅ Comparativa cuantitativa baseline vs. envenenado.
5. ✅ Métricas de éxito por query, por tipo de ataque y agregadas.
6. ✅ Demo grabable en terminal con colores (legítimo en verde vs. envenenado en rojo).

### ¿Qué falta como mínimo para ser entregable?

**P0 imprescindible:**
1. **Actualizar README** — corregir versiones del stack, documentar `demo_poisoning.py`, `poisoning.py`, `metricas.py`, `run_experiment.py`; eliminar la referencia a `evaluate.py` inexistente. Sin esto, el profesor no puede reproducir la fase E2.
2. **Verificar ejecución end-to-end en Mac M4** — confirmar compatibilidad de las versiones recientes de langchain/chromadb y que `llama3.2` responde aceptablemente en castellano. Si falla, fallback a `LLM_PROVIDER=openai` o `none`.
3. **Documento descriptivo (`ENTREGABLE.md`)** — no existe, es uno de los dos artefactos obligatorios.
4. **Guion del vídeo (`GUION_VIDEO.md`)** — no existe, es el otro artefacto obligatorio.

### ¿Qué lo hace defendible académicamente?

**A favor:**
- Cubre **5 vectores de ataque diferentes**, no uno repetido. Material para una sección comparativa fuerte.
- La **amplificación semántica** (dos documentos para la misma query) es un detalle táctico que muestra pensamiento de atacante.
- La detección heurística está **mapeada explícitamente** a cada ataque — el lector ve qué cuenta como "éxito" del envenenamiento.
- El ataque más vistoso para el vídeo es probablemente **`weak_passwords`** (12 → 6 caracteres, cambio dramático) o **`protocol_downgrade`** (permitir TLS 1.0 / Telnet salta a la vista).

**En contra (anticipar en defensa):**
- **No hay módulo de defensa implementado.** Para un trabajo de ciberseguridad es el agujero más grande. Defendible si el scope se enmarca como "caracterización ofensiva", pero gana mucho con al menos una defensa básica (sanitización de contexto, filtrado por fuente, scoring de confianza, etc.).
- **El ataque asume acceso de escritura a ChromaDB** — realista (cualquier RAG que ingiere desde fuentes web/internas tiene este vector) pero conviene justificarlo en el entregable.
- **Solo un modelo de embeddings, un LLM y un vector store probados** — sin comparativa entre proveedores.

---

## Cierre

Fase 0 completada. Siguiente paso: Fase 1 (`PLAN_MEJORAS.md` con propuestas P0/P1/P2/P3) tras tu aprobación explícita.
