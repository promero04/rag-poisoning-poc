"""
run_experiment.py — Orquestador del experimento completo con captura de logs
=============================================================================
Proyecto: RAG Poisoning PoC
Asignatura: Seguridad de la Información (SDI) — Deusto 2025/26
Autor: Pablo García

DESCRIPCIÓN:
    Ejecuta el pipeline completo de demostración en múltiples configuraciones
    (k=3, k=5) y captura todo el output en archivos de log con timestamp.
    Genera además un resumen comparativo en Markdown para incluir en el informe.

USO:
    python run_experiment.py                 # Experimento completo k=3 y k=5
    python run_experiment.py --k 3           # Solo k=3
    python run_experiment.py --skip-ingest   # Asumir que los docs ya están indexados
    python run_experiment.py --report-only   # Generar informe desde resultados existentes
"""

import argparse
import json
import sys
import io
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

RESULTS_DIR = Path("./resultados")
LOGS_DIR    = Path("./logs")


# ─── Utilidades de captura de logs ───────────────────────────────────────────

class TeeOutput:
    """Duplica stdout: escribe en terminal Y en fichero simultáneamente."""

    def __init__(self, log_path: Path):
        self.terminal = sys.stdout
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(log_path, "w", encoding="utf-8")

    def write(self, message: str):
        self.terminal.write(message)
        # Strip ANSI color codes para el log file
        import re
        clean = re.sub(r'\x1b\[[0-9;]*m', '', message)
        self.log.write(clean)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


def banner(title: str, color: str = Fore.CYAN):
    width = 64
    print(f"\n{color}{'═'*width}")
    print(f"  {title}")
    print(f"{'═'*width}{Style.RESET_ALL}\n")


# ─── Generador de informe Markdown ───────────────────────────────────────────

def generar_informe_markdown(resultados_por_k: dict[int, dict]) -> str:
    """
    Genera la sección 8 (Resultados) del informe en Markdown,
    a partir de los resultados del experimento para cada valor de k.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Sección 8 — Resultados del Experimento",
        f"",
        f"*Generado automáticamente: {ts}*",
        f"",
        f"---",
        f"",
    ]

    for k, data in resultados_por_k.items():
        if not data:
            continue
        metrics   = data.get("metrics", {})
        comps     = data.get("comparisons", [])
        col_stats = data.get("collection_stats", {})

        lines += [
            f"## 8.{k // 2} Experimento con k={k}",
            f"",
            f"### Configuración del experimento",
            f"",
            f"| Parámetro | Valor |",
            f"|---|---|",
            f"| Modelo de embeddings | `sentence-transformers/all-MiniLM-L6-v2` |",
            f"| Vector store | ChromaDB (persistente, local) |",
            f"| Top-k retriever | k={k} |",
            f"| Documentos legítimos en corpus | {col_stats.get('total_chunks', 'N/A') - col_stats.get('poisoned', 0)} chunks |",
            f"| Documentos maliciosos inyectados | {col_stats.get('poisoned', 6)} chunks |",
            f"| Ratio de envenenamiento en DB | {col_stats.get('poison_ratio', 'N/A')} |",
            f"| Queries del benchmark | {metrics.get('total_queries', 5)} |",
            f"",
            f"### 8.{k // 2}.1 Resultados por query",
            f"",
            f"| # | Query | Retrieval comprometido | Respuesta envenenada | Chunks veneno en top-{k} | Indicadores detectados |",
            f"|---|---|:---:|:---:|:---:|---|",
        ]

        for i, c in enumerate(comps, 1):
            q_short = c["query"][:55] + ("..." if len(c["query"]) > 55 else "")
            retrieval = "✗ SÍ" if c["retrieval_compromised"] else "✓ NO"
            answer    = "✗ SÍ" if c["answer_poisoned"]       else "✓ NO"
            n_chunks  = c.get("poison_chunks_in_top_k", 0)
            indics    = ", ".join(f'`{x}`' for x in c.get("matched_indicators", [])[:3])
            if not indics:
                indics = "—"
            lines.append(
                f"| {i} | {q_short} | {retrieval} | {answer} | {n_chunks} | {indics} |"
            )

        lines += [
            f"",
            f"### 8.{k // 2}.2 Métricas de efectividad",
            f"",
            f"| Métrica | Valor |",
            f"|---|---|",
            f"| Queries con retrieval comprometido | "
            f"{metrics.get('queries_retrieval_attacked', '?')}/{metrics.get('total_queries', 5)} |",
            f"| Queries con respuesta contaminada (heurística) | "
            f"{metrics.get('queries_answer_poisoned', '?')}/{metrics.get('total_queries', 5)} |",
            f"| **Tasa de éxito total del ataque** | **{metrics.get('attack_success_rate', '?')}** |",
            f"| Media de chunks envenenados en top-{k} | {metrics.get('avg_poison_chunks_per_query', '?')} |",
            f"| Drift coseno medio (1.0 = idénticas) | {metrics.get('avg_answer_drift_cosine', 'N/A')} |",
            f"",
        ]

        # Tabla por tipo de ataque
        at_breakdown = metrics.get("attack_type_breakdown", {})
        if at_breakdown:
            lines += [
                f"### 8.{k // 2}.3 Efectividad por tipo de ataque",
                f"",
                f"| Tipo de ataque | Query objetivo | Retrieval OK | Answer OK | Estado |",
                f"|---|---|:---:|:---:|:---:|",
            ]
            for at, info in at_breakdown.items():
                ret = "✗" if info["retrieval_compromised"] else "✓"
                ans = "✗" if info["answer_poisoned"]       else "✓"
                estado = "**EXITOSO**" if (info["retrieval_compromised"] or info["answer_poisoned"]) else "Fallido"
                tq = info.get("target_query", "")[:45] + "..."
                lines.append(f"| `{at}` | {tq} | {ret} | {ans} | {estado} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Tabla resumen comparativa k=3 vs k=5
    if len(resultados_por_k) > 1:
        lines += [
            f"## 8.X Comparativa k=3 vs k=5",
            f"",
            f"| Métrica | k=3 | k=5 |",
            f"|---|:---:|:---:|",
        ]
        ks = sorted(resultados_por_k.keys())
        for metric_key, label in [
            ("queries_retrieval_attacked", "Queries con retrieval comprometido"),
            ("queries_answer_poisoned",    "Queries con respuesta contaminada"),
            ("attack_success_rate",        "**Tasa de éxito total**"),
            ("avg_poison_chunks_per_query","Media chunks veneno en top-k"),
        ]:
            vals = []
            for k in ks:
                m = resultados_por_k[k].get("metrics", {})
                vals.append(str(m.get(metric_key, "N/A")))
            lines.append(f"| {label} | {' | '.join(vals)} |")

        lines += [
            "",
            "> **Observación:** Un k mayor dilata el efecto del ataque al incorporar más chunks "
            "legítimos al contexto. Sin embargo, al usar amplificación semántica (2 documentos "
            "por query objetivo), el ataque mantiene alta efectividad incluso con k=5.",
            "",
            "---",
            "",
        ]

    return "\n".join(lines)


# ─── Ejecución del experimento ────────────────────────────────────────────────

def ejecutar_con_k(k: int, skip_ingest: bool) -> dict | None:
    """Ejecuta demo_poisoning.run_demo() con top-k=k y devuelve los resultados."""
    banner(f"EXPERIMENTO — top-k = {k}", Fore.RED)

    try:
        from demo_poisoning import run_demo
        resultado = run_demo(skip_ingest=skip_ingest, k=k)
        return resultado
    except Exception as e:
        print(f"{Fore.RED}Error en experimento k={k}: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return None


def cargar_resultados_existentes(k: int) -> dict | None:
    """Carga resultados de un experimento previo desde JSON."""
    path = RESULTS_DIR / f"poisoning_comparison_k{k}.json"
    if not path.exists():
        path = RESULTS_DIR / "poisoning_comparison.json"
    if path.exists():
        print(f"{Fore.CYAN}Cargando resultados existentes: {path}{Style.RESET_ALL}")
        return json.loads(path.read_text(encoding="utf-8"))
    return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Orquestador del experimento RAG Poisoning con captura de logs"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="Ejecutar solo con este valor de k (default: k=3 y k=5)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="No reingestar documentos (usar colecciones existentes)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Solo generar el informe a partir de resultados JSON existentes",
    )
    args = parser.parse_args()

    k_values = [args.k] if args.k else [3, 5]

    RESULTS_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"experiment_{ts_str}.log"

    # Configurar tee output
    tee = TeeOutput(log_path)
    sys.stdout = tee

    banner(f"RAG Poisoning — Experimento completo ({ts_str})", Fore.RED)
    print(f"  Valores de k      : {k_values}")
    print(f"  Skip ingest       : {args.skip_ingest}")
    print(f"  Report only       : {args.report_only}")
    print(f"  Log file          : {log_path}")
    print(f"  Timestamp         : {datetime.now().isoformat()}")

    # ── Ejecutar o cargar experimentos ──────────────────────────────────────
    resultados_por_k: dict[int, dict] = {}

    for k in k_values:
        if args.report_only:
            data = cargar_resultados_existentes(k)
        else:
            data = ejecutar_con_k(k=k, skip_ingest=args.skip_ingest)
            # Guardar con sufijo _k{k} para distinguir configuraciones
            if data:
                out_k = RESULTS_DIR / f"poisoning_comparison_k{k}.json"
                out_k.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"\n{Fore.GREEN}✓ Resultados k={k} guardados en: {out_k}{Style.RESET_ALL}")

        if data:
            resultados_por_k[k] = data
        else:
            print(f"{Fore.YELLOW}  Sin datos para k={k} — se omite en el informe{Style.RESET_ALL}")

    # ── Generar informe Markdown ─────────────────────────────────────────────
    sys.stdout = tee.terminal  # restaurar stdout antes de escribir el md
    tee.close()

    if resultados_por_k:
        informe_md = generar_informe_markdown(resultados_por_k)
        informe_path = RESULTS_DIR / "seccion8_resultados_generado.md"
        informe_path.write_text(informe_md, encoding="utf-8")
        print(f"\n{Fore.GREEN}✓ Informe Markdown generado: {informe_path}{Style.RESET_ALL}")

    print(f"\n{Fore.GREEN}✓ Log completo guardado en: {log_path}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Archivos generados:")
    for p in sorted(RESULTS_DIR.iterdir()) if RESULTS_DIR.exists() else []:
        print(f"  {p}")
    for p in sorted(LOGS_DIR.iterdir()) if LOGS_DIR.exists() else []:
        print(f"  {p}")


if __name__ == "__main__":
    main()
