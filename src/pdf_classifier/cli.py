#!/usr/bin/env python3
"""PDF Classifier CLI - Classify and organize PDF documents using Claude."""

import argparse
import os
import shutil
import sys
from pathlib import Path

from .analyzer import analyze_document, load_rules
from .ocr import extract_text, needs_ocr, run_ocr


def main():
    parser = argparse.ArgumentParser(
        description="Classify and organize PDF documents using Claude AI"
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the PDF file to classify"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without actually moving files"
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR even if document has no text"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--rules",
        type=str,
        help="Path to custom rules.json file"
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()

    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    if not pdf_path.suffix.lower() == ".pdf":
        print(f"Error: Not a PDF file: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Load rules
    rules_path = Path(args.rules) if args.rules else None
    try:
        rules = load_rules(rules_path)
    except FileNotFoundError:
        print("Error: rules.json not found", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Processing: {pdf_path.name}")

    # Check if OCR is needed
    if not args.no_ocr and needs_ocr(pdf_path):
        if args.verbose:
            print("  Running OCR...")
        if not run_ocr(pdf_path):
            print(f"Warning: OCR failed for {pdf_path.name}", file=sys.stderr)

    # Extract text
    text = extract_text(pdf_path)
    if not text.strip():
        print(f"Warning: No text extracted from {pdf_path.name}", file=sys.stderr)
        if not args.dry_run:
            # Leave file in place if we can't read it
            sys.exit(0)

    # Analyze document
    if args.verbose:
        print("  Analyzing with Claude...")

    result = analyze_document(text, pdf_path.name, rules)

    # Expand ~ in destination path
    destination = Path(os.path.expanduser(result.destination))

    if args.verbose or args.dry_run:
        print(f"\nClassification Result:")
        print(f"  Category:    {result.category}")
        print(f"  Subcategory: {result.subcategory}")
        print(f"  Company:     {result.company}")
        print(f"  Doc Type:    {result.doc_type}")
        print(f"  Date:        {result.doc_date}")
        print(f"  Title:       {result.title}")
        print(f"  Confidence:  {result.confidence}")
        print(f"  Reasoning:   {result.reasoning}")
        print(f"\n  Destination: {destination}")
        print(f"  New name:    {result.new_filename}")

    if result.confidence == "low":
        print(f"\nWarning: Low confidence classification", file=sys.stderr)
        if not args.dry_run:
            print("File not moved. Use --dry-run to see details.", file=sys.stderr)
            sys.exit(0)

    if args.dry_run:
        print(f"\n[DRY RUN] Would move:")
        print(f"  From: {pdf_path}")
        print(f"  To:   {destination / result.new_filename}")
        sys.exit(0)

    # Create destination directory if needed
    destination.mkdir(parents=True, exist_ok=True)

    # Move and rename file
    new_path = destination / result.new_filename

    # Handle existing file
    if new_path.exists():
        # Add number suffix
        base = new_path.stem
        suffix = new_path.suffix
        counter = 1
        while new_path.exists():
            new_path = destination / f"{base} ({counter}){suffix}"
            counter += 1

    try:
        shutil.move(str(pdf_path), str(new_path))
        print(f"Moved: {pdf_path.name}")
        print(f"  To: {new_path}")
    except Exception as e:
        print(f"Error moving file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
