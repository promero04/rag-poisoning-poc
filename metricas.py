"""
metricas.py — Análisis de métricas del experimento RAG Poisoning
=================================================================
Proyecto: RAG Poisoning PoC
Asignatura: Seguridad de la Información (SDI) — Deusto 2025/26
Autor: Pablo García

DESCRIPCIÓN:
    Lee los JSON de resultados del experimento y produce:
    - Tabla de métricas por tipo de ataque
    - Análisis de posicionamiento de chunks (scores de similitud coseno)
    - Comparativa baseline vs envenenado por query
    - Resumen ejecutivo para el informe

USO:
    python metricas.py                          # Analizar todos los JSON en ./resultados/
    python metricas.py --file resultados/X.json # Analizar un JSON concreto
    python metricas.py --live                   # Ejecutar consultas de análisis en tiempo real
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

RESULTS_DIR = Path("./resultados")
PLOTS_DIR   = RESULTS_DIR / "plots"

# Tipos de ataque y sus etiquetas legibles
ATTACK_TYPE_LABELS = {
    "weak_passwords":      "Contraseñas débiles",
    "incident_suppression": "Supresión de incidentes",
    "access_escalation":   "Escalación de acceso",
    "key_rotation_bypass": "Bypass rotación de claves",
    "protocol_downgrade":  "Degradación de protocolo",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def banner(title: str, color: str = Fore.CYAN):
    width = 64
    print(f"\n{color}{'═'*width}")
    print(f"  {title}")
    print(f"{'═'*width}{Style.RESET_ALL}\n")


def cargar_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{Fore.RED}Error leyendo {path}: {e}{Style.RESET_ALL}")
        return None


# ─── Análisis ────────────────────────────────────────────────────────────────

def analizar_resultados(data: dict, k: Optional[int] = None) -> dict:
    """
    Extrae métricas completas de un resultado de experimento.
    Devuelve un dict con todas las métricas calculadas.
    """
    metrics      = data.get("metrics", {})
    comparisons  = data.get("comparisons", [])
    config       = data.get("config", {})
    col_stats    = data.get("collection_stats", {})
    baseline_r   = data.get("baseline_results", [])
    poisoned_r   = data.get("poisoned_results", [])

    k_val = k or config.get("k", "?")

    banner(f"Análisis de resultados — k={k_val}", Fore.CYAN)

    # ── 1. Métricas globales ──────────────────────────────────────────────────
    print(f"{Fore.CYAN}[MÉTRICAS GLOBALES]{Style.RESET_ALL}")
    total   = metrics.get("total_queries", 0)
    ret_att = metrics.get("queries_retrieval_attacked", 0)
    ans_att = metrics.get("queries_answer_poisoned", 0)
    total_s = metrics.get("queries_affected_total", 0)
    rate    = metrics.get("attack_success_rate", "N/A")
    avg_ch  = metrics.get("avg_poison_chunks_per_query", 0)

    print(f"  {'Queries evaluadas':<40}: {total}")
    print(f"  {'Retrieval comprometido':<40}: {ret_att}/{total} ({ret_att/total*100:.0f}%)" if total else "  N/A")
    print(f"  {'Respuesta contaminada (heurística)':<40}: {ans_att}/{total} ({ans_att/total*100:.0f}%)" if total else "  N/A")
    print(f"  {Fore.RED}{'Tasa de éxito total':<40}: {rate}{Style.RESET_ALL}")
    print(f"  {'Media chunks veneno en top-{}'.format(k_val):<40}: {avg_ch}")
    print(f"  {'Ratio de envenenamiento en DB':<40}: {col_stats.get('poison_ratio', 'N/A')}")
    print(f"  {'Chunks totales en ChromaDB':<40}: {col_stats.get('total_chunks', 'N/A')}")
    print(f"    → Legítimos: {col_stats.get('total_chunks', 0) - col_stats.get('poisoned', 0)}")
    print(f"    → Envenenados: {col_stats.get('poisoned', 0)}")

    # ── 2. Tabla por query ────────────────────────────────────────────────────
    print(f"\n{Fore.CYAN}[POR QUERY]{Style.RESET_ALL}")
    print(f"  {'#':<3} {'Query':<45} {'Retrieval':>12} {'Answer':>10} {'Chunks':>7}")
    print(f"  {'─'*3} {'─'*45} {'─'*12} {'─'*10} {'─'*7}")

    for i, c in enumerate(comparisons, 1):
        q_short = c["query"][:43] + ".." if len(c["query"]) > 43 else c["query"]
        ret_c   = Fore.RED + "COMPROMETIDO" + Style.RESET_ALL if c["retrieval_compromised"] else Fore.GREEN + "SEGURO      " + Style.RESET_ALL
        ans_c   = Fore.RED + "CONTAM." + Style.RESET_ALL if c["answer_poisoned"] else Fore.GREEN + "LIMPIO " + Style.RESET_ALL
        n_chunks = c.get("poison_chunks_in_top_k", 0)
        print(f"  {i:<3} {q_short:<45} {ret_c:>12} {ans_c:>10} {n_chunks:>7}")

    # ── 3. Por tipo de ataque ─────────────────────────────────────────────────
    print(f"\n{Fore.CYAN}[POR TIPO DE ATAQUE]{Style.RESET_ALL}")
    at_data = metrics.get("attack_type_breakdown", {})

    if at_data:
        print(f"  {'Tipo de ataque':<30} {'Etiqueta':<28} {'Retrieval':>12} {'Answer':>10}")
        print(f"  {'─'*30} {'─'*28} {'─'*12} {'─'*10}")
        for at_key, info in at_data.items():
            label = ATTACK_TYPE_LABELS.get(at_key, at_key)
            ret = (Fore.RED + "✗ SÍ" + Style.RESET_ALL) if info["retrieval_compromised"] else (Fore.GREEN + "✓ NO" + Style.RESET_ALL)
            ans = (Fore.RED + "✗ SÍ" + Style.RESET_ALL) if info["answer_poisoned"]        else (Fore.GREEN + "✓ NO" + Style.RESET_ALL)
            print(f"  {at_key:<30} {label:<28} {ret:>12} {ans:>10}")
    else:
        print(f"  {Fore.YELLOW}Sin desglose por tipo de ataque en este JSON{Style.RESET_ALL}")

    # ── 4. Análisis de similitud coseno ────────────────────────────────────────
    print(f"\n{Fore.CYAN}[ANÁLISIS DE SCORES]{Style.RESET_ALL}")
    print("  Comparativa de scores de similitud coseno (baseline vs envenenado):")
    print()

    for b, p in zip(baseline_r, poisoned_r):
        q = b.get("question", "")[:50]
        b_srcs = b.get("sources", [])
        p_srcs = p.get("sources", [])
        poison_srcs = [s for s in p_srcs if s.get("is_poisoned")]

        print(f"  Q: {q}")
        print(f"    Baseline  : {len(b_srcs)} chunks legítimos")
        print(f"    Envenenado: {len(p_srcs) - len(poison_srcs)} legítimos + "
              f"{Fore.RED}{len(poison_srcs)} envenenados{Style.RESET_ALL}")
        if poison_srcs:
            for ps in poison_srcs:
                src_name = Path(ps.get("source", "?")).name
                print(f"      {Fore.RED}→ [VENENO] {src_name}{Style.RESET_ALL}")
        print()

    # ── 5. Indicadores más frecuentes ─────────────────────────────────────────
    all_indicators: dict[str, int] = {}
    for c in comparisons:
        for ind in c.get("matched_indicators", []):
            all_indicators[ind] = all_indicators.get(ind, 0) + 1

    if all_indicators:
        print(f"{Fore.CYAN}[INDICADORES DE ATAQUE MÁS FRECUENTES]{Style.RESET_ALL}")
        for ind, count in sorted(all_indicators.items(), key=lambda x: -x[1]):
            print(f"  [{count}x] '{ind}'")

    # ── Resumen ejecutivo ──────────────────────────────────────────────────────
    resumen = {
        "k":                    k_val,
        "total_queries":        total,
        "retrieval_attacked":   ret_att,
        "answer_poisoned":      ans_att,
        "total_success":        total_s,
        "success_rate":         rate,
        "avg_poison_chunks":    avg_ch,
        "db_poison_ratio":      col_stats.get("poison_ratio", "N/A"),
        "attack_types_ok":      [at for at, info in at_data.items()
                                  if info["retrieval_compromised"] or info["answer_poisoned"]],
        "attack_types_fail":    [at for at, info in at_data.items()
                                  if not info["retrieval_compromised"] and not info["answer_poisoned"]],
    }

    return resumen


# ─── Graficos (P3-01) ────────────────────────────────────────────────────────

def generar_plots(data: dict, output_dir: Path = PLOTS_DIR, suffix: str = "") -> list[Path]:
    """
    Genera graficos PNG a partir de un resultado de demo_poisoning.

    Produce hasta 3 PNG:
      1. Tasa de exito retrieval/answer por query (barras agrupadas).
      2. Drift coseno por query (barras horizontales).
      3. Distribucion de scores de similitud baseline vs envenenado.

    Returns:
        Lista de rutas a los PNG generados.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # backend no interactivo, para entornos sin display
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"{Fore.YELLOW}matplotlib no esta instalado. "
              f"Anadelo con: pip install matplotlib{Style.RESET_ALL}")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    plots: list[Path] = []

    comparisons = data.get("comparisons", [])
    if not comparisons:
        print(f"{Fore.YELLOW}Sin comparisons en el JSON; no se generan plots.{Style.RESET_ALL}")
        return plots

    # Etiquetas cortas para el eje x
    def short(q: str, n: int = 28) -> str:
        return (q[: n - 1] + "…") if len(q) > n else q

    labels      = [short(c["query"]) for c in comparisons]
    retrieval   = [1 if c["retrieval_compromised"] else 0 for c in comparisons]
    answer      = [1 if c["answer_poisoned"] else 0 for c in comparisons]
    drift       = [c.get("answer_drift_cosine") for c in comparisons]

    # ── 1. Retrieval vs answer compromise por query ──
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(labels))
    width = 0.35
    ax.bar([i - width / 2 for i in x], retrieval, width,
           label="Retrieval comprometido", color="#d62728")
    ax.bar([i + width / 2 for i in x], answer, width,
           label="Respuesta contaminada (heuristica)", color="#ff7f0e")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["No", "Si"])
    ax.set_ylabel("Comprometido")
    ax.set_title("Exito del ataque por query")
    ax.legend()
    fig.tight_layout()
    p1 = output_dir / f"attack_per_query{suffix}.png"
    fig.savefig(p1, dpi=120)
    plt.close(fig)
    plots.append(p1)

    # ── 2. Drift coseno por query ──
    drift_vals = [d if d is not None else 0.0 for d in drift]
    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.barh(labels, drift_vals, color="#1f77b4")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Similitud coseno (baseline vs envenenada). 1.0 = identica.")
    ax.set_title("Drift semantico de la respuesta tras el envenenamiento")
    for bar, val in zip(bars, drift_vals):
        ax.text(min(val + 0.01, 0.99), bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", fontsize=8)
    fig.tight_layout()
    p2 = output_dir / f"answer_drift{suffix}.png"
    fig.savefig(p2, dpi=120)
    plt.close(fig)
    plots.append(p2)

    # ── 3. Distribucion de scores baseline vs envenenado ──
    baseline_scores: list[float] = []
    poisoned_legit_scores: list[float] = []
    poisoned_poison_scores: list[float] = []
    for b, p in zip(data.get("baseline_results", []), data.get("poisoned_results", [])):
        for s in b.get("sources", []):
            if s.get("similarity_score") is not None:
                baseline_scores.append(s["similarity_score"])
        for s in p.get("sources", []):
            score = s.get("similarity_score")
            if score is None:
                continue
            if s.get("is_poisoned"):
                poisoned_poison_scores.append(score)
            else:
                poisoned_legit_scores.append(score)

    if baseline_scores or poisoned_legit_scores or poisoned_poison_scores:
        fig, ax = plt.subplots(figsize=(8, 4))
        bins = 12
        if baseline_scores:
            ax.hist(baseline_scores, bins=bins, alpha=0.5,
                    label=f"Baseline legitimos (n={len(baseline_scores)})",
                    color="#2ca02c")
        if poisoned_legit_scores:
            ax.hist(poisoned_legit_scores, bins=bins, alpha=0.5,
                    label=f"Envenenado legitimos (n={len(poisoned_legit_scores)})",
                    color="#1f77b4")
        if poisoned_poison_scores:
            ax.hist(poisoned_poison_scores, bins=bins, alpha=0.7,
                    label=f"Envenenado maliciosos (n={len(poisoned_poison_scores)})",
                    color="#d62728")
        ax.set_xlabel("Score de similitud coseno")
        ax.set_ylabel("Frecuencia")
        ax.set_title("Distribucion de scores en top-k")
        ax.legend()
        fig.tight_layout()
        p3 = output_dir / f"score_distribution{suffix}.png"
        fig.savefig(p3, dpi=120)
        plt.close(fig)
        plots.append(p3)

    print(f"{Fore.GREEN}Plots generados: {len(plots)}{Style.RESET_ALL}")
    for p in plots:
        print(f"  -> {p}")
    return plots


def analisis_live():
    """
    Ejecuta consultas de similitud en tiempo real para ver el posicionamiento
    de los chunks en la colección envenenada.
    """
    banner("Análisis LIVE — Similitud coseno en colección envenenada", Fore.YELLOW)

    try:
        from rag_pipeline import RAGPipeline
        from poisoning import POISONED_DOCUMENTS
    except ImportError as e:
        print(f"{Fore.RED}Error al importar módulos: {e}{Style.RESET_ALL}")
        print("Ejecuta este script desde el directorio del código.")
        return

    pipeline = RAGPipeline(collection="rag_poisoned", verbose=False)
    queries = list({d["target_query"] for d in POISONED_DOCUMENTS})

    for query in queries:
        print(f"\n{Fore.YELLOW}Query: {query}{Style.RESET_ALL}")
        hits = pipeline.similarity_search(query, k=5)

        for rank, (doc, score) in enumerate(hits, 1):
            is_p    = doc.metadata.get("is_poisoned", False)
            color   = Fore.RED if is_p   else Fore.GREEN
            label   = "VENENO  " if is_p else "LEGÍTIMO"
            src     = Path(doc.metadata.get("source", "?")).name
            snippet = doc.page_content[:70].replace("\n", " ")
            print(f"  [{rank}] {color}[{label} score={score:.4f}]{Style.RESET_ALL} {src}")
            print(f"       {snippet}...")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Análisis de métricas del experimento RAG Poisoning"
    )
    parser.add_argument(
        "--file",
        default=None,
        help="JSON de resultados a analizar (default: todos en ./resultados/)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Ejecutar análisis de similitud en tiempo real",
    )
    parser.add_argument(
        "--plots",
        action="store_true",
        help="Generar graficos PNG en resultados/plots/",
    )
    args = parser.parse_args()

    if args.live:
        analisis_live()
        return

    if args.file:
        paths = [Path(args.file)]
    else:
        paths = sorted(RESULTS_DIR.glob("poisoning_comparison*.json"))
        if not paths:
            print(f"{Fore.YELLOW}No se encontraron resultados en {RESULTS_DIR}/")
            print(f"Ejecuta primero: python run_experiment.py{Style.RESET_ALL}")
            return

    resumenes = []
    for path in paths:
        data = cargar_json(path)
        if data:
            # Inferir k del nombre del archivo si es posible
            k = None
            stem = path.stem
            if "_k" in stem:
                try:
                    k = int(stem.split("_k")[-1])
                except ValueError:
                    pass
            resumen = analizar_resultados(data, k=k)
            resumenes.append(resumen)

            if args.plots:
                suffix = f"_k{k}" if k is not None else f"_{path.stem}"
                generar_plots(data, suffix=suffix)

    # Guardar resumen JSON
    if resumenes:
        out = RESULTS_DIR / "metricas_resumen.json"
        out.write_text(json.dumps(resumenes, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{Fore.GREEN}✓ Resumen de métricas guardado en: {out}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
