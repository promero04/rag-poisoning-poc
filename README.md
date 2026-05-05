# RAG Poisoning PoC — Código

**Asignatura:** Seguridad de la Información (SDI) — Deusto 2025/26
**Proyecto:** Demostración de ataques de Poisoning sobre sistemas RAG
**Autor:** Pablo García

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Pipeline                             │
│                                                             │
│  Documentos  →  Splitter  →  Embeddings  →  ChromaDB       │
│  (./docs/)      (chunks)   (MiniLM-L6)    (persistente)    │
│                                                 │           │
│  Query  ──────────────────→  Retriever  ────────┘           │
│                               (top-k)                      │
│                                  │                         │
│                                  ↓                         │
│                          Prompt Template                    │
│                                  │                         │
│                                  ↓                         │
│                             LLM (Ollama/OpenAI)            │
│                                  │                         │
│                                  ↓                         │
│                            Respuesta + Fuentes             │
└─────────────────────────────────────────────────────────────┘
```

## Stack técnico

| Componente | Tecnología |
|---|---|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) |
| Vector store | ChromaDB 0.6 (persistente en disco) |
| RAG framework | LangChain 0.3 |
| LLM | Ollama (`llama3.2`) o OpenAI (`gpt-4o-mini`) |
| Chunking | `RecursiveCharacterTextSplitter` (500 chars, 50 overlap) |

## Instalación

```bash
bash setup.sh
source .venv/bin/activate
```

## Uso

```bash
# 1. Ingestar documentos legítimos en ChromaDB
python ingest.py

# 2. Demo completa (E1 — Baseline)
python demo_baseline.py

# 3. Query interactiva
python query.py

# 4. Query directa
python query.py -q "¿Cuál es la política de contraseñas?"

# 5. Batch de queries
python query.py --batch preguntas_baseline.txt --output resultados/baseline.json

# 6. Ver scores de similitud
python query.py --scores -q "acceso a producción"
```

## Estructura de archivos

```
codigo/
├── rag_pipeline.py        ← Clase RAGPipeline (core)
├── ingest.py              ← Script de ingestión
├── query.py               ← CLI de consultas
├── demo_baseline.py       ← Demo E1 (baseline limpio)
├── poisoning.py           ← [Día 6] Script de ataque
├── evaluate.py            ← [Día 7] Métricas de efectividad
├── docs/                  ← Documentos legítimos del knowledge base
│   ├── politica_seguridad.txt
│   ├── gestion_incidentes.txt
│   ├── control_accesos.txt
│   └── configuracion_red.txt
├── chroma_db/             ← Base de datos vectorial (creada automáticamente)
├── resultados/            ← JSONs de resultados de demos
├── requirements.txt
├── .env.example           → copiar a .env
└── setup.sh
```

## Fases del PoC

| Fase | Script | Descripción |
|------|--------|-------------|
| **E1** | `demo_baseline.py` | RAG limpio, verificar funcionamiento correcto |
| **E2** | `poisoning.py` | Inyectar documentos maliciosos, medir impacto |
| **E2** | `evaluate.py` | Comparar baseline vs. envenenado, métricas |

## Metadatos de documentos (ChromaDB)

Cada chunk almacenado incluye:
- `source`: ruta del documento original
- `chunk_id`: hash MD5 del contenido (detección de duplicados)
- `ingested_at`: timestamp de ingestión
- `is_poisoned`: `False` en baseline, `True` en documentos maliciosos

Este campo `is_poisoned` permite distinguir visualmente en la demo
si el chunk recuperado es legítimo o ha sido inyectado por el atacante.
