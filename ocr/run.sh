#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

if [[ ! -d .venv ]]; then
  echo "创建 Python 虚拟环境..."
  if command -v uv >/dev/null 2>&1; then
    uv venv .venv --python "${PYTHON_VERSION:-3.11}"
    uv pip install --python .venv/bin/python -e ".[dev]"
  else
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e ".[dev]"
  fi
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已创建 .env。请先填写 SILICONFLOW_API_KEY，再重新运行本脚本。"
  exit 1
fi

if grep -q "SILICONFLOW_API_KEY=sk-your-key" .env 2>/dev/null; then
  echo "提示：.env 中的 SILICONFLOW_API_KEY 仍是示例值；云端识别会被阻止。"
fi

echo "Soran OCR 启动：http://${HOST}:${PORT}"
exec .venv/bin/uvicorn app.main:app --host "${HOST}" --port "${PORT}"
