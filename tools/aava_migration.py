#!/usr/bin/env python3
"""
AAVA migration toolkit (Python version).

Replaces shell-only orchestration with a structured CLI for better maintainability
and cross-platform behavior.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional

DEFAULT_SOURCE_CANDIDATES = [
    r"D:\AAVA_Project_clean",
    r"E:\AAVA_Final_Backup",
]

DEFAULT_SCAN_TARGETS = [
    r"D:\AAVA_Project_clean",
    r"C:\Users\David\Music",
    r"C:\Users\David\Downloads",
    r"E:\AAVA_Final_Backup",
]

MARKER_RE = re.compile(r"(^|[^a-z])(ios|aios|ai\s*os|version|release|build|ubuntu)($|[^a-z])", re.IGNORECASE)


def normalize_windows_path(path: str) -> Path:
    p = path.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", p)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2)
        return Path(f"/mnt/{drive}/{rest}")
    return Path(p)


def iter_pdfs(root: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pdf"):
                yield Path(dirpath) / name


def choose_extractor() -> str:
    if shutil.which("pdftotext"):
        return "pdftotext"

    # Lightweight availability check for pypdf.
    check = subprocess.run(
        [sys.executable, "-c", "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('pypdf') else 1)"],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return "python-pypdf"

    if shutil.which("strings"):
        return "strings"

    return "none"


def extract_pdf_text(pdf_path: Path, extractor: str) -> Optional[str]:
    if extractor == "pdftotext":
        proc = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None

    if extractor == "python-pypdf":
        code = (
            "from pypdf import PdfReader\n"
            "import sys\n"
            "r=PdfReader(sys.argv[1])\n"
            "print('\\n\\n'.join((p.extract_text() or '') for p in r.pages))\n"
        )
        proc = subprocess.run([sys.executable, "-c", code, str(pdf_path)], capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None

    if extractor == "strings":
        proc = subprocess.run(["strings", str(pdf_path)], capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None

    return None


def cmd_bootstrap(args: argparse.Namespace) -> int:
    dest_root = Path(args.dest_root)
    if not dest_root.is_dir():
        print(f"ERROR: Destination root does not exist: {dest_root}", file=sys.stderr)
        return 2

    source_candidates = args.sources or DEFAULT_SOURCE_CANDIDATES
    selected: Optional[Path] = None
    for candidate in source_candidates:
        mapped = normalize_windows_path(candidate)
        if mapped.is_dir():
            selected = mapped
            break

    if selected is None:
        print("ERROR: Could not find source folder in this environment.", file=sys.stderr)
        print("Checked:", file=sys.stderr)
        for c in source_candidates:
            print(f"  - {c} (mapped: {normalize_windows_path(c)})", file=sys.stderr)
        return 2

    target = dest_root / args.new_name
    if target.exists():
        print(f"ERROR: Target already exists: {target}", file=sys.stderr)
        return 2

    print(f"Selected source: {selected}")
    print(f"Creating working copy: {target}")
    shutil.copytree(selected, target)
    print("Copy complete.")
    return 0


def cmd_deep_scan(args: argparse.Namespace) -> int:
    targets = args.paths or DEFAULT_SCAN_TARGETS
    print("== AAVA deep scan ==")
    print(f"UTC timestamp: {dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}")
    print()

    found_any = False
    for raw in targets:
        mapped = normalize_windows_path(raw)
        print("## Target")
        print(f"- Input:  {raw}")
        print(f"- Mapped: {mapped}")

        if not mapped.exists():
            print("- Status: MISSING in this environment")
            print()
            continue

        found_any = True
        if mapped.is_dir():
            print("- Status: DIRECTORY")

            top_entries = list(mapped.iterdir())[:50]
            print("- Top-level entries:")
            for p in top_entries:
                print(f"  - {p}")

            pdfs = list(iter_pdfs(mapped))[:200]
            print("- PDF files (first 200):")
            for p in pdfs:
                print(f"  - {p}")

            repos = []
            for dirpath, dirnames, _ in os.walk(mapped):
                if ".git" in dirnames:
                    repos.append(Path(dirpath))
                if len(repos) >= 100:
                    break
            print("- Likely repo roots (first 100):")
            for r in repos[:100]:
                print(f"  - {r}")
        else:
            print("- Status: FILE")
            print(f"- File: {mapped}")
        print()

    if not found_any:
        print("No target paths are mounted/available in this environment.")
        print("If using WSL/Linux, mount C:/D:/E: under /mnt/c, /mnt/d, /mnt/e.")
    return 0


def cmd_pdf_scan(args: argparse.Namespace) -> int:
    root = normalize_windows_path(args.search_root)
    if not root.is_dir():
        print(f"ERROR: Search root does not exist in this environment: {root}", file=sys.stderr)
        return 2

    pdfs = list(iter_pdfs(root))
    if not pdfs:
        print(f"No PDFs found under: {root}")
        return 0

    extractor = choose_extractor()
    if extractor == "none":
        print("ERROR: No extractor available (install pdftotext, pypdf, or strings).", file=sys.stderr)
        return 2

    print(f"Found {len(pdfs)} PDF(s). Using extractor: {extractor}")
    print("Scanning for markers: iOS, AIOS, AI OS, version, release, build, ubuntu")

    for pdf in pdfs:
        print(f"\n=== {pdf} ===")
        text = extract_pdf_text(pdf, extractor)
        if text is None:
            print(f"(Unable to parse with extractor: {extractor})")
            continue

        matched = 0
        for i, line in enumerate(text.splitlines(), start=1):
            if MARKER_RE.search(line):
                print(f"{i}:{line}")
                matched += 1
                if matched >= 80:
                    break
        if matched == 0:
            print("(No matching markers found)")
    return 0


def cmd_kickoff(args: argparse.Namespace) -> int:
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    report_dir = Path("reports") / ts
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "kickoff_report.md"

    steps = [
        ("Bootstrap copy", ["bootstrap", "--new-name", args.new_name, "--dest-root", args.dest_root]),
        ("Deep scan default targets", ["deep-scan"]),
        ("PDF scan Downloads", ["pdf-scan", "--search-root", r"C:\Users\David\Downloads"]),
        ("PDF scan Music", ["pdf-scan", "--search-root", r"C:\Users\David\Music"]),
    ]

    report_lines: List[str] = [
        "# AAVA Migration Kickoff Report",
        "",
        f"- UTC time: {dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}",
        f"- Requested working copy name: {args.new_name}",
        f"- Destination root: {args.dest_root}",
        "",
    ]

    for title, step_args in steps:
        proc = subprocess.run([sys.executable, __file__, *step_args], capture_output=True, text=True)
        log_name = f"{title.replace(' ', '_')}.log"
        (report_dir / log_name).write_text(proc.stdout + ("\n" + proc.stderr if proc.stderr else ""))

        report_lines.extend(
            [
                f"## {title}",
                "",
                f"- Exit code: {proc.returncode}",
                f"- Log file: `{log_name}`",
                "",
            ]
        )

    report_file.write_text("\n".join(report_lines))
    print("Kickoff complete.")
    print(f"Report: {report_file}")
    print(f"Logs:   {report_dir}/*.log")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AAVA migration toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bootstrap = sub.add_parser("bootstrap", help="Copy source project into a renamed working folder")
    p_bootstrap.add_argument("--new-name", default="AAVA_Project_vNext")
    p_bootstrap.add_argument("--dest-root", default="/workspace")
    p_bootstrap.add_argument("--sources", nargs="*", help="Optional source candidate list")
    p_bootstrap.set_defaults(func=cmd_bootstrap)

    p_scan = sub.add_parser("deep-scan", help="Deep scan source locations")
    p_scan.add_argument("paths", nargs="*", help="Optional paths to scan")
    p_scan.set_defaults(func=cmd_deep_scan)

    p_pdf = sub.add_parser("pdf-scan", help="Scan PDFs for version markers")
    p_pdf.add_argument("--search-root", default=".")
    p_pdf.set_defaults(func=cmd_pdf_scan)

    p_kick = sub.add_parser("kickoff", help="Run bootstrap + scans and write report")
    p_kick.add_argument("--new-name", default="AAVA_Project_vNext")
    p_kick.add_argument("--dest-root", default="/workspace")
    p_kick.set_defaults(func=cmd_kickoff)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
