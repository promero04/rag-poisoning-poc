#!/usr/bin/env bash
# setup.sh — Configuración del entorno para RAG Poisoning PoC
# ============================================================
# Uso: bash setup.sh

set -e

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  RAG Poisoning PoC — Setup del entorno"
echo "  Asignatura: Seguridad (SDI) — Deusto 2025/26"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Directorio del proyecto ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Python virtual environment ───────────────────────────────────────────────
echo "→ Creando entorno virtual Python..."
python3 -m venv .venv
source .venv/bin/activate

echo "→ Actualizando pip..."
pip install --upgrade pip --quiet

echo "→ Instalando PyTorch CPU (evita descargar CUDA ~3GB)..."
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

echo "→ Instalando dependencias RAG (puede tardar 2-3 min)..."
pip install --no-cache-dir -r requirements.txt

# ── Fichero .env ─────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "→ Creando .env desde .env.example..."
    cp .env.example .env
    echo ""
    echo "  ⚠  Edita .env para configurar tu LLM:"
    echo "     - LLM_PROVIDER=ollama  (requiere: ollama pull llama3.2)"
    echo "     - LLM_PROVIDER=openai  (requiere: OPENAI_API_KEY=sk-...)"
    echo "     - LLM_PROVIDER=none    (solo recuperación, sin generación)"
fi

# ── Crear carpetas necesarias ─────────────────────────────────────────────────
mkdir -p chroma_db resultados

# ── Verificar Ollama (opcional) ───────────────────────────────────────────────
if command -v ollama &>/dev/null; then
    echo ""
    echo "→ Ollama detectado. Modelos disponibles:"
    ollama list 2>/dev/null || true
    echo ""
    echo "  Si no tienes llama3.2, ejecuta: ollama pull llama3.2"
else
    echo ""
    echo "  ℹ  Ollama no instalado. Para instalar:"
    echo "     curl -fsSL https://ollama.com/install.sh | sh"
    echo "     ollama pull llama3.2"
    echo ""
    echo "  Alternativa: edita .env → LLM_PROVIDER=none  (modo sin LLM)"
fi

# ── Test rápido ───────────────────────────────────────────────────────────────
echo ""
echo "→ Verificando instalación..."
python3 -c "
import chromadb
import langchain
from sentence_transformers import SentenceTransformer
print('  ✓ ChromaDB:', chromadb.__version__)
print('  ✓ LangChain:', langchain.__version__)
print('  ✓ sentence-transformers: OK')
"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Setup completado. Próximos pasos:"
echo ""
echo "  1. Activar entorno:  source .venv/bin/activate"
echo "  2. Ingestar docs:    python ingest.py"
echo "  3. Demo completa:    python demo_baseline.py"
echo "  4. Query manual:     python query.py"
echo "═══════════════════════════════════════════════════════════"
echo ""
