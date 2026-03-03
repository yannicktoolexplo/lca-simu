#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/workspaces/lca-simu"
APP_PATH="$ROOT_DIR/streamlit_supply_risk_app.py"

if [ ! -f "$APP_PATH" ]; then
  echo "App not found: $APP_PATH" >&2
  exit 1
fi

cd "$ROOT_DIR"
exec streamlit run "$APP_PATH"

