#!/usr/bin/env bash
set -euo pipefail

# Deep scan helper for mixed Windows/Linux paths.
# It gathers:
# - PDF inventory and marker hits
# - repository-like folders
# - key project files (README, package manifests, etc.)
#
# Usage:
#   ./tools/deep_scan_aava_sources.sh [path ...]
#
# Defaults (if no args provided):
#   D:\AAVA_Project_clean
#   C:\Users\David\Music
#   C:\Users\David\Downloads
#   E:\AAVA_Final_Backup

DEFAULT_PATHS=(
  'D:\AAVA_Project_clean'
  'C:\Users\David\Music'
  'C:\Users\David\Downloads'
  'E:\AAVA_Final_Backup'
)

if [ "$#" -gt 0 ]; then
  INPUT_PATHS=("$@")
else
  INPUT_PATHS=("${DEFAULT_PATHS[@]}")
fi

normalize_windows_path() {
  local path="$1"
  path="${path//\\//}"

  if [[ "$path" =~ ^([A-Za-z]):/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    local rest="${BASH_REMATCH[2]}"
    echo "/mnt/${drive}/${rest}"
  else
    echo "$path"
  fi
}

echo "== AAVA deep scan =="
date -u '+UTC timestamp: %Y-%m-%d %H:%M:%S'
echo

found_any=0
for raw in "${INPUT_PATHS[@]}"; do
  mapped="$(normalize_windows_path "$raw")"

  echo "## Target"
  echo "- Input:  $raw"
  echo "- Mapped: $mapped"

  if [ ! -e "$mapped" ]; then
    echo "- Status: MISSING in this environment"
    echo
    continue
  fi

  found_any=1
  if [ -d "$mapped" ]; then
    echo "- Status: DIRECTORY"

    echo "- Top-level entries:"
    find "$mapped" -maxdepth 1 -mindepth 1 2>/dev/null | head -n 50 | sed 's/^/  - /'

    echo "- PDF files (first 200):"
    rg --files "$mapped" 2>/dev/null | rg -i '\.pdf$' | head -n 200 | sed 's/^/  - /' || true

    echo "- Likely repo roots (first 100):"
    find "$mapped" -type d -name .git 2>/dev/null | sed 's#/\.git$##' | head -n 100 | sed 's/^/  - /' || true

    echo "- Key project files (first 200):"
    rg --files "$mapped" 2>/dev/null | rg -i '(^|/)(readme(\.md|\.txt)?|package\.json|pyproject\.toml|requirements\.txt|cargo\.toml|go\.mod|pom\.xml|build\.gradle|dockerfile|compose\.ya?ml)$' | head -n 200 | sed 's/^/  - /' || true

    echo "- PDF marker extraction attempt:"
    if [ -x "./tools/find_versions_from_pdfs.sh" ]; then
      ./tools/find_versions_from_pdfs.sh "$mapped" 2>&1 | sed 's/^/  /' | head -n 220
    else
      echo "  - Skipped: tools/find_versions_from_pdfs.sh not found"
    fi
  else
    echo "- Status: FILE"
    echo "- File info:"
    file "$mapped" 2>/dev/null | sed 's/^/  - /' || true
  fi
  echo

done

if [ "$found_any" -eq 0 ]; then
  echo "No target paths are mounted/available in this environment."
  echo "If you are using WSL/Linux, mount Windows drives so C:/D:/E: appear under /mnt/c, /mnt/d, /mnt/e."
fi
