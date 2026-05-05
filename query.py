"""
query.py — CLI interactivo para consultar el RAG
=================================================
Uso:
    python query.py                         # Modo interactivo
    python query.py -q "¿Cuál es la política de contraseñas?"  # Query directa
    python query.py --batch preguntas.txt   # Batch de queries desde fichero
    python query.py --scores -q "..."       # Mostrar scores de similitud
"""

import argparse
import json
import sys
from pathlib import Path
from colorama import Fore, Style, init as colorama_init

from rag_pipeline import RAGPipeline

colorama_init(autoreset=True)


def print_result(result: dict, show_sources: bool = True):
    """Formatea e imprime el resultado de una query."""
    print(f"\n{Fore.YELLOW}{'─'*60}")
    print(f"PREGUNTA: {result['question']}")
    print(f"{'─'*60}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}RESPUESTA:{Style.RESET_ALL}")
    print(result["answer"])

    if show_sources:
        print(f"\n{Fore.WHITE}FUENTES RECUPERADAS ({result['chunks_retrieved']} chunks):{Style.RESET_ALL}")
        for i, src in enumerate(result["sources"]):
            tag = f"{Fore.RED}[ENVENENADO]" if src["is_poisoned"] else f"{Fore.GREEN}[LEGÍTIMO]"
            print(f"  {i+1}. {tag} {Path(src['source']).name} {Style.RESET_ALL}| id={src['chunk_id']}")
            print(f"     → {src['snippet']}")


def interactive_mode(pipeline: RAGPipeline):
    """Loop interactivo de consultas."""
    print(f"\n{Fore.GREEN}╔══════════════════════════════════════════╗")
    print(f"║  RAG Poisoning PoC — Modo interactivo    ║")
    print(f"║  Escribe 'salir' o 'exit' para terminar  ║")
    print(f"╚══════════════════════════════════════════╝{Style.RESET_ALL}\n")

    stats = pipeline.collection_stats()
    print(f"Colección: {stats['collection']} | Chunks: {stats['total_chunks']}\n")

    while True:
        try:
            question = input(f"{Fore.YELLOW}Pregunta> {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo...")
            break

        if not question:
            continue

        if question.lower() in ("salir", "exit", "quit"):
            print("¡Hasta luego!")
            break

        result = pipeline.query(question)
        print_result(result)


def batch_mode(pipeline: RAGPipeline, filepath: str) -> list:
    """Procesa un fichero de preguntas (una por línea)."""
    questions = [
        line.strip()
        for line in Path(filepath).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    print(f"\n{Fore.CYAN}Procesando {len(questions)} preguntas en batch...{Style.RESET_ALL}")
    results = []

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}]")
        result = pipeline.query(q)
        print_result(result)
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Consultar el RAG PoC")
    parser.add_argument("-q", "--question",  help="Query directa (single shot)")
    parser.add_argument("--batch",           help="Fichero con queries (una por línea)")
    parser.add_argument("--scores",          action="store_true", help="Mostrar scores de similitud")
    parser.add_argument("--output",          help="Guardar resultados en JSON")
    parser.add_argument("--collection",      default=None)
    args = parser.parse_args()

    kwargs = {}
    if args.collection:
        kwargs["collection"] = args.collection

    pipeline = RAGPipeline(**kwargs)

    # Verificar que hay datos
    stats = pipeline.collection_stats()
    if stats["total_chunks"] == 0:
        print(f"\n{Fore.RED}La colección está vacía. Ejecuta primero: python ingest.py{Style.RESET_ALL}")
        sys.exit(1)

    results = []

    if args.question:
        if args.scores:
            # Mostrar scores raw de similitud
            hits = pipeline.similarity_search(args.question)
            print(f"\n{Fore.CYAN}Similitud para: '{args.question}'{Style.RESET_ALL}")
            for doc, score in hits:
                poison = "[ENVENENADO]" if doc.metadata.get("is_poisoned") else "[LEGÍTIMO]"
                print(f"  score={score:.4f} {poison} {Path(doc.metadata.get('source','')).name}")
                print(f"    → {doc.page_content[:100]}...")
        else:
            result = pipeline.query(args.question)
            print_result(result)
            results = [result]

    elif args.batch:
        results = batch_mode(pipeline, args.batch)

    else:
        interactive_mode(pipeline)

    if args.output and results:
        Path(args.output).write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n{Fore.GREEN}Resultados guardados en: {args.output}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
