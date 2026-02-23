#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a working copy of the AAVA project from Windows drives.
#
# Default source priority:
#   1) D:\AAVA_Project_clean
#   2) E:\AAVA_Final_Backup
#
# Usage:
#   ./tools/bootstrap_aava_project.sh [new-name] [destination-root]
#
# Example:
#   ./tools/bootstrap_aava_project.sh AAVA_Project_vNext /workspace

NEW_NAME="${1:-AAVA_Project_vNext}"
DEST_ROOT="${2:-/workspace}"

SOURCE_CANDIDATES=(
  'D:\AAVA_Project_clean'
  'E:\AAVA_Final_Backup'
)

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

pick_source_path() {
  local candidate
  for candidate in "${SOURCE_CANDIDATES[@]}"; do
    local mapped
    mapped="$(normalize_windows_path "$candidate")"
    if [ -d "$mapped" ]; then
      echo "$mapped"
      return 0
    fi
  done
  return 1
}

if [ ! -d "$DEST_ROOT" ]; then
  echo "ERROR: Destination root does not exist: $DEST_ROOT" >&2
  exit 2
fi

SOURCE_PATH="$(pick_source_path || true)"
if [ -z "$SOURCE_PATH" ]; then
  echo "ERROR: Could not find source folder in this environment." >&2
  echo "Checked:" >&2
  for candidate in "${SOURCE_CANDIDATES[@]}"; do
    mapped="$(normalize_windows_path "$candidate")"
    echo "  - $candidate (mapped: $mapped)" >&2
  done
  echo "Tip: In Linux/WSL, ensure Windows drives are mounted under /mnt/d and /mnt/e." >&2
  exit 2
fi

TARGET_PATH="$DEST_ROOT/$NEW_NAME"
if [ -e "$TARGET_PATH" ]; then
  echo "ERROR: Target already exists: $TARGET_PATH" >&2
  exit 2
fi

echo "Selected source: $SOURCE_PATH"
echo "Creating working copy: $TARGET_PATH"

cp -a "$SOURCE_PATH" "$TARGET_PATH"

echo "Copy complete."

# Lightweight inventory to help kickoff.
echo "---"
echo "Top-level files/folders (first 60):"
find "$TARGET_PATH" -maxdepth 1 -mindepth 1 2>/dev/null | head -n 60

echo "---"
echo "Detected project manifests (first 120):"
rg --files "$TARGET_PATH" 2>/dev/null | rg -i '(^|/)(readme(\.md|\.txt)?|package\.json|pyproject\.toml|requirements\.txt|cargo\.toml|go\.mod|pom\.xml|build\.gradle|dockerfile|compose\.ya?ml)$' | head -n 120 || true

echo "---"
echo "Next step (optional): run deep scan"
echo "  ./tools/deep_scan_aava_sources.sh '$(normalize_windows_path 'D:\AAVA_Project_clean')'"
