#!/bin/bash
# Sprint Health Agent - Report Generator
# Usage: ./run_report.sh

echo ""
echo "========================================"
echo "  Sprint Health Agent"
echo "  $(date)"
echo "========================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

echo "Generating sprint health report..."
echo ""

# Run the analysis and export HTML
python -m src.main export-html

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "  ERROR: Report generation failed!"
    echo "  "
    echo "  Make sure you have:"
    echo "  1. Installed dependencies: pip install -r requirements.txt"
    echo "  2. Configured config/config.json"
    echo "========================================"
    echo ""
    exit 1
fi

echo ""
echo "========================================"
echo "  Report generated successfully!"
echo "  Check your browser for the report."
echo "========================================"
echo ""

