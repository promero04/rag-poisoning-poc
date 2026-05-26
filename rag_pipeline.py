"""
rag_pipeline.py — Pipeline RAG base (fase LIMPIA / baseline)
=============================================================
Proyecto: RAG Poisoning PoC
Asignatura: Seguridad de la Información (SDI) — Deusto 2025/26
Autores: Pablo Romero, Iker Diez y Jacqueline Furelos

Implementa el pipeline RAG completo:
  1. Ingestión: carga documentos → divide en chunks → genera embeddings → almacena en ChromaDB
  2. Consulta: recibe pregunta → recupera chunks relevantes → genera respuesta con LLM

Este módulo actúa como baseline LIMPIO. El script de poisoning (poisoning.py)
inyectará documentos maliciosos en la misma ChromaDB para demostrar el ataque.
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from colorama import Fore, Style, init as colorama_init

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from defenses import get_defense_from_env

load_dotenv()
colorama_init(autoreset=True)

# ─── Configuración ──────────────────────────────────────────────────────────

EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PERSIST   = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME  = os.getenv("CHROMA_COLLECTION", "rag_baseline")
RETRIEVAL_K      = int(os.getenv("RETRIEVAL_K", "3"))
CHUNK_SIZE       = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP    = int(os.getenv("CHUNK_OVERLAP", "50"))
LLM_PROVIDER     = os.getenv("LLM_PROVIDER", "ollama").lower()

# ─── Prompt template ────────────────────────────────────────────────────────

PROMPT_TEMPLATE = ChatPromptTemplate.from_template("""
Eres un asistente de seguridad corporativa. Responde la pregunta usando ÚNICAMENTE
la información proporcionada en el contexto. Si el contexto no contiene la respuesta,
di explícitamente que no dispones de esa información.

Contexto:
{context}

Pregunta: {question}

Respuesta:""")


# ─── Helpers ────────────────────────────────────────────────────────────────

VALID_LLM_PROVIDERS = {"ollama", "openai", "none"}


def _ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Comprueba si el servidor Ollama responde en /api/tags."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _get_llm():
    """
    Inicializa el LLM según LLM_PROVIDER en .env, con validaciones claras.

    Si el proveedor configurado no está disponible (Ollama caído, API key
    placeholder), imprime un mensaje accionable y cae a modo 'none'
    (solo recuperación) en vez de fallar a la primera query.
    """
    provider = LLM_PROVIDER

    if provider not in VALID_LLM_PROVIDERS:
        print(
            f"{Fore.YELLOW}[LLM] Valor LLM_PROVIDER='{provider}' no reconocido. "
            f"Valores válidos: {sorted(VALID_LLM_PROVIDERS)}. Cayendo a 'none'.{Style.RESET_ALL}"
        )
        provider = "none"

    if provider == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        if not _ollama_reachable(base):
            print(
                f"{Fore.YELLOW}[LLM] Ollama no responde en {base}. "
                f"Arranca el servidor (`ollama serve`) y descarga el modelo "
                f"(`ollama pull {model}`), o cambia LLM_PROVIDER a 'openai' / 'none'.{Style.RESET_ALL}"
            )
            print(f"{Fore.YELLOW}[LLM] Continuando en modo 'none' (solo recuperación, sin generación).{Style.RESET_ALL}")
            return None
        from langchain_ollama import ChatOllama
        print(f"{Fore.CYAN}[LLM] Usando Ollama → {model} en {base}{Style.RESET_ALL}")
        return ChatOllama(model=model, base_url=base, temperature=0)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-...") or api_key == "sk-":
            print(
                f"{Fore.YELLOW}[LLM] OPENAI_API_KEY no configurada (o es el placeholder 'sk-...'). "
                f"Define una clave real en .env o cambia LLM_PROVIDER a 'ollama' / 'none'.{Style.RESET_ALL}"
            )
            print(f"{Fore.YELLOW}[LLM] Continuando en modo 'none' (solo recuperación, sin generación).{Style.RESET_ALL}")
            return None
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        print(f"{Fore.CYAN}[LLM] Usando OpenAI → {model}{Style.RESET_ALL}")
        return ChatOpenAI(model=model, temperature=0)

    # provider == "none"
    print(f"{Fore.YELLOW}[LLM] Modo 'none' — se mostrará el contexto recuperado sin generación{Style.RESET_ALL}")
    return None


def _doc_fingerprint(content: str) -> str:
    """Hash MD5 corto del contenido del documento para detectar duplicados."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


# ─── Clase principal ────────────────────────────────────────────────────────

class RAGPipeline:
    """
    Pipeline RAG completo sobre ChromaDB.

    Uso básico:
        pipeline = RAGPipeline()
        pipeline.ingest("./docs")
        respuesta = pipeline.query("¿Cuál es la política de contraseñas?")
    """

    def __init__(self, collection: str = COLLECTION_NAME, verbose: bool = True):
        self.collection  = collection
        self.verbose     = verbose
        self._log(f"Iniciando RAGPipeline | colección='{collection}'")

        # Modelo de embeddings local (sentence-transformers, no requiere API)
        self._log(f"Cargando modelo de embeddings: {EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        # ChromaDB persistente
        self.vectorstore = Chroma(
            collection_name=self.collection,
            embedding_function=self.embeddings,
            persist_directory=CHROMA_PERSIST,
        )

        # Defensa opcional contra prompt injection (P2-01).
        # Se activa via DEFENSE_ENABLED=true en .env.
        self.defense = get_defense_from_env()
        if self.defense is not None:
            self._log(f"Defensa activada: {type(self.defense).__name__}", color=Fore.MAGENTA)

        # LLM
        self.llm = _get_llm()

        # Cadena de GENERACION (recibe context+question ya formateados).
        # No incluimos el retriever en la cadena para poder obtener scores
        # de similitud coseno por chunk y aplicar defensas opcionales antes
        # de formatear el contexto.
        if self.llm:
            self._gen_chain = PROMPT_TEMPLATE | self.llm | StrOutputParser()
        else:
            self._gen_chain = None

        self._log("Pipeline listo ✓", color=Fore.GREEN)

    # ── Ingestión ──────────────────────────────────────────────────────────

    def ingest(self, docs_dir: str = "./docs", glob: str = "**/*.txt") -> int:
        """
        Carga todos los documentos del directorio, los divide en chunks,
        genera embeddings y los almacena en ChromaDB.

        Returns:
            Número de chunks almacenados.
        """
        docs_path = Path(docs_dir)
        if not docs_path.exists():
            raise FileNotFoundError(f"Directorio de documentos no encontrado: {docs_dir}")

        self._log(f"Cargando documentos desde: {docs_dir}")

        # 1. Cargar documentos de texto
        loader = DirectoryLoader(
            str(docs_path),
            glob=glob,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=False,
        )
        raw_docs = loader.load()
        self._log(f"Documentos cargados: {len(raw_docs)}")

        # 2. Dividir en chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " "],
        )
        chunks = splitter.split_documents(raw_docs)

        # Añadir metadatos útiles para el análisis del ataque
        for chunk in chunks:
            chunk.metadata["chunk_id"]    = _doc_fingerprint(chunk.page_content)
            chunk.metadata["ingested_at"] = datetime.utcnow().isoformat()
            chunk.metadata["is_poisoned"] = False  # marcador de baseline limpio

        self._log(f"Chunks generados: {len(chunks)} (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

        # 3. Guardar en ChromaDB (genera embeddings automáticamente)
        self._log("Generando embeddings y almacenando en ChromaDB...")
        self.vectorstore.add_documents(chunks)
        self._log(f"{len(chunks)} chunks almacenados en '{self.collection}' ✓", color=Fore.GREEN)

        return len(chunks)

    # ── Consulta ───────────────────────────────────────────────────────────

    def query(self, question: str, k: int = RETRIEVAL_K) -> dict:
        """
        Ejecuta una query completa: recupera contexto + (opcionalmente filtra
        con defensas) + genera respuesta.

        Returns:
            dict con 'answer', 'sources' (incluye similarity_score por chunk),
            'chunks_retrieved', 'chunks_filtered_by_defense'.
        """
        self._log(f"\n{'─'*60}")
        self._log(f"QUERY: {question}", color=Fore.YELLOW)

        # Recuperar chunks con score de similitud
        hits = self.vectorstore.similarity_search_with_relevance_scores(question, k=k)
        docs_with_scores = list(hits)

        # Aplicar defensas si estan activadas (P2-01).
        filtered = []
        if self.defense is not None:
            kept, filtered = self.defense.filter(docs_with_scores)
            docs_with_scores = kept

        sources = [
            {
                "source":           doc.metadata.get("source", "desconocido"),
                "chunk_id":         doc.metadata.get("chunk_id", ""),
                "is_poisoned":      doc.metadata.get("is_poisoned", False),
                "similarity_score": float(score) if score is not None else None,
                "snippet":          doc.page_content[:120] + "...",
            }
            for doc, score in docs_with_scores
        ]

        self._log(f"Chunks recuperados: {len(docs_with_scores)}"
                  + (f" (filtrados por defensa: {len(filtered)})" if filtered else ""))
        for i, src in enumerate(sources):
            poison_tag = f"{Fore.RED}[ENVENENADO]" if src["is_poisoned"] else f"{Fore.GREEN}[LEGÍTIMO]"
            score_str = f"{src['similarity_score']:.4f}" if src["similarity_score"] is not None else "n/a"
            self._log(f"  [{i+1}] {poison_tag} score={score_str} {src['source']} | id={src['chunk_id']}")
            self._log(f"       Snippet: {src['snippet']}")

        # Generar respuesta
        if self._gen_chain:
            context = self._format_docs([doc for doc, _ in docs_with_scores])
            answer = self._gen_chain.invoke({"context": context, "question": question})
        else:
            # Sin LLM: devolver el contexto raw
            answer = "─── CONTEXTO RECUPERADO (sin LLM) ───\n\n"
            for i, (doc, _) in enumerate(docs_with_scores):
                answer += f"[Chunk {i+1}] {doc.page_content}\n\n"

        self._log(f"\nRESPUESTA:\n{answer}", color=Fore.CYAN)

        return {
            "question":                  question,
            "answer":                    answer,
            "sources":                   sources,
            "chunks_retrieved":          len(docs_with_scores),
            "chunks_filtered_by_defense": [
                {
                    "source":   doc.metadata.get("source", "desconocido"),
                    "chunk_id": doc.metadata.get("chunk_id", ""),
                    "reason":   reason,
                    "similarity_score": float(score) if score is not None else None,
                }
                for doc, score, reason in filtered
            ],
        }

    def similarity_search(self, question: str, k: int = RETRIEVAL_K) -> list:
        """Recupera chunks con score de similitud (para análisis del ataque)."""
        return self.vectorstore.similarity_search_with_relevance_scores(question, k=k)

    def collection_stats(self) -> dict:
        """Estadísticas de la colección ChromaDB."""
        count = self.vectorstore._collection.count()
        return {
            "collection":   self.collection,
            "total_chunks": count,
            "persist_dir":  CHROMA_PERSIST,
            "embedding_model": EMBEDDING_MODEL,
        }

    def clear_collection(self):
        """Vacía la colección (útil para reiniciar el estado)."""
        self.vectorstore._collection.delete(
            where={"chunk_id": {"$ne": ""}}
        )
        self._log(f"Colección '{self.collection}' vaciada ✓", color=Fore.YELLOW)

    # ── Internos ───────────────────────────────────────────────────────────

    @staticmethod
    def _format_docs(docs) -> str:
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    def _log(self, msg: str, color: str = Style.RESET_ALL):
        if self.verbose:
            print(f"{color}{msg}{Style.RESET_ALL}")
