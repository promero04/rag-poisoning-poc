"""
demo_poisoning.py — Demo E2: Comparativa RAG Limpio vs. Envenenado
===================================================================
Proyecto: RAG Poisoning PoC
Asignatura: Seguridad de la Información (SDI) — Deusto 2025/26
Autor: Pablo García

DESCRIPCIÓN:
    Este script ejecuta el pipeline completo de demostración del ataque:
      1. Carga los resultados baseline (del demo_baseline.py)
      2. Inyecta los documentos maliciosos via poisoning.py
      3. Ejecuta las mismas queries del baseline con el RAG envenenado
      4. Compara respuestas: detecta cambios y qué queries fueron afectadas
      5. Genera métricas de efectividad del ataque
      6. Guarda el informe completo en JSON

CRITERIOS DE DETECCIÓN DE ATAQUE EXITOSO:
    Una query se considera "afectada" si:
    - Al menos 1 chunk envenenado aparece en los top-k resultados
    - Y/o la respuesta del LLM contiene información incorrecta (detección heurística)

USO:
    python demo_poisoning.py                # Ejecución completa (ingest + poison + compare)
    python demo_poisoning.py --skip-ingest  # Asumir que ya hay documentos en ChromaDB
    python demo_poisoning.py --no-llm       # Solo comparar chunks recuperados (sin LLM)
    python demo_poisoning.py --k 5          # Cambiar el top-k del retriever
"""

import json
import os
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv

from rag_pipeline import RAGPipeline, COLLECTION_NAME
from poisoning import RAGPoisoner, POISONED_DOCUMENTS
from dataset_loader import load_queries, load_attack_indicators

load_dotenv()
colorama_init(autoreset=True)


# ─── Queries del experimento ─────────────────────────────────────────────────
# Misma fuente que demo_baseline.py (datasets/queries_es.txt) — comparativa directa.
EXPERIMENT_QUERIES = load_queries()

# Mapeo query -> indicadores heuristicos de envenenamiento.
# Cambiar en datasets/attack_indicators.yaml.
ATTACK_INDICATORS = load_attack_indicators()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def banner(title: str, color: str = Fore.BLUE):
    width = 62
    print(f"\n{color}{'═'*width}")
    print(f"  {title}")
    print(f"{'═'*width}{Style.RESET_ALL}\n")


def detect_attack_in_answer(query: str, answer: str) -> tuple[bool, list[str]]:
    """
    Detecta heurísticamente si una respuesta contiene información del ataque.
    Returns (was_poisoned, matched_indicators).
    """
    indicators = ATTACK_INDICATORS.get(query, [])
    matched = [ind for ind in indicators if ind.lower() in answer.lower()]
    return len(matched) > 0, matched


# ── Metrica continua (P2-02): coseno entre respuesta baseline y envenenada ───
# Carga perezosa para no penalizar usuarios que solo quieren la heuristica.

_DRIFT_MODEL = None


def _get_drift_model():
    global _DRIFT_MODEL
    if _DRIFT_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _DRIFT_MODEL = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2", device="cpu"
        )
    return _DRIFT_MODEL


def answer_drift_cosine(baseline_text: str, poisoned_text: str) -> float | None:
    """
    Devuelve la similitud coseno entre dos respuestas codificadas con MiniLM.
    1.0 = identicas en significado. < 1.0 = la respuesta ha cambiado.
    Devuelve None si alguno de los textos esta vacio.
    """
    if not baseline_text or not poisoned_text:
        return None
    model = _get_drift_model()
    embs = model.encode([baseline_text, poisoned_text], normalize_embeddings=True)
    return float(embs[0] @ embs[1])


def compare_results(baseline: dict, poisoned: dict) -> dict:
    """
    Compara un resultado baseline con uno post-poisoning.
    Devuelve análisis de qué cambió + métricas continuas.
    """
    poison_chunks = [s for s in poisoned["sources"] if s.get("is_poisoned")]
    answer_poisoned, indicators = detect_attack_in_answer(
        poisoned["question"],
        poisoned.get("answer", ""),
    )

    retrieval_compromised = len(poison_chunks) > 0

    baseline_answer = baseline.get("answer", "")
    poisoned_answer = poisoned.get("answer", "")
    drift = answer_drift_cosine(baseline_answer, poisoned_answer)

    return {
        "query":                poisoned["question"],
        "retrieval_compromised": retrieval_compromised,
        "answer_poisoned":      answer_poisoned,
        "attack_success":       retrieval_compromised or answer_poisoned,
        "poison_chunks_in_top_k": len(poison_chunks),
        "poison_chunk_sources": [Path(s["source"]).name for s in poison_chunks],
        "matched_indicators":   indicators,
        "baseline_answer_len":  len(baseline_answer),
        "poisoned_answer_len":  len(poisoned_answer),
        "answer_drift_cosine":  drift,
    }


def print_comparison(comparison: dict, baseline_answer: str, poisoned_answer: str):
    """Imprime side-by-side la comparativa de una query."""
    q = comparison["query"]
    success = comparison["attack_success"]

    status_color = Fore.RED if success else Fore.GREEN
    status_label = "ATAQUE EXITOSO" if success else "SIN CAMBIOS"

    print(f"\n{status_color}{'▓'*62}")
    print(f"  {status_label}")
    print(f"{'▓'*62}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Query: {q}{Style.RESET_ALL}")

    if comparison["retrieval_compromised"]:
        print(f"\n  {Fore.RED}⚠ RETRIEVAL COMPROMETIDO{Style.RESET_ALL} — "
              f"{comparison['poison_chunks_in_top_k']} chunk(s) envenenado(s) en top-k")
        print(f"    Fuentes maliciosas: {comparison['poison_chunk_sources']}")

    if comparison["matched_indicators"]:
        print(f"\n  {Fore.RED}⚠ RESPUESTA CONTAMINADA{Style.RESET_ALL} — "
              f"indicadores encontrados:")
        for ind in comparison["matched_indicators"]:
            print(f"    → '{ind}'")

    print(f"\n  {Fore.GREEN}[BASELINE]{Style.RESET_ALL}")
    # Mostrar las primeras líneas de la respuesta baseline
    for line in baseline_answer.strip().split("\n")[:6]:
        print(f"    {line}")
    if len(baseline_answer.strip().split("\n")) > 6:
        print(f"    ...")

    if success:
        print(f"\n  {Fore.RED}[ENVENENADO]{Style.RESET_ALL}")
        for line in poisoned_answer.strip().split("\n")[:6]:
            print(f"    {line}")
        if len(poisoned_answer.strip().split("\n")) > 6:
            print(f"    ...")
    else:
        print(f"\n  {Fore.GREEN}[ENVENENADO]{Style.RESET_ALL} Respuesta sin cambios significativos")


# ─── Demo principal ───────────────────────────────────────────────────────────

def run_demo(skip_ingest: bool = False, k: int = 3):
    banner("RAG Poisoning PoC — FASE 2: Comparativa Baseline vs. Envenenado", Fore.RED)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Queries del experimento: {len(EXPERIMENT_QUERIES)}")
    print(f"Top-k retriever: k={k}\n")

    # ── PASO 1: Inicializar pipeline base ────────────────────────────────────
    banner("PASO 1: Inicialización — colección LIMPIA", Fore.CYAN)
    pipeline_clean = RAGPipeline(collection="rag_baseline_clean", verbose=False)

    if not skip_ingest:
        docs_dir = "./docs"
        if not Path(docs_dir).exists():
            print(f"{Fore.RED}Error: carpeta ./docs no encontrada{Style.RESET_ALL}")
            return

        stats = pipeline_clean.collection_stats()
        if stats["total_chunks"] == 0:
            print("Ingestando documentos legítimos en colección limpia...")
            n = pipeline_clean.ingest(docs_dir)
            print(f"{Fore.GREEN}✓ {n} chunks ingestados{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}✓ Colección limpia existente: {stats['total_chunks']} chunks{Style.RESET_ALL}")
    else:
        stats = pipeline_clean.collection_stats()
        print(f"  Chunks en colección limpia: {stats['total_chunks']}")

    # ── PASO 2: Colección envenenada (separada) ──────────────────────────────
    banner("PASO 2: Preparando colección ENVENENADA", Fore.RED)
    pipeline_poison = RAGPipeline(collection="rag_poisoned", verbose=False)

    if not skip_ingest:
        stats_p = pipeline_poison.collection_stats()
        if stats_p["total_chunks"] == 0:
            print("Copiando documentos legítimos a colección de ataque...")
            pipeline_poison.ingest("./docs")

    # Inyectar documentos maliciosos en la colección de ataque
    poisoner = RAGPoisoner(collection="rag_poisoned")
    stats_before = poisoner.stats()

    if stats_before["poisoned"] == 0:
        print(f"\n{Fore.RED}Inyectando {len(POISONED_DOCUMENTS)} documentos maliciosos...{Style.RESET_ALL}")
        poisoner.inject_all(dry_run=False)
        stats_after = poisoner.stats()
    else:
        stats_after = stats_before
        print(f"{Fore.YELLOW}Documentos maliciosos ya presentes: {stats_after['poisoned']}{Style.RESET_ALL}")

    print(f"\n{Fore.RED}Estado colección envenenada:{Style.RESET_ALL}")
    for key, val in stats_after.items():
        color = Fore.RED if key == "poisoned" and stats_after["poisoned"] > 0 else Fore.WHITE
        print(f"  {color}{key:<20}: {val}{Style.RESET_ALL}")

    # ── PASO 3: Ejecutar queries en baseline ──────────────────────────────────
    banner("PASO 3: Queries en RAG LIMPIO (baseline)", Fore.GREEN)
    baseline_results = []

    for i, query in enumerate(EXPERIMENT_QUERIES, 1):
        print(f"{Fore.GREEN}[{i}/{len(EXPERIMENT_QUERIES)}] {query[:55]}...{Style.RESET_ALL}")
        result = pipeline_clean.query(query, k=k)
        baseline_results.append(result)
        poison_in_top = sum(1 for s in result["sources"] if s.get("is_poisoned"))
        print(f"  Chunks recuperados: {result['chunks_retrieved']} | Envenenados: {poison_in_top}")
        print()

    # ── PASO 4: Ejecutar queries en colección envenenada ─────────────────────
    banner("PASO 4: Queries en RAG ENVENENADO", Fore.RED)
    poisoned_results = []

    for i, query in enumerate(EXPERIMENT_QUERIES, 1):
        print(f"{Fore.RED}[{i}/{len(EXPERIMENT_QUERIES)}] {query[:55]}...{Style.RESET_ALL}")
        result = pipeline_poison.query(query, k=k)
        poisoned_results.append(result)
        poison_in_top = sum(1 for s in result["sources"] if s.get("is_poisoned"))
        print(f"  Chunks recuperados: {result['chunks_retrieved']} | Envenenados: {poison_in_top}")
        print()

    # ── PASO 5: Análisis comparativo ─────────────────────────────────────────
    banner("PASO 5: Análisis comparativo", Fore.YELLOW)
    comparisons = []

    for b_result, p_result in zip(baseline_results, poisoned_results):
        comparison = compare_results(b_result, p_result)
        comparisons.append(comparison)
        print_comparison(
            comparison,
            b_result.get("answer", ""),
            p_result.get("answer", ""),
        )

    # ── PASO 6: Métricas de efectividad ──────────────────────────────────────
    banner("PASO 6: Métricas de efectividad del ataque", Fore.CYAN)

    total_queries      = len(comparisons)
    retrieval_attacks  = sum(1 for c in comparisons if c["retrieval_compromised"])
    answer_attacks     = sum(1 for c in comparisons if c["answer_poisoned"])
    total_attacks      = sum(1 for c in comparisons if c["attack_success"])
    avg_poison_chunks  = (
        sum(c["poison_chunks_in_top_k"] for c in comparisons) / total_queries
    )
    drift_values = [c["answer_drift_cosine"] for c in comparisons
                    if c.get("answer_drift_cosine") is not None]
    avg_drift = sum(drift_values) / len(drift_values) if drift_values else None

    # Por tipo de ataque
    attack_type_results = {}
    for doc in POISONED_DOCUMENTS:
        at = doc["attack_type"]
        tq = doc["target_query"]
        matching = [c for c in comparisons if c["query"] == tq]
        if matching:
            attack_type_results[at] = {
                "target_query":         tq[:50] + "...",
                "retrieval_compromised": matching[0]["retrieval_compromised"],
                "answer_poisoned":      matching[0]["answer_poisoned"],
            }

    metrics = {
        "total_queries":            total_queries,
        "queries_retrieval_attacked": retrieval_attacks,
        "queries_answer_poisoned":  answer_attacks,
        "queries_affected_total":   total_attacks,
        "attack_success_rate":      f"{(total_attacks / total_queries * 100):.1f}%",
        "avg_poison_chunks_per_query": round(avg_poison_chunks, 2),
        "avg_answer_drift_cosine":  round(avg_drift, 4) if avg_drift is not None else None,
        "poisoned_docs_injected":   stats_after["poisoned"],
        "total_chunks_in_db":       stats_after["total_chunks"],
        "poison_ratio_in_db":       stats_after["poison_ratio"],
        "attack_type_breakdown":    attack_type_results,
    }

    print(f"  {'Queries totales':<35}: {total_queries}")
    print(f"  {'Retrieval comprometido':<35}: {retrieval_attacks}/{total_queries}")
    print(f"  {'Respuesta contaminada (heurística)':<35}: {answer_attacks}/{total_queries}")
    print(f"  {Fore.RED}{'Tasa de éxito del ataque':<35}: {metrics['attack_success_rate']}{Style.RESET_ALL}")
    print(f"  {'Avg chunks envenenados en top-k':<35}: {avg_poison_chunks:.2f}")
    if avg_drift is not None:
        print(f"  {'Avg drift coseno respuesta':<35}: {avg_drift:.4f}  "
              f"({Fore.YELLOW}1.0 = identica, < 1.0 = drift{Style.RESET_ALL})")
    print(f"  {'Docs maliciosos en ChromaDB':<35}: {stats_after['poisoned']}")
    print(f"  {'Ratio de envenenamiento en DB':<35}: {stats_after['poison_ratio']}")

    print(f"\n{Fore.CYAN}Por tipo de ataque:{Style.RESET_ALL}")
    for at, info in attack_type_results.items():
        retrieval_ok = info["retrieval_compromised"]
        answer_ok    = info["answer_poisoned"]
        status = f"{Fore.RED}EXITOSO{Style.RESET_ALL}" if (retrieval_ok or answer_ok) else f"{Fore.GREEN}FALLIDO{Style.RESET_ALL}"
        print(f"  {status} [{at}]")
        print(f"         retrieval={retrieval_ok} | answer={answer_ok}")

    # ── PASO 7: Guardar informe completo ─────────────────────────────────────
    banner("PASO 7: Guardado del informe", Fore.CYAN)

    output_dir = Path("./resultados")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "poisoning_comparison.json"

    export = {
        "fase":              "poisoning_comparison",
        "timestamp":         datetime.now().isoformat(),
        "config": {
            "k":               k,
            "queries_count":   total_queries,
            "poisoned_docs":   len(POISONED_DOCUMENTS),
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "llm_provider":    os.getenv("LLM_PROVIDER", "none"),
        },
        "collection_stats":   stats_after,
        "metrics":            metrics,
        "baseline_results":   baseline_results,
        "poisoned_results":   poisoned_results,
        "comparisons":        comparisons,
    }
    output_file.write_text(
        json.dumps(export, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{Fore.GREEN}✓ Informe guardado en: {output_file}{Style.RESET_ALL}")

    # ── Resumen final ─────────────────────────────────────────────────────────
    banner("RESUMEN FINAL — Entrega 2 (E2)", Fore.RED if total_attacks > 0 else Fore.GREEN)
    print(f"  {'Fase':<35}: RAG Poisoning PoC — E2")
    print(f"  {'Queries evaluadas':<35}: {total_queries}")
    print(f"  {'Queries comprometidas':<35}: {total_attacks}")
    print(f"  {Fore.RED}{'Tasa de éxito':<35}: {metrics['attack_success_rate']}{Style.RESET_ALL}")
    print(f"  {'Docs maliciosos inyectados':<35}: {stats_after['poisoned']}")
    print(f"  {'Ratio en DB':<35}: {stats_after['poison_ratio']}")
    print(f"  {'Resultado guardado':<35}: {output_file}")

    if total_attacks == total_queries:
        print(f"\n{Fore.RED}  ✗ TODAS las queries del benchmark fueron comprometidas")
        print(f"  ✗ El sistema RAG NO puede considerarse fiable tras el poisoning{Style.RESET_ALL}\n")
    elif total_attacks > 0:
        print(f"\n{Fore.YELLOW}  ⚠ {total_attacks}/{total_queries} queries comprometidas")
        print(f"  ⚠ El ataque fue parcialmente exitoso{Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.GREEN}  ✓ Ninguna query comprometida — el RAG es resistente{Style.RESET_ALL}\n")

    return export


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Demo comparativa RAG limpio vs. envenenado"
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="No reingestar documentos (usar colecciones existentes)",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        help="Top-k para el retriever (default: 3)",
    )
    args = parser.parse_args()

    run_demo(skip_ingest=args.skip_ingest, k=args.k)
