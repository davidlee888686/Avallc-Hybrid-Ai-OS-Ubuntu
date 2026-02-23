#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./tools/find_versions_from_pdfs.sh [search-root]
#
# Examples:
#   ./tools/find_versions_from_pdfs.sh /workspace
#   ./tools/find_versions_from_pdfs.sh 'C:\Users\David\Downloads'

INPUT_ROOT="${1:-.}"
MARKER_REGEX='(^|[^a-z])(ios|aios|ai\s*os|version|release|build|ubuntu)($|[^a-z])'

normalize_windows_path() {
  local path="$1"

  # Convert backslashes to slashes for easier pattern matching.
  path="${path//\\//}"

  # Convert C:/Users/... -> /mnt/c/Users/... if applicable (WSL-style mount).
  if [[ "$path" =~ ^([A-Za-z]):/(.*)$ ]]; then
    local drive
    drive="${BASH_REMATCH[1],,}"
    local rest
    rest="${BASH_REMATCH[2]}"
    echo "/mnt/${drive}/${rest}"
    return 0
  fi

  echo "$path"
}

choose_extractor() {
  if command -v pdftotext >/dev/null 2>&1; then
    echo "pdftotext"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    if python3 - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec('pypdf') else 1)
PY
    then
      echo "python-pypdf"
      return 0
    fi
  fi

  if command -v strings >/dev/null 2>&1; then
    echo "strings"
    return 0
  fi

  echo "none"
}

extract_with_pypdf() {
  local pdf="$1"
  local out="$2"
  python3 - "$pdf" "$out" <<'PY'
import sys
from pathlib import Path
from pypdf import PdfReader

pdf_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])

texts = []
try:
    reader = PdfReader(str(pdf_path))
    for page in reader.pages:
      texts.append(page.extract_text() or "")
except Exception:
    raise SystemExit(1)

out_path.write_text("\n\n".join(texts), encoding="utf-8", errors="ignore")
PY
}

SEARCH_ROOT="$(normalize_windows_path "$INPUT_ROOT")"

if [ ! -d "$SEARCH_ROOT" ]; then
  echo "ERROR: Search root does not exist in this environment: $SEARCH_ROOT" >&2
  echo "Tip: Windows paths like C:\\Users\\... are mapped to /mnt/c/Users/... on Linux/WSL." >&2
  exit 2
fi

mapfile -t pdfs < <(rg --files "$SEARCH_ROOT" 2>/dev/null | rg -i '\.pdf$' || true)

if [ "${#pdfs[@]}" -eq 0 ]; then
  echo "No PDFs found under: $SEARCH_ROOT"
  exit 0
fi

extractor="$(choose_extractor)"
if [ "$extractor" = "none" ]; then
  echo "ERROR: No PDF extractor available. Install one of: pdftotext, python3+pypdf, or strings." >&2
  exit 2
fi

echo "Found ${#pdfs[@]} PDF(s). Using extractor: $extractor"
echo "Scanning for markers: iOS, AIOS, AI OS, version, release, build, ubuntu"

for pdf in "${pdfs[@]}"; do
  echo
  echo "=== $pdf ==="
  text_tmp="$(mktemp)"

  parsed_ok=0
  case "$extractor" in
    pdftotext)
      if pdftotext -layout "$pdf" "$text_tmp" 2>/dev/null; then
        parsed_ok=1
      fi
      ;;
    python-pypdf)
      if extract_with_pypdf "$pdf" "$text_tmp" 2>/dev/null; then
        parsed_ok=1
      fi
      ;;
    strings)
      if strings "$pdf" > "$text_tmp" 2>/dev/null; then
        parsed_ok=1
      fi
      ;;
  esac

  if [ "$parsed_ok" -eq 1 ]; then
    rg -n -i "$MARKER_REGEX" "$text_tmp" | head -n 80 || echo "(No matching markers found)"
  else
    echo "(Unable to parse this PDF with extractor: $extractor)"
  fi

  rm -f "$text_tmp"
done
