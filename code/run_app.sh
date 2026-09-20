#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if command -v xdg-open >/dev/null 2>&1; then
  (sleep 2 && xdg-open http://localhost:8501 >/dev/null 2>&1) &
elif command -v open >/dev/null 2>&1; then
  (sleep 2 && open http://localhost:8501 >/dev/null 2>&1) &
fi
python -m streamlit run app.py --server.headless=false --server.port 8501
