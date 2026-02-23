#!/usr/bin/env bash
set -euo pipefail

# One-command kickoff for AAVA migration/discovery.
#
# Usage:
#   ./tools/start_aava_migration.sh [new-project-name] [destination-root]
#
# Example:
#   ./tools/start_aava_migration.sh AAVA_Project_vNext /workspace

NEW_NAME="${1:-AAVA_Project_vNext}"
DEST_ROOT="${2:-/workspace}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="reports/${TIMESTAMP}"
REPORT_FILE="${REPORT_DIR}/kickoff_report.md"

mkdir -p "$REPORT_DIR"

run_and_capture() {
  local title="$1"
  shift

  local log_file="$REPORT_DIR/${title// /_}.log"
  {
    echo "# $title"
    echo
    echo '```bash'
    printf '%q ' "$@"
    echo
    echo '```'
    echo
  } >> "$REPORT_FILE"

  set +e
  "$@" >"$log_file" 2>&1
  local code=$?
  set -e

  {
    echo "Exit code: $code"
    echo
    echo "Output:"
    echo
    echo '```text'
    sed -n '1,220p' "$log_file"
    echo '```'
    echo
  } >> "$REPORT_FILE"

  return 0
}

cat > "$REPORT_FILE" <<EOM
# AAVA Migration Kickoff Report

- UTC time: $(date -u '+%Y-%m-%d %H:%M:%S')
- Requested working copy name: ${NEW_NAME}
- Destination root: ${DEST_ROOT}

This report captures bootstrap, deep scan, and targeted PDF scan attempts.
EOM

run_and_capture "Bootstrap copy" ./tools/bootstrap_aava_project.sh "$NEW_NAME" "$DEST_ROOT"
run_and_capture "Deep scan default targets" ./tools/deep_scan_aava_sources.sh
run_and_capture "PDF scan Downloads" ./tools/find_versions_from_pdfs.sh 'C:\Users\David\Downloads'
run_and_capture "PDF scan Music" ./tools/find_versions_from_pdfs.sh 'C:\Users\David\Music'

cat <<EOM
Kickoff complete.
Report: $REPORT_FILE
Logs:   $REPORT_DIR/*.log
EOM
