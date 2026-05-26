# Corpus ampliado (trabajo futuro)

Esta carpeta contiene **21 documentos adicionales** (políticas y procedimientos de seguridad redactados el 25 may 2026) que **no forman parte del corpus indexado** en el experimento principal documentado en `ENTREGABLE.md` §6.

## Por qué están fuera de `docs/`

El experimento del 18 may 2026 se calibró sobre los 4 documentos legítimos de `docs/` (configuracion_red, control_accesos, gestion_incidentes, politica_seguridad). Las métricas reportadas en §6 (80% attack success rate, drift coseno 0,6494) son específicas de ese corpus.

Mover estos 21 documentos a `docs/` y re-ejecutar `python ingest.py` invalidaría las cifras de §6 — el ratio de envenenamiento pasaría del 18,8% a aproximadamente 3,8%, y el ataque previsiblemente perdería eficacia (consistente con la lectura de §6.8: en un corpus de producción la tasa cae mientras el vector y la métrica de drift coseno siguen siendo válidos).

## Cómo usarlos (trabajo futuro)

Replicar el experimento con corpus ampliado:

```bash
cp corpus_ampliado/*.txt docs/
python ingest.py --clear
python ingest.py
python run_experiment.py
python metricas.py --plots
```

Esto produce métricas comparables sobre un corpus más realista (~25 docs legítimos vs 6 maliciosos). Los resultados permitirían contrastar empíricamente la predicción de §6.8: la tasa de éxito cae al diluirse la fracción envenenada, pero el drift coseno mantiene su utilidad como métrica de monitorización.

## Por qué se conservan en el repo

- Son documentos plausibles ya redactados (políticas y procedimientos reales) que sirven como punto de partida para la línea de trabajo futuro descrita en `ENTREGABLE.md` §8.3.
- Permiten a un evaluador externo reproducir la extensión sin tener que generar el corpus manualmente.
