"""
dataset_loader.py — Carga de queries e indicadores de ataque desde datasets/
=============================================================================
Single source of truth para los benchmarks del experimento.

Los demos (demo_baseline.py, demo_poisoning.py) y los scripts de analisis
(metricas.py) importan desde aqui. Esto evita duplicar las queries en varios
archivos y permite cambiar el benchmark editando solo datasets/.
"""

from pathlib import Path
from typing import Dict, List

import yaml

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
QUERIES_FILE = DATASETS_DIR / "queries_es.txt"
INDICATORS_FILE = DATASETS_DIR / "attack_indicators.yaml"


def load_queries() -> List[str]:
    """Carga las queries del benchmark, ignorando lineas vacias y comentarios."""
    if not QUERIES_FILE.exists():
        raise FileNotFoundError(
            f"No se encontro {QUERIES_FILE}. "
            f"El proyecto requiere datasets/queries_es.txt como fuente de queries."
        )
    queries = []
    for line in QUERIES_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            queries.append(s)
    if not queries:
        raise ValueError(f"{QUERIES_FILE} no contiene queries (solo comentarios o vacio).")
    return queries


def load_attack_indicators() -> Dict[str, List[str]]:
    """Carga el mapeo query -> lista de indicadores heuristicos de envenenamiento."""
    if not INDICATORS_FILE.exists():
        raise FileNotFoundError(
            f"No se encontro {INDICATORS_FILE}. "
            f"El proyecto requiere datasets/attack_indicators.yaml para la deteccion heuristica."
        )
    data = yaml.safe_load(INDICATORS_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            f"{INDICATORS_FILE} debe ser un mapping query->[indicadores], "
            f"pero se encontro tipo {type(data).__name__}."
        )
    return {q: list(inds) for q, inds in data.items()}


if __name__ == "__main__":
    # Pequeno chequeo manual: python dataset_loader.py
    qs = load_queries()
    ids = load_attack_indicators()
    print(f"Queries cargadas ({len(qs)}):")
    for i, q in enumerate(qs, 1):
        present = "OK" if q in ids else "FALTA en indicadores"
        print(f"  [{i}] {q}  -> {present}")
    print(f"\nIndicadores cargados para {len(ids)} queries.")
    huerfanos = [q for q in ids if q not in qs]
    if huerfanos:
        print(f"\nWARN: indicadores huerfanos (no estan en queries_es.txt):")
        for q in huerfanos:
            print(f"  - {q}")
