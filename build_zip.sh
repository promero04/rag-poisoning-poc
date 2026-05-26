#!/usr/bin/env bash
# Empaqueta el proyecto para entrega SDI Deusto 2025/26 — 29 may 2026
# Uso: bash build_zip.sh
# Genera: rag_poisoning_poc_romero_diez_furelos.zip en el directorio padre.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$PROJECT_DIR")"
NAME="rag_poisoning_poc_romero_diez_furelos"
STAGING="$PARENT_DIR/$NAME"
ZIP_PATH="$PARENT_DIR/$NAME.zip"

echo "==> Limpiando staging anterior..."
rm -rf "$STAGING" "$ZIP_PATH"
mkdir -p "$STAGING/codigo" "$STAGING/resultados/plots"

echo "==> Copiando código fuente..."
cp "$PROJECT_DIR"/*.py "$STAGING/codigo/"
cp "$PROJECT_DIR"/*.md "$STAGING/codigo/"
cp "$PROJECT_DIR"/requirements.txt "$STAGING/codigo/"
cp "$PROJECT_DIR"/pyproject.toml "$STAGING/codigo/"
cp "$PROJECT_DIR"/setup.sh "$STAGING/codigo/"
cp "$PROJECT_DIR"/.env.example "$STAGING/codigo/"
cp "$PROJECT_DIR"/.gitignore "$STAGING/codigo/"

echo "==> Copiando docs/ y datasets/..."
cp -R "$PROJECT_DIR"/docs "$STAGING/codigo/"
cp -R "$PROJECT_DIR"/datasets "$STAGING/codigo/"

echo "==> Copiando resultados del experimento..."
cp "$PROJECT_DIR"/resultados/*.json "$STAGING/resultados/" 2>/dev/null || true
cp "$PROJECT_DIR"/resultados/*.md "$STAGING/resultados/" 2>/dev/null || true
cp "$PROJECT_DIR"/resultados/plots/*.png "$STAGING/resultados/plots/" 2>/dev/null || true

echo "==> Copiando README a la raíz del ZIP..."
cp "$PROJECT_DIR"/README.md "$STAGING/README.md"

echo "==> Comprobando ENTREGABLE.pdf..."
if [[ -f "$PROJECT_DIR/ENTREGABLE.pdf" ]]; then
  cp "$PROJECT_DIR/ENTREGABLE.pdf" "$STAGING/ENTREGABLE.pdf"
  echo "    ✓ ENTREGABLE.pdf incluido"
else
  echo "    ⚠ ENTREGABLE.pdf NO existe — expórtalo antes de entregar:"
  echo "      pandoc ENTREGABLE.md -o ENTREGABLE.pdf --pdf-engine=xelatex -V geometry:margin=2cm -V mainfont=Helvetica --toc"
fi

echo "==> Limpiando artefactos no deseables del staging..."
find "$STAGING" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -type d -name "chroma_db" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -type d -name ".git" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -type d -name "logs" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$STAGING" -type f -name ".env" -delete 2>/dev/null || true
find "$STAGING" -type f -name ".DS_Store" -delete 2>/dev/null || true
find "$STAGING" -type f -name "build_zip.sh" -delete 2>/dev/null || true

echo "==> Creando ZIP..."
cd "$PARENT_DIR"
zip -qr "$ZIP_PATH" "$NAME"

SIZE_HUMAN=$(du -h "$ZIP_PATH" | cut -f1)
COUNT=$(unzip -l "$ZIP_PATH" | tail -1 | awk '{print $2}')

echo ""
echo "✅ ZIP creado:"
echo "   Ruta:      $ZIP_PATH"
echo "   Tamaño:    $SIZE_HUMAN"
echo "   Ficheros:  $COUNT"
echo ""
echo "==> Contenido (top 30 entradas):"
unzip -l "$ZIP_PATH" | head -35
echo ""
echo "==> Comprobaciones rápidas:"
unzip -l "$ZIP_PATH" | grep -q "ENTREGABLE.md" && echo "   ✓ ENTREGABLE.md presente" || echo "   ✗ ENTREGABLE.md FALTA"
unzip -l "$ZIP_PATH" | grep -q "baseline_results.json" && echo "   ✓ baseline_results.json presente" || echo "   ✗ baseline_results.json FALTA"
unzip -l "$ZIP_PATH" | grep -q "poisoning_comparison_k3.json" && echo "   ✓ poisoning_comparison_k3.json presente" || echo "   ✗ FALTA"
unzip -l "$ZIP_PATH" | grep -q "attack_per_query_k3.png" && echo "   ✓ gráficos presentes" || echo "   ✗ gráficos FALTAN"
unzip -l "$ZIP_PATH" | grep -q "\.env$" && echo "   ✗ AVISO: hay un .env (¡secretos!)" || echo "   ✓ sin .env (bien)"
unzip -l "$ZIP_PATH" | grep -q "chroma_db" && echo "   ✗ AVISO: hay chroma_db" || echo "   ✓ sin chroma_db (bien)"
unzip -l "$ZIP_PATH" | grep -q "ENTREGABLE.pdf" && echo "   ✓ ENTREGABLE.pdf presente" || echo "   ⚠ ENTREGABLE.pdf FALTA — exporta antes de entregar"

echo ""
echo "==> Limpiando staging temporal..."
rm -rf "$STAGING"

echo "Hecho."
