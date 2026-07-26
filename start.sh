#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"

if [ ! -f "$FRONTEND_DIR/dist/index.html" ]; then
  echo "前端页面未构建，正在生成页面文件..."
  cd "$FRONTEND_DIR"
  if ! command -v pnpm >/dev/null 2>&1; then
    if command -v corepack >/dev/null 2>&1; then
      corepack enable pnpm
    fi
  fi
  if ! command -v pnpm >/dev/null 2>&1; then
    echo "未找到 pnpm。请先安装 pnpm，避免生成不一致的 npm 锁文件。"
    exit 1
  fi
  pnpm install --frozen-lockfile
  pnpm build
fi

cd "$BACKEND_DIR"
pkill -f "uvicorn app.main" 2>/dev/null
sleep 1
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 5173
