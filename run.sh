#!/usr/bin/env bash
# 一鍵：打包前端 + 起 server（區網其他人可連）
set -euo pipefail
cd "$(dirname "$0")"
( cd web && bun install && bun run build )
cd server
if command -v uv >/dev/null; then
  uv run uvicorn banana.app:app --host 0.0.0.0 --port "${PORT:-8000}"
else
  python3 -m uvicorn banana.app:app --host 0.0.0.0 --port "${PORT:-8000}"
fi
