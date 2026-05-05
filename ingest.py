"""
ingest.py — Script de ingestión de documentos en ChromaDB
==========================================================
Uso:
    python ingest.py                        # Carga ./docs/ (por defecto)
    python ingest.py --docs ./mis_docs      # Carpeta personalizada
    python ingest.py --clear                # Limpia la colección antes de ingestar
    python ingest.py --stats                # Solo muestra estadísticas
"""

import argparse
import sys
from rag_pipeline import RAGPipeline
from colorama import Fore, Style


def main():
    parser = argparse.ArgumentParser(
        description="Ingestar documentos en ChromaDB para el PoC RAG Poisoning"
    )
    parser.add_argument("--docs",   default="./docs", help="Directorio de documentos")
    parser.add_argument("--clear",  action="store_true", help="Vaciar colección antes de ingestar")
    parser.add_argument("--stats",  action="store_true", help="Mostrar estadísticas y salir")
    parser.add_argument("--collection", default=None, help="Nombre de colección (default: del .env)")
    args = parser.parse_args()

    print(f"\n{'═'*60}")
    print(f"  RAG Poisoning PoC — Ingestión de documentos")
    print(f"{'═'*60}\n")

    # Inicializar pipeline
    kwargs = {}
    if args.collection:
        kwargs["collection"] = args.collection

    pipeline = RAGPipeline(**kwargs)

    if args.stats:
        stats = pipeline.collection_stats()
        print(f"\n{Fore.CYAN}Estadísticas de la colección:{Style.RESET_ALL}")
        for k, v in stats.items():
            print(f"  {k:<20}: {v}")
        return

    if args.clear:
        print(f"\n{Fore.YELLOW}Limpiando colección...{Style.RESET_ALL}")
        pipeline.clear_collection()

    # Ingestar
    try:
        n_chunks = pipeline.ingest(args.docs)
        print(f"\n{Fore.GREEN}✓ Ingestión completada: {n_chunks} chunks en ChromaDB{Style.RESET_ALL}")

        # Mostrar estadísticas finales
        stats = pipeline.collection_stats()
        print(f"\n{Fore.CYAN}Estado de la colección:{Style.RESET_ALL}")
        for k, v in stats.items():
            print(f"  {k:<20}: {v}")

    except FileNotFoundError as e:
        print(f"\n{Fore.RED}Error: {e}{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Error durante la ingestión: {e}{Style.RESET_ALL}")
        raise


if __name__ == "__main__":
    main()
