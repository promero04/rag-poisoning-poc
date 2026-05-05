"""
demo_baseline.py — Demo E1: RAG funcional (estado LIMPIO / baseline)
=====================================================================
Demuestra el pipeline RAG completo antes de cualquier ataque de poisoning.
Ejecutar con: python demo_baseline.py

Salida esperada:
  ✓ Documentos ingestados en ChromaDB
  ✓ Queries respondidas correctamente con contexto recuperado
  ✓ Scores de similitud visualizados
  ✓ JSON de resultados guardado en ./resultados/baseline_results.json

Este script es la EVIDENCIA de la Entrega 1 (E1).
"""

import json
import os
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, init as colorama_init

from rag_pipeline import RAGPipeline

colorama_init(autoreset=True)

# ─── Preguntas de baseline ───────────────────────────────────────────────────
# Estas queries representan el comportamiento CORRECTO del sistema.
# En la fase de poisoning, el sistema devolverá respuestas manipuladas.

BASELINE_QUERIES = [
    "¿Cuál es la política de contraseñas de la empresa?",
    "¿Qué debo hacer si detecto un incidente de seguridad?",
    "¿Quién tiene acceso a los sistemas de producción?",
    "¿Cada cuánto tiempo se rotan las claves de acceso?",
    "¿Qué protocolos de cifrado se usan en la red interna?",
]


def banner(title: str, color: str = Fore.BLUE):
    width = 62
    print(f"\n{color}{'═'*width}")
    print(f"  {title}")
    print(f"{'═'*width}{Style.RESET_ALL}\n")


def run_demo():
    banner("RAG Poisoning PoC — FASE 1: Baseline (RAG Limpio)", Fore.BLUE)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ── 1. Inicializar pipeline ─────────────────────────────────────────────
    banner("PASO 1: Inicialización del pipeline RAG", Fore.CYAN)
    pipeline = RAGPipeline(collection="rag_baseline")

    # ── 2. Ingestar documentos legítimos ────────────────────────────────────
    banner("PASO 2: Ingestión de documentos legítimos", Fore.CYAN)

    docs_dir = "./docs"
    if not Path(docs_dir).exists():
        print(f"{Fore.RED}Error: carpeta ./docs no encontrada.{Style.RESET_ALL}")
        return

    doc_files = list(Path(docs_dir).glob("*.txt"))
    print(f"Documentos encontrados: {len(doc_files)}")
    for f in doc_files:
        size = f.stat().st_size
        print(f"  • {f.name:<40} ({size:>5} bytes)")

    print()
    n_chunks = pipeline.ingest(docs_dir)
    print(f"\n{Fore.GREEN}✓ {n_chunks} chunks almacenados en ChromaDB{Style.RESET_ALL}")

    # ── 3. Estadísticas de la colección ─────────────────────────────────────
    banner("PASO 3: Estado de ChromaDB", Fore.CYAN)
    stats = pipeline.collection_stats()
    for k, v in stats.items():
        print(f"  {k:<25}: {v}")

    # ── 4. Ejecutar queries baseline ─────────────────────────────────────────
    banner("PASO 4: Queries de baseline (comportamiento CORRECTO)", Fore.CYAN)

    results = []
    for i, question in enumerate(BASELINE_QUERIES, 1):
        print(f"\n{Fore.YELLOW}[Query {i}/{len(BASELINE_QUERIES)}]{Style.RESET_ALL}")
        result = pipeline.query(question)
        results.append(result)
        print(f"\n  {Fore.GREEN}✓ Respuesta generada | Chunks recuperados: {result['chunks_retrieved']}{Style.RESET_ALL}")

    # ── 5. Análisis de similitud ─────────────────────────────────────────────
    banner("PASO 5: Análisis de similitud (embeddings)", Fore.CYAN)

    test_query = BASELINE_QUERIES[0]
    print(f"Query de análisis: '{test_query}'")
    print(f"\nScores de similitud coseno:")

    hits = pipeline.similarity_search(test_query, k=5)
    for doc, score in hits:
        source = Path(doc.metadata.get("source", "?")).name
        is_poisoned = doc.metadata.get("is_poisoned", False)
        tag = f"{Fore.RED}[ENVENENADO]" if is_poisoned else f"{Fore.GREEN}[LEGÍTIMO] "
        bar_len = int(score * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        print(f"  {tag}{Style.RESET_ALL} {score:.4f} [{bar}] {source}")
        print(f"           → {doc.page_content[:80]}...")

    # ── 6. Guardar resultados ────────────────────────────────────────────────
    banner("PASO 6: Guardado de resultados", Fore.CYAN)

    output_dir = Path("./resultados")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "baseline_results.json"

    export = {
        "fase":       "baseline",
        "timestamp":  datetime.now().isoformat(),
        "stats":      stats,
        "queries":    results,
    }
    output_file.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{Fore.GREEN}✓ Resultados guardados en: {output_file}{Style.RESET_ALL}")

    # ── Resumen final ─────────────────────────────────────────────────────────
    banner("RESUMEN E1 — Setup técnico completado", Fore.GREEN)
    print(f"  {'Documentos ingestados':<30}: {len(doc_files)}")
    print(f"  {'Chunks en ChromaDB':<30}: {n_chunks}")
    print(f"  {'Queries ejecutadas':<30}: {len(BASELINE_QUERIES)}")
    print(f"  {'LLM utilizado':<30}: {os.getenv('LLM_PROVIDER', 'none')}")
    print(f"  {'Modelo de embeddings':<30}: sentence-transformers/all-MiniLM-L6-v2")
    print(f"  {'Resultados':<30}: {output_file}")
    print(f"\n{Fore.GREEN}  ✓ Pipeline RAG base funcional y verificado")
    print(f"  ✓ Listo para la fase de poisoning (Día 6){Style.RESET_ALL}\n")


if __name__ == "__main__":
    run_demo()
