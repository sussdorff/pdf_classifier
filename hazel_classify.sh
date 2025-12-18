#!/bin/bash
# Hazel wrapper script for PDF Classifier
# Usage: hazel_classify.sh "$1"
# Where $1 is the path to the PDF file (passed by Hazel)

set -e

PDF_PATH="$1"

if [ -z "$PDF_PATH" ]; then
    echo "Error: No PDF path provided"
    exit 1
fi

# Change to the project directory and run with uv
cd ~/code/pdf_classifier
uv run pdf-classifier "$PDF_PATH"
