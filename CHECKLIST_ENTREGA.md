# Checklist final de entrega

**Asignatura:** SDI — Universidad de Deusto, 2025/26
**Deadline:** 29 de mayo de 2026

---

## Antes del día de la entrega

### Validar que el proyecto arranca desde cero

Probar en una carpeta limpia (idealmente en Mac M4, el entorno real de entrega):

```bash
git clone <url-del-repo> rag-poisoning-poc-test
cd rag-poisoning-poc-test
bash setup.sh
source .venv/bin/activate
python validate_setup.py         # debe terminar con "TODO OK"
ollama pull llama3.2             # si vas a usar Ollama
python run_experiment.py         # experimento completo (~5-10 min)
python metricas.py --plots       # gráficos PNG
```

Verificar:
- [ ] `validate_setup.py` termina sin errores.
- [ ] `resultados/baseline_results.json` existe y tiene 5 queries.
- [ ] `resultados/poisoning_comparison_k3.json` existe y tiene métricas con `attack_success_rate > 0%`.
- [ ] `resultados/plots/*.png` contiene los 3 gráficos.
- [ ] `resultados/seccion8_resultados_generado.md` contiene tablas con números.

### Completar los documentos con los números reales

- [ ] `ENTREGABLE.md` §6 — sustituir los rangos esperados por los valores observados (copiar de `resultados/seccion8_resultados_generado.md`).
- [ ] `ENTREGABLE.md` §6.6 — añadir las capturas de los PNG generados.
- [ ] `ENTREGABLE.md` §8.4 — escribir la reflexión personal (5–10 líneas).
- [ ] `ENTREGABLE.md` §9 — verificar URLs/DOIs de las referencias marcadas con ⚠.
- [ ] `GUION_VIDEO.md` Bloque D — sustituir `[PORCENTAJE]` y `[VALOR]` por los números reales.

### Grabar el vídeo

- [ ] Ensayar el guion con cronómetro 2–3 veces (objetivo: ≤ 2:25).
- [ ] Grabar a 1920×1080.
- [ ] Audio limpio (sin ruidos, sin clicks de teclado dominantes).
- [ ] Duración total ≤ 2:30.
- [ ] Exportar `.mp4` (H.264) con nombre `rag_poisoning_poc_pablo_garcia.mp4`.

---

## Lo que va en el ZIP

```
rag_poisoning_poc_pablo_garcia.zip
├── codigo/                              # carpeta con TODO el repo
│   ├── *.py                             # todos los scripts
│   ├── docs/                            # corpus legítimo
│   ├── datasets/                        # benchmark de queries
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── setup.sh
│   ├── .env.example
│   ├── .gitignore
│   ├── README.md
│   ├── RECONOCIMIENTO.md
│   ├── PLAN_MEJORAS.md
│   ├── ENTREGABLE.md
│   ├── GUION_VIDEO.md
│   └── CHECKLIST_ENTREGA.md
├── resultados/                          # outputs reales del experimento
│   ├── baseline_results.json
│   ├── poisoning_comparison_k3.json
│   ├── poisoning_comparison_k5.json
│   ├── metricas_resumen.json
│   ├── seccion8_resultados_generado.md
│   └── plots/*.png
├── ENTREGABLE.pdf                       # exportar ENTREGABLE.md a PDF (Pandoc o Word)
└── README.md                            # copia del README del repo en la raíz del ZIP
```

**Importante: NO incluir** en el ZIP:
- `.venv/` (entorno virtual, varios GB).
- `chroma_db/` (regenerable con `python ingest.py`).
- `.git/` (opcional; depende de si el profesor pide el historial; por defecto fuera para reducir tamaño).
- `__pycache__/` y `*.pyc`.
- `.env` (puede contener tu API key — usa `.env.example` que es plantilla).
- `logs/` (regenerable).

---

## Qué va en Drive si excede el tamaño

Si el ZIP supera el límite de la plataforma (típicamente 100 MB en eGela):

- Subir el `.mp4` del vídeo a Drive (>10 MB sin comprimir) y dejar el enlace en `ENTREGABLE.md` portada y en el formulario de entrega.
- Si el ZIP sigue siendo grande, mover también `resultados/plots/*.png` a Drive y referenciarlos en `ENTREGABLE.md`.
- Comprobar permisos del enlace de Drive: **lectura para cualquiera con el enlace** (no "sólo Deusto" salvo que el profesor pida lo contrario).

---

## Exportar ENTREGABLE.md a PDF

Opciones:

**Pandoc (recomendado, mantiene tablas y código):**
```bash
brew install pandoc basictex
pandoc ENTREGABLE.md -o ENTREGABLE.pdf \
    --pdf-engine=xelatex \
    -V geometry:margin=2cm \
    -V mainfont="Helvetica" \
    --toc
```

**Alternativa simple:** abrir `ENTREGABLE.md` en VS Code con la extensión "Markdown PDF" → Export PDF.

**Si los DOIs / referencias dan guerra:** exportar a `.docx` con `pandoc ENTREGABLE.md -o ENTREGABLE.docx`, abrir en Word, ajustar manualmente y guardar como PDF desde Word.

---

## Día de la entrega

- [ ] Probar de nuevo `python validate_setup.py` desde el ZIP recién descomprimido.
- [ ] Verificar enlaces de Drive (abrir en navegador en modo incógnito).
- [ ] Enviar el formulario / plataforma del profesor con:
  - ZIP del proyecto.
  - PDF de `ENTREGABLE.md`.
  - Enlace al `.mp4` del vídeo.
- [ ] Guardar copia local de todo lo enviado (por si la plataforma da problemas).

---

## Si algo falla en el último momento

| Problema | Plan B |
|---|---|
| Ollama no descarga `llama3.2` | Cambiar a `LLM_PROVIDER=openai` con `gpt-4o-mini` (necesita API key). |
| OpenAI también falla | Usar `LLM_PROVIDER=none` — la demo muestra el contexto recuperado, sin generación. Sigue siendo grabable y honesta. |
| `chromadb` / `langchain` incompatibles | Crear `.venv` con Python 3.11 (más conservador que 3.13). |
| El vídeo dura > 2:30 | Recortar el Bloque B (RAG limpio) a 20 s en lugar de 30 s. |
| Pandoc no exporta PDF | Plan B: export desde VS Code (`Markdown PDF`). Plan C: copiar a Google Docs → "Descargar como PDF". |

---

*Universidad de Deusto · Seguridad de la Información (SDI) · Curso 2025/26 · Pablo García · 29 de mayo de 2026*
